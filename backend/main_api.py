# coding=utf-8
import json
import os
import re
import sys
import logging
import hashlib
import secrets
import subprocess
import time
from collections import deque
from datetime import datetime, timedelta

from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import httpx

try:
    # 本地开发自动载入项目根 .env（已有的系统环境变量优先，不覆盖）
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"), override=False)
except ImportError:
    pass

if __package__ in (None, ""):
    # 目录方式运行（Docker WORKDIR /app 内 uvicorn main_api:app）
    from core.database import get_db, init_db, PhoneNumber, SmsRecord, AuditLog, SessionLocal, DATABASE_URL
    from core.database import SystemConfig, UploadFile as UploadFileRecord, AdminUser, MallCate, MallGoods
    from core.jwt_manager import JWTManager
    from core.cache import cache, is_redis_live
    from core.security import SecurityUtils
    from core.crypto import PasswordManager
    from display_pages import html_phones, html_sms, render_backups_page
    from monitor_console import html_console
else:
    # 包方式运行（pytest / uvicorn backend.main_api:app）
    from .core.database import get_db, init_db, PhoneNumber, SmsRecord, AuditLog, SessionLocal, DATABASE_URL
    from .core.database import SystemConfig, UploadFile as UploadFileRecord, AdminUser, MallCate, MallGoods
    from .core.jwt_manager import JWTManager
    from .core.cache import cache, is_redis_live
    from .core.security import SecurityUtils
    from .core.crypto import PasswordManager
    from .display_pages import html_phones, html_sms, render_backups_page
    from .monitor_console import html_console

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="TeleBot API")

# 跨域：8002 展示页要调 8000 的接口，真浏览器需预检放行；允许携带 Cookie 凭证
def _allowed_origins():
    extra = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    defaults = [
        "http://localhost:8000", "http://127.0.0.1:8000",
        "http://localhost:8002", "http://127.0.0.1:8002",
        "http://localhost:3000", "http://127.0.0.1:3000",
    ]
    return list(dict.fromkeys(extra + defaults))


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Request-ID"],
)

# 接口限流：同一 IP 每分钟上限（环境变量可调，测试可 monkeypatch 本全局量）
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = 60


# 请求日志环（监控台实时图表与日志流数据源，内存保留最近500条）
request_journal = deque(maxlen=500)


def _journal_level(status_code: int) -> str:
    if status_code >= 500:
        return "ERROR"
    if status_code >= 400:
        return "WARN"
    return "INFO"


@app.middleware("http")
async def rate_limit_and_audit(request: Request, call_next):
    # 健康检查/文档/预检不计入，其他请求限流；变更类请求写审计（失败也不影响主流程）
    path = request.url.path
    if request.method == "OPTIONS" or path in ("/health", "/api/health", "/openapi.json") or path.startswith("/docs"):
        return await call_next(request)
    ip = SecurityUtils.get_client_ip(request)
    try:
        key = f"ratelimit:{ip}"
        count = int(cache.incr(key))
        if count == 1:
            cache.expire(key, RATE_LIMIT_WINDOW)
        if count > RATE_LIMIT_REQUESTS:
            # 限流拒绝也带上 CORS 头，否则跨域页面读不到 429
            resp = JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后再试"})
            origin = request.headers.get("origin", "")
            if origin in _allowed_origins():
                resp.headers["Access-Control-Allow-Origin"] = origin
                resp.headers["Access-Control-Allow-Credentials"] = "true"
                resp.headers["Vary"] = "Origin"
            return resp
    except Exception:
        pass
    response = await call_next(request)
    # 监控台日志环：健康检查与指标自查不记，避免轮询污染图表
    if not path.startswith("/health") and not path.startswith("/api/metrics"):
        try:
            request_journal.append({
                "t": datetime.now().strftime("%H:%M:%S"),
                "method": request.method,
                "path": path,
                "status": response.status_code,
                "level": _journal_level(response.status_code),
            })
        except Exception:
            pass
    if request.method in ("POST", "PUT", "DELETE", "PATCH") and not path.startswith("/docs"):
        try:
            session = get_session(request)
            db = SessionLocal()
            try:
                db.add(AuditLog(
                    username=(session or {}).get("username", ""),
                    ip=ip, method=request.method, path=path,
                    status_code=response.status_code,
                ))
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"审计写入失败: {e}")
    return response
# 备份目录：优先用环境变量/Docker卷 /backups，不可写时回退到项目内 backups（跨平台）
def _resolve_backup_dir():
    candidates = [
        os.getenv("BACKUP_DIR", ""),
        "/backups",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backups"),
    ]
    for c in candidates:
        if not c:
            continue
        try:
            os.makedirs(c, exist_ok=True)
            # 可写性探测
            probe = os.path.join(c, ".write_test")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
            return c
        except Exception:
            continue
    fallback = os.path.join(os.getcwd(), "backups")
    os.makedirs(fallback, exist_ok=True)
    return fallback

BACKUP_DIR = _resolve_backup_dir()
logger.info(f"备份目录: {BACKUP_DIR}")


def _safe_backup_filename(filename: str) -> str:
    # 防路径穿越：只取基名，拒绝空名与含路径分隔符的原名
    if not filename or filename.strip() == "":
        raise HTTPException(status_code=400, detail="文件名不能为空")
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    name = os.path.basename(filename.strip())
    if name in ("", ".", ".."):
        raise HTTPException(status_code=400, detail="非法文件名")
    return name

API_KEY = os.getenv("API_KEY")
ENABLE_AUTH = os.getenv("ENABLE_AUTH", "false").lower() == "true"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")


def _verify_admin_password(plain: str) -> bool:
    # 生产用 argon2 哈希优先（ADMIN_PASSWORD_HASH），开发回退明文比对
    if ADMIN_PASSWORD_HASH:
        try:
            return PasswordManager.verify_password(plain, ADMIN_PASSWORD_HASH)
        except Exception as e:
            logger.warning(f"哈希验密异常: {e}")
            return False
    return hash_password(plain) == hash_password(ADMIN_PASSWORD)
# 密钥：优先环境变量（JWT_SECRET 兼容 security 配置），缺失则落盘复用，保证重启不掉线
SECRET_KEY = os.getenv("JWT_SECRET", os.getenv("SECRET_KEY", ""))


def _load_or_create_secret() -> str:
    global SECRET_KEY
    if SECRET_KEY:
        return SECRET_KEY
    secret_file = os.path.join(BACKUP_DIR, ".jwt_secret")
    try:
        if os.path.isfile(secret_file):
            SECRET_KEY = open(secret_file, "r").read().strip()
            if SECRET_KEY:
                return SECRET_KEY
    except Exception:
        pass
    SECRET_KEY = secrets.token_hex(32)
    try:
        with open(secret_file, "w") as f:
            f.write(SECRET_KEY)
    except Exception as e:
        logger.warning(f"密钥落盘失败（仅本次有效）: {e}")
    return SECRET_KEY


jwt_manager = JWTManager(_load_or_create_secret())
init_db()

# 登录防爆破：5 次失败锁定 15 分钟（与 SecurityConfig 对齐）
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_SECONDS = 15 * 60


def _login_fail_key(ip: str) -> str:
    return f"login_fail:{ip}"


def _is_login_locked(ip: str) -> bool:
    try:
        return int(cache.get(_login_fail_key(ip)) or 0) >= MAX_LOGIN_ATTEMPTS
    except Exception:
        return False


def _record_login_fail(ip: str) -> None:
    try:
        fails = int(cache.incr(_login_fail_key(ip)))
        if fails == 1:
            cache.expire(_login_fail_key(ip), LOGIN_LOCK_SECONDS)
    except Exception:
        pass


def _clear_login_fail(ip: str) -> None:
    try:
        cache.delete(_login_fail_key(ip))
    except Exception:
        pass

# Bot process reference
bot_process = None

def verify_api_key(request: Request, x_api_key: Optional[str] = Header(None)):
    if not ENABLE_AUTH:
        return True
    # 方式一：API Key（给外部程序调用）
    if API_KEY and x_api_key == API_KEY:
        return True
    # 方式二：后台登录态 JWT Cookie（给页面按钮用，同源自动带、同站跨端口需 credentials:include）
    if get_session(request):
        return True
    if not API_KEY:
        logger.warning("API_KEY未配置，已禁用认证")
        return True
    raise HTTPException(status_code=401, detail="Invalid API Key")

def get_session(request: Request):
    # JWT 会话：从 Cookie 取 token 验签，无状态，重启不掉线
    token = request.cookies.get("access_token") or request.cookies.get("session_id")
    if not token:
        return None
    try:
        payload = jwt_manager.verify_token(token)
        if payload.get("type") != "access":
            return None
        return {"user_id": payload.get("sub"), "username": payload.get("username"),
                "role": payload.get("role", "operator")}
    except Exception:
        return None

def require_login(request: Request):
    session = get_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session


def require_admin(request: Request):
    # 管理员角色校验（operator 只读与非破坏操作，删除/启停/密钥/账号等仅 admin）
    session = require_login(request)
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return session


def require_admin_or_key(request: Request, x_api_key: Optional[str] = Header(None)):
    # 破坏性操作：API Key 或管理员登录态任一通过（鉴权关闭时全放行）
    if not ENABLE_AUTH:
        return True
    if API_KEY and x_api_key == API_KEY:
        return {"username": "api-key", "role": "admin"}
    session = get_session(request)
    if session and session.get("role") == "admin":
        return session
    if not API_KEY:
        logger.warning("API_KEY未配置，已禁用认证")
        return True
    raise HTTPException(status_code=403, detail="需要管理员权限")


def _phone_to_dict(p: PhoneNumber) -> dict:
    return {"id": p.id, "number": p.number, "country": p.country,
            "status": p.status, "is_valid": p.is_valid}


def _sms_to_dict(s: SmsRecord) -> dict:
    return {"id": s.id, "phone": s.phone, "content": s.content,
            "sender": s.sender, "status": s.status,
            "retry_count": s.retry_count or 0, "error": s.error or ""}


# 短信队列：认领超时分钟数与最大重试次数
CLAIM_TIMEOUT_MIN = 5
SMS_MAX_RETRY = 3

class BackupPayload(BaseModel):
    account_id: int
    data: dict

class PhoneGenerateRequest(BaseModel):
    count: int = 1

class ValidatePhoneRequest(BaseModel):
    numbers: List[str]

class SendSMSRequest(BaseModel):
    phone: str
    content: str
    sender: str = "TelegramBot"

class LoginRequest(BaseModel):
    username: str
    password: str

def generate_hk_number():
    import random
    prefixes = ['5', '6', '9']
    prefix = random.choice(prefixes)
    number = ''.join([str(random.randint(0, 9)) for _ in range(7)])
    return f"+852{prefix}{number}"

def hash_password(password: str) -> str:
    return hashlib.sha256(f"{password}{SECRET_KEY}".encode()).hexdigest()

HTML_TEMPLATE = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>{% block title %}TeleBot 管理后台{% endblock %}</title>
  <style>
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f5f5;min-height:100vh}
    .header{background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:20px}
    .header h1{font-size:24px}
    .nav{padding:15px 20px;background:white;border-bottom:1px solid #e5e7eb;display:flex;gap:15px}
    .nav a{color:#667eea;text-decoration:none;padding:8px 16px;border-radius:6px}
    .nav a:hover,.nav a.active{background:#667eea;color:white}
    .container{max-width:1200px;margin:20px auto;padding:0 20px}
    .card{background:white;border-radius:12px;padding:24px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,0.1)}
    .btn{display:inline-block;padding:10px 20px;background:#667eea;color:white;border:none;border-radius:6px;cursor:pointer}
    .btn:hover{background:#5568d3}
    .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;margin-bottom:20px}
    .stat-card{background:white;padding:25px;border-radius:12px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.1)}
    .stat-card .num{font-size:36px;font-weight:bold;background:linear-gradient(135deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
    table{width:100%;border-collapse:collapse}
    th,td{padding:12px;border-bottom:1px solid #e5e7eb;text-align:left}
    th{background:#f9fafb;font-weight:600;color:#374151}
    .form-group{margin-bottom:15px}
    .form-group label{display:block;margin-bottom:6px;color:#555}
    .form-group input{width:100%;padding:10px;border:1px solid #e5e7eb;border-radius:6px}
    .login-form{max-width:400px;margin:100px auto}
  </style>
</head>
<body>
  {% if session %}
  <div class="header">
    <h1>🔒 TeleBot 管理后台</h1>
  </div>
  <nav class="nav">
    <a href="/admin/">📊 首页</a>
    <a href="/admin/phones">📱 号码管理</a>
    <a href="/admin/sms">💬 短信记录</a>
    <a href="/admin/backups">📦 备份管理</a>
    <a href="/admin/logout" style="margin-left:auto">🚪 退出</a>
  </nav>
  {% endif %}
  <div class="container">
    {% block content %}{% endblock %}
  </div>
</body>
</html>
"""

LOGIN_PAGE = HTML_TEMPLATE.replace("{% block content %}{% endblock %}", """
<div class="card login-form">
  <h2>管理员登录</h2>
  <form action="/admin/login" method="post">
    <div class="form-group">
      <label>用户名</label>
      <input type="text" name="username" required>
    </div>
    <div class="form-group">
      <label>密码</label>
      <input type="password" name="password" required>
    </div>
    <button type="submit" class="btn" style="width:100%">登录</button>
  </form>
</div>
""").replace("{% block title %}TeleBot 管理后台{% endblock %}", "登录 - TeleBot")

ADMIN_SHELL = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>TeleBot 管理后台</title>
  <style>
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#111827;color:#e5e7eb;height:100vh;display:flex;flex-direction:column}
    .topbar{background:#1f2937;padding:12px 20px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #374151}
    .topbar h1{font-size:18px}
    .topbar a{color:#9ca3af;text-decoration:none}
    .topbar a:hover{color:#fff}
    .wrap{flex:1;display:flex;min-height:0}
    .sidebar{width:200px;background:#1f2937;border-right:1px solid #374151;padding:12px 0;flex-shrink:0}
    .sidebar button{display:block;width:100%;text-align:left;background:none;border:none;color:#d1d5db;padding:12px 20px;font-size:14px;cursor:pointer;border-left:3px solid transparent}
    .sidebar button:hover{background:#374151;color:#fff}
    .sidebar button.active{background:#374151;color:#fff;border-left-color:#22c55e}
    .content{flex:1;min-width:0}
    .content iframe{width:100%;height:100%;border:none;background:#fff}
    @media (max-width:768px){
      .wrap{flex-direction:column}
      .sidebar{width:100%;display:flex;overflow-x:auto;padding:0;border-right:none;border-bottom:1px solid #374151}
      .sidebar button{white-space:nowrap;border-left:none;border-bottom:3px solid transparent;padding:10px 14px}
      .sidebar button.active{border-bottom-color:#22c55e}
      .topbar h1{font-size:15px}
    }
  </style>
</head>
<body>
  <div class="topbar">
    <h1>🤖 TeleBot 管理后台</h1>
    <a href="/admin/logout">🚪 退出</a>
  </div>
  <div class="wrap">
    <div class="sidebar">
      <button data-src="/admin/console" class="active">📊 监控台</button>
      <button data-src="/admin/phones">📱 号码管理</button>
      <button data-src="/admin/sms">💬 短信记录</button>
      <button data-src="/admin/backups">📦 备份管理</button>
      <button data-src="/docs">📖 接口文档</button>
    </div>
    <div class="content">
      <iframe id="mainframe" src="/admin/console"></iframe>
    </div>
  </div>
<script>
document.querySelectorAll('.sidebar button').forEach(function(b){
  b.addEventListener('click', function(){
    document.querySelectorAll('.sidebar button').forEach(function(x){x.classList.remove('active')});
    b.classList.add('active');
    document.getElementById('mainframe').src = b.getAttribute('data-src');
  });
});
</script>
</body>
</html>
"""

# 展示页模板已抽取到 display_pages.py（原8002富版本，R1并入统一后端）

@app.get('/health', include_in_schema=False)
def health():
    return {'status': 'ok', 'version': '1.0.0'}

@app.get('/api/health', include_in_schema=False)
def api_health():
    return {'status': 'ok', 'version': '1.0.0'}

@app.get('/', include_in_schema=False)
def root_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse('/admin/', status_code=302)

@app.get('/api/metrics/overview')
def metrics_overview(db: Session = Depends(get_db)):
    # 监控台指标卡：一口聚合（公开只读）
    phone_count = db.query(PhoneNumber).count()
    valid_count = db.query(PhoneNumber).filter(PhoneNumber.status == 'valid').count()
    sms_count = db.query(SmsRecord).count()
    audit_count = db.query(AuditLog).count()
    queue = {}
    for st in ("queued", "sending", "sent", "failed"):
        queue[st] = db.query(SmsRecord).filter(SmsRecord.status == st).count()
    return {'phones': phone_count, 'valid_phones': valid_count, 'sms': sms_count,
            'backups': len(_list_backup_files()), 'audit': audit_count, 'sms_queue': queue}


@app.get('/api/metrics/recent')
def metrics_recent():
    # 监控台图表+日志流：按分钟分桶的请求量与最近明细（公开只读）
    per_min = {}
    for e in request_journal:
        per_min[e["t"][:5]] = per_min.get(e["t"][:5], 0) + 1
    minutes = sorted(per_min)[-20:]
    buckets = [per_min[m] for m in minutes] if minutes else [0] * 20
    entries = list(request_journal)[-30:]
    entries.reverse()
    return {'buckets': buckets, 'labels': minutes, 'entries': entries}


@app.get('/api/system/status')
def system_status():
    # 监控台服务健康：各依赖真实探活（公开只读）
    bot_alive = bot_process is not None and bot_process.poll() is None
    try:
        from opentele.td import TDesktop  # noqa
        opentele_ok = True
    except ImportError:
        opentele_ok = False
    return {
        'backend': {'ok': True, 'label': '统一后端:8000'},
        'database': {'ok': True, 'label': 'SQLite' if DATABASE_URL.startswith('sqlite') else 'MySQL'},
        'redis': {'ok': is_redis_live(), 'label': 'Redis' if is_redis_live() else '内存降级'},
        'bot': {'ok': bot_alive, 'label': '机器人运行中' if bot_alive else '机器人未运行'},
        'converter': {'ok': opentele_ok, 'label': '转换可用' if opentele_ok else '转换降级'},
    }


@app.get('/api/', include_in_schema=False)
def api_root():    return {
        'service': 'TeleBot API',
        'version': '1.0.0',
        'endpoints': [
            '/api/health',
            '/api/phone/list',
            '/api/phone/generate',
            '/api/phone/validate',
            '/api/phone/import',
            '/api/sms/list',
            '/api/sms/send',
            '/api/backup/import',
            '/api/backup/import_json',
            '/api/metrics/overview',
            '/api/metrics/recent',
            '/api/system/status',
            '/api/system/config',
            '/api/upload',
            '/api/audit/logs',
            '/api/bot/log',
            '/api/bot/token',
            '/api/users',
            '/api/mall/cate',
            '/api/mall/goods',
            '/to-tdata',
            '/console',
            '/admin/console',
        ]
    }

@app.get('/admin/login', response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if session:
        return HTMLResponse(ADMIN_SHELL)
    return HTMLResponse(LOGIN_PAGE)

@app.post('/admin/login', response_class=HTMLResponse)
async def login(request: Request, username: str = Form(default=""), password: str = Form(default=""), db: Session = Depends(get_db)):
    # 兼容两种提交：页面表单（form）与接口调用（JSON）
    if not username:
        try:
            body = await request.json()
            username = body.get("username", "")
            password = body.get("password", "")
        except Exception:
            pass
    client_ip = SecurityUtils.get_client_ip(request)
    if _is_login_locked(client_ip):
        return HTMLResponse(LOGIN_PAGE + "<script>alert('失败次数过多，已锁定15分钟')</script>")
    authed = None  # (user_id, username, role)
    # 方式一：数据库账号（argon2，多账号多角色）
    if username:
        db_user = db.query(AdminUser).filter(AdminUser.username == username).first()
        if db_user and db_user.status == 1:
            try:
                if PasswordManager.verify_password(password, db_user.password_hash):
                    db_user.login_num += 1
                    db.commit()
                    authed = (db_user.id, db_user.username, db_user.role or "operator")
            except Exception:
                db.rollback()
    # 方式二：环境变量超级管理员（回退）
    if not authed and username == ADMIN_USERNAME and _verify_admin_password(password):
        authed = (1, ADMIN_USERNAME, "admin")
    if authed:
        _clear_login_fail(client_ip)
        token = jwt_manager.create_access_token(user_id=authed[0], username=authed[1], role=authed[2], expires_delta=timedelta(hours=12))
        response = HTMLResponse(ADMIN_SHELL)
        response.set_cookie('access_token', token, httponly=True, max_age=12 * 3600)
        response.delete_cookie("session_id")
        return response
    _record_login_fail(client_ip)
    return HTMLResponse(LOGIN_PAGE + "<script>alert('用户名或密码错误')</script>")

@app.get('/admin/logout')
def logout(request: Request):
    response = HTMLResponse(status_code=302)
    response.delete_cookie("access_token")
    response.delete_cookie("session_id")
    response.headers["Location"] = "/admin/login"
    return response

@app.get('/admin/', response_class=HTMLResponse)
def admin_home(request: Request, db: Session = Depends(get_db)):
    require_login(request)
    return HTMLResponse(ADMIN_SHELL)

@app.get('/admin/phones', response_class=HTMLResponse)
@app.get('/phones', response_class=HTMLResponse)
def admin_phones(request: Request):
    # /admin/* 需登录；/phones 别名保持原8002公开行为
    if request.url.path.startswith('/admin'):
        require_login(request)
    return HTMLResponse(html_phones)

@app.get('/admin/sms', response_class=HTMLResponse)
@app.get('/sms', response_class=HTMLResponse)
def admin_sms(request: Request):
    if request.url.path.startswith('/admin'):
        require_login(request)
    return HTMLResponse(html_sms)


def _list_backup_files():
    # 备份目录真实文件列表（过滤隐藏与密钥文件）
    items = []
    try:
        for name in sorted(os.listdir(BACKUP_DIR)):
            if name.startswith('.'):
                continue
            p = os.path.join(BACKUP_DIR, name)
            if not os.path.isfile(p):
                continue
            st = os.stat(p)
            size = st.st_size
            size_str = f"{size / 1024:.1f}KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f}MB"
            items.append((name, size_str, datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M')))
    except Exception as e:
        logger.warning(f"读取备份目录失败: {e}")
    return items


@app.get('/admin/backups', response_class=HTMLResponse)
@app.get('/backups', response_class=HTMLResponse)
def admin_backups(request: Request):
    if request.url.path.startswith('/admin'):
        require_login(request)
    return HTMLResponse(render_backups_page(_list_backup_files()))


@app.get('/admin/console', response_class=HTMLResponse)
@app.get('/console', response_class=HTMLResponse)
def monitor_console_page(request: Request):
    # 统一实时监控台（31号风格）；/admin/* 需登录，/console 公开展示
    if request.url.path.startswith('/admin'):
        require_login(request)
    return HTMLResponse(html_console)


class ToTdataBackup(BaseModel):
    data: str = ""
    format: str = "telethon_session"


class ToTdataRequest(BaseModel):
    backup: ToTdataBackup = ToTdataBackup()
    options: dict = {}
    password: str = ""  # 二次验证密码（账号开了才填）


@app.post('/to-tdata')
async def to_tdata(payload: ToTdataRequest):
    # 会话转换（原8002转换服务，R1并入统一后端；机器人经 CONVERTER_URL 调用）
    # 成功后打包为 BACKUP_DIR/tdata_*.zip，经 /api/backup/download/{name} 下载
    import shutil
    import tempfile
    session_str = (payload.backup.data or "").strip()
    if not session_str:
        return {"error": "empty_session", "detail": "缺少 session 字符串"}
    try:
        from opentele.td import TDesktop
        from opentele.tl import TelegramClient as TelethonToDesktop
        from opentele.api import API, UseCurrentSession
        api = API.TelegramDesktop.Generate()
        client = TelethonToDesktop(session_str, api=api)
        tdesk = await client.ToTDesktop(flag=UseCurrentSession, password=payload.password or None)
        tmpdir = tempfile.mkdtemp(prefix="tdata_")
        try:
            ok = tdesk.SaveTData(tmpdir)
        except Exception as e:
            shutil.rmtree(tmpdir, ignore_errors=True)
            return {"error": "save_failed", "detail": f"tdata落盘失败：{e}"}
        if not ok:
            shutil.rmtree(tmpdir, ignore_errors=True)
            return {"error": "save_failed", "detail": "tdata落盘失败（opentele返回False）"}
        fname = f"tdata_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip"
        zpath = os.path.join(BACKUP_DIR, fname)
        shutil.make_archive(zpath[:-4], "zip", tmpdir)
        shutil.rmtree(tmpdir, ignore_errors=True)
        return {"status": "ok", "format": "tdata", "file": fname,
                "download": f"/api/backup/download/{fname}", "detail": "转换成功，已打包"}
    except ImportError:
        logger.warning("opentele 未安装，转换请求已受理但未执行")
        return {"status": "queued", "format": "tdata", "detail": "opentele 未安装，需 pip install opentele 后重试"}
    except Exception as e:
        logger.error(f"转换失败: {e}")
        return {"error": "convert_failed", "detail": str(e)}


@app.get('/api/backup/download/{name}')
def download_backup(name: str, request: Request = None, _: dict = Depends(require_login)):
    # 下载备份/tdata包（需登录；点名防穿越，密钥与库文件不许下）
    filename = _safe_backup_filename(name)
    if filename.startswith(".") or filename.endswith((".db", ".bak")):
        raise HTTPException(status_code=400, detail="该文件不允许下载")
    path = os.path.join(BACKUP_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, filename=filename)

@app.post('/api/backup/import')
async def import_backup(file: UploadFile = File(...), _: bool = Depends(verify_api_key)):
    filename = _safe_backup_filename(file.filename)
    path = os.path.join(BACKUP_DIR, filename)
    with open(path, 'wb') as f:
        content = await file.read()
        f.write(content)
    return {'status': 'saved', 'path': path}

@app.post('/api/backup/import_json')
async def import_backup_json(payload: BackupPayload, _: bool = Depends(verify_api_key)):
    path = os.path.join(BACKUP_DIR, f'backup_{payload.account_id}.json')
    with open(path, 'w') as f:
        json.dump(payload.data, f)
    return {'status': 'saved', 'path': path}

@app.post('/api/phone/generate')
def generate_phone(request: PhoneGenerateRequest, db: Session = Depends(get_db), _: bool = Depends(verify_api_key)):
    count = min(max(request.count, 1), 100)
    generated = []
    attempts = 0
    while len(generated) < count and attempts < count * 10:
        # 随机号入库，撞唯一键则重试
        attempts += 1
        phone = generate_hk_number()
        row = PhoneNumber(number=phone, country="HK", status="generated", is_valid=False)
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
            generated.append({"id": row.id, "number": row.number, "country": "HK", "status": "generated"})
        except IntegrityError:
            db.rollback()
            continue
    logger.info(f"生成号码数量: {len(generated)}")
    return {'message': '生成成功', 'data': generated, 'count': len(generated)}

@app.post('/api/phone/validate')
def validate_phone(request: ValidatePhoneRequest, db: Session = Depends(get_db), _: bool = Depends(verify_api_key)):
    # 香港号码规则：+852 + 8位数字，首位为5/6/9；兼容8位本地号与带空格/横线输入
    # 库中存在的号码同步更新状态，方便按 valid/invalid 筛选
    results = []
    for raw in request.numbers:
        num = raw.replace(' ', '').replace('-', '').strip()
        local = ''
        if num.startswith('+852'):
            local = num[4:]
        elif num.startswith('852') and len(num) == 11:
            local = num[3:]
        elif len(num) == 8 and num.isdigit():
            local = num
        is_valid = len(local) == 8 and local.isdigit() and local[0] in '569'
        results.append({'number': raw, 'is_valid': is_valid, 'status': 'valid' if is_valid else 'invalid'})
    try:
        full_numbers = {r["number"] for r in results}
        rows = db.query(PhoneNumber).filter(PhoneNumber.number.in_(full_numbers)).all()
        verdict = {r["number"]: r for r in results}
        for row in rows:
            v = verdict.get(row.number)
            if v:
                row.is_valid = v["is_valid"]
                row.status = v["status"]
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"验证状态回写失败（不影响判定结果）: {e}")
    return {'data': results}


class ImportPhoneRequest(BaseModel):
    numbers: List[str]


@app.post('/api/phone/import')
def import_phones(request: ImportPhoneRequest, db: Session = Depends(get_db), _: bool = Depends(verify_api_key)):
    # 批量导入外部号码：仅收有效香港号，重复/非法分别计数（供脚本与后台导入用）
    imported, skipped_dup, skipped_invalid = 0, 0, []
    for raw in request.numbers:
        num = raw.replace(' ', '').replace('-', '').strip()
        local = ''
        if num.startswith('+852'):
            local = num[4:]
        elif num.startswith('852') and len(num) == 11:
            local = num[3:]
        elif len(num) == 8 and num.isdigit():
            local = num
        if not (len(local) == 8 and local.isdigit() and local[0] in '569'):
            skipped_invalid.append(raw)
            continue
        full = f"+852{local}"
        if db.query(PhoneNumber).filter(PhoneNumber.number == full).first():
            skipped_dup += 1
            continue
        db.add(PhoneNumber(number=full, country="HK", status="valid", is_valid=True))
        try:
            db.commit()
            imported += 1
        except IntegrityError:
            db.rollback()
            skipped_dup += 1
    return {'message': '导入完成', 'imported': imported,
            'skipped_dup': skipped_dup, 'skipped_invalid': skipped_invalid}

@app.get('/api/phone/list')
def list_phones(status: Optional[str] = None, limit: int = 200, offset: int = 0, db: Session = Depends(get_db), _: bool = Depends(verify_api_key)):
    limit = min(max(limit, 1), 1000)
    q = db.query(PhoneNumber).order_by(PhoneNumber.id.desc())
    if status:
        q = q.filter(PhoneNumber.status == status)
    total = q.count()
    rows = q.offset(max(offset, 0)).limit(limit).all()
    return {'data': [_phone_to_dict(p) for p in rows], 'total': total}


@app.delete('/api/phone/{phone_id}')
def delete_phone(phone_id: int, db: Session = Depends(get_db), _: bool = Depends(require_admin_or_key)):
    # 按ID删除号码（供管理页删除按钮使用）
    row = db.query(PhoneNumber).filter(PhoneNumber.id == phone_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="号码不存在")
    db.delete(row)
    db.commit()
    return {'message': '删除成功', 'id': phone_id}

@app.post('/api/sms/send')
def send_sms(request: SendSMSRequest, db: Session = Depends(get_db), _: bool = Depends(verify_api_key)):
    # 号码归一化：支持 +852XXXXXXXX / 852XXXXXXXX / 8位本地号，非法直接422
    raw = request.phone.replace(' ', '').replace('-', '').strip()
    local = ''
    if raw.startswith('+852'):
        local = raw[4:]
    elif raw.startswith('852') and len(raw) == 11:
        local = raw[3:]
    elif len(raw) == 8 and raw.isdigit():
        local = raw
    if not (len(local) == 8 and local.isdigit() and local[0] in '569'):
        raise HTTPException(status_code=422, detail="手机号格式不正确，需为香港8位号码（5/6/9开头）")
    phone = f"+852{local}"
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="短信内容不能为空")
    if len(content) > 1000:
        raise HTTPException(status_code=422, detail="短信内容超长（最多1000字）")
    logger.info(f"[SMS] 发送到 {phone}: {content}")
    row = SmsRecord(phone=phone, content=content, sender=request.sender, status="queued",
                    note="已入队，实际投递由 Telegram 客户端（bot）执行")
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'message': '发送成功', 'sms_id': row.id, 'phone': phone, 'status': 'queued'}

@app.get('/api/sms/list')
def list_sms(limit: int = 200, offset: int = 0, status: Optional[str] = None,
             db: Session = Depends(get_db), _: bool = Depends(verify_api_key)):
    limit = min(max(limit, 1), 1000)
    q = db.query(SmsRecord).order_by(SmsRecord.id.desc())
    if status:
        q = q.filter(SmsRecord.status == status)
    total = q.count()
    rows = q.offset(max(offset, 0)).limit(limit).all()
    return {'data': [_sms_to_dict(s) for s in rows], 'total': total}


@app.post('/api/sms/claim')
def claim_sms(db: Session = Depends(get_db), _: bool = Depends(verify_api_key)):
    # worker认领：取最老排队项，超时未回执的sending一并回收
    deadline = datetime.utcnow() - timedelta(minutes=CLAIM_TIMEOUT_MIN)
    row = (db.query(SmsRecord)
           .filter(SmsRecord.status == "queued")
           .order_by(SmsRecord.id)
           .first())
    if not row:
        row = (db.query(SmsRecord)
               .filter(SmsRecord.status == "sending", (SmsRecord.updated_at == None) | (SmsRecord.updated_at < deadline))
               .order_by(SmsRecord.id)
               .first())
    if not row:
        return {'message': '队列为空', 'data': None}
    row.status = "sending"
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return {'message': '认领成功', 'data': _sms_to_dict(row)}


class SmsResult(BaseModel):
    status: str  # sent | failed
    error: str = ""


@app.post('/api/sms/{sms_id}/complete')
def complete_sms(sms_id: int, body: SmsResult, db: Session = Depends(get_db), _: bool = Depends(verify_api_key)):
    if body.status not in ("sent", "failed"):
        raise HTTPException(status_code=422, detail="状态非法")
    row = db.query(SmsRecord).filter(SmsRecord.id == sms_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    if row.status not in ("sending", "queued"):
        raise HTTPException(status_code=409, detail=f"当前状态{row.status}不可回执")
    if body.status == "sent":
        row.status, row.error = "sent", ""
    else:
        row.retry_count = (row.retry_count or 0) + 1
        row.error = body.error[:500]
        # 未超重试回队列，超限终结为失败
        row.status = "queued" if row.retry_count < SMS_MAX_RETRY else "failed"
    row.updated_at = datetime.utcnow()
    db.commit()
    return {'message': '回执成功', 'data': _sms_to_dict(row)}


@app.post('/api/sms/{sms_id}/requeue')
def requeue_sms(sms_id: int, db: Session = Depends(get_db), _: bool = Depends(require_admin_or_key)):
    row = db.query(SmsRecord).filter(SmsRecord.id == sms_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    row.status, row.retry_count, row.error = "queued", 0, ""
    row.updated_at = datetime.utcnow()
    db.commit()
    return {'message': '已重发（回队列）', 'data': _sms_to_dict(row)}

@app.get('/api/bot/status')
def get_bot_status():
    global bot_process
    is_running = False
    if bot_process is not None:
        if bot_process.poll() is None:
            is_running = True
    return {'status': 'running' if is_running else 'stopped'}

@app.post('/api/bot/start')
def start_bot(_: bool = Depends(require_admin_or_key)):
    global bot_process
    if bot_process is not None and bot_process.poll() is None:
        return {'message': 'Bot is already running', 'status': 'running'}
    try:
        # 路径解析：环境变量优先，其次按项目结构自动定位（兼容Windows本地与Docker）
        bot_script = os.getenv("BOT_SCRIPT", "")
        bot_cwd = os.getenv("BOT_WORKDIR", "")
        if not bot_script or not os.path.isfile(bot_script):
            here = os.path.dirname(os.path.abspath(__file__))
            candidates = [
                os.path.join(here, "..", "bot", "bot.py"),
                os.path.join(os.getcwd(), "bot", "bot.py"),
                os.path.join("/app", "bot", "bot.py"),
            ]
            for c in candidates:
                if os.path.isfile(c):
                    bot_script = os.path.normpath(c)
                    bot_cwd = os.path.normpath(os.path.dirname(c))
                    break
        if not bot_script or not os.path.isfile(bot_script):
            return {'message': '未找到 bot.py（可用 BOT_SCRIPT 环境变量指定）', 'status': 'error'}
        if not bot_cwd:
            bot_cwd = os.path.dirname(bot_script)
        bot_process = subprocess.Popen([sys.executable, bot_script], cwd=bot_cwd)
        return {'message': 'Bot started successfully', 'status': 'running'}
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        return {'message': f'Failed to start bot: {str(e)}', 'status': 'error'}

@app.post('/api/bot/stop')
def stop_bot(_: bool = Depends(require_admin_or_key)):
    global bot_process
    if bot_process is None or bot_process.poll() is not None:
        return {'message': 'Bot is not running', 'status': 'stopped'}
    try:
        bot_process.terminate()
        bot_process.wait(timeout=5)
        return {'message': 'Bot stopped successfully', 'status': 'stopped'}
    except Exception as e:
        logger.error(f"Failed to stop bot: {e}")
        # Force kill if terminate fails
        if bot_process:
            bot_process.kill()
        return {'message': 'Bot stopped forcefully', 'status': 'stopped'}

# ================= R2：PHP后台迁移接口（配置/上传/审计/机器人/账号/商城） =================

class ConfigItem(BaseModel):
    key: str
    value: str = ""
    remark: str = ""


@app.get('/api/system/config')
def get_config(db: Session = Depends(get_db), _: bool = Depends(verify_api_key)):
    rows = db.query(SystemConfig).order_by(SystemConfig.key).all()
    return {'data': [{'key': r.key, 'value': r.value, 'remark': r.remark} for r in rows]}


@app.put('/api/system/config')
def put_config(item: ConfigItem, db: Session = Depends(get_db), _: bool = Depends(require_admin_or_key)):
    key = item.key.strip()
    if not key or len(key) > 100:
        raise HTTPException(status_code=422, detail="配置键非法")
    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if row:
        row.value, row.remark = item.value, item.remark
    else:
        db.add(SystemConfig(key=key, value=item.value, remark=item.remark))
    db.commit()
    return {'message': '保存成功', 'key': key}


UPLOAD_DIR = os.path.join(BACKUP_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


@app.post('/api/upload')
async def upload_file(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db),
                      _who: bool = Depends(require_admin_or_key)):
    filename = _safe_backup_filename(file.filename)
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件超限（最大100MB）")
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, 'wb') as f:
        f.write(content)
    session = get_session(request)
    row = UploadFileRecord(filename=filename, path=path, size=len(content),
                           uploader=(session or {}).get("username", "api-key"))
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'message': '上传成功', 'id': row.id, 'filename': filename, 'size': len(content)}


@app.get('/api/upload/list')
def list_uploads(limit: int = 100, offset: int = 0, db: Session = Depends(get_db), _: bool = Depends(verify_api_key)):
    q = db.query(UploadFileRecord).order_by(UploadFileRecord.id.desc())
    total = q.count()
    rows = q.offset(max(offset, 0)).limit(min(max(limit, 1), 500)).all()
    return {'data': [{'id': r.id, 'filename': r.filename, 'size': r.size,
                      'uploader': r.uploader} for r in rows], 'total': total}


@app.get('/api/audit/logs')
def audit_logs(limit: int = 100, offset: int = 0, request: Request = None, db: Session = Depends(get_db),
               _: dict = Depends(require_login)):
    q = db.query(AuditLog).order_by(AuditLog.id.desc())
    total = q.count()
    rows = q.offset(max(offset, 0)).limit(min(max(limit, 1), 500)).all()
    return {'data': [{'id': r.id, 'username': r.username, 'ip': r.ip, 'method': r.method,
                      'path': r.path, 'status': r.status_code} for r in rows], 'total': total}


def _bot_dir() -> str:
    # 机器人目录定位（与启动逻辑同源）
    env_dir = os.getenv("BOT_WORKDIR", "")
    if env_dir and os.path.isdir(env_dir):
        return env_dir
    here = os.path.dirname(os.path.abspath(__file__))
    for c in (os.path.join(here, "..", "bot"), os.path.join(os.getcwd(), "bot")):
        if os.path.isdir(c):
            return os.path.normpath(c)
    return ""


@app.get('/api/bot/log')
def bot_log(num: int = 200, request: Request = None, _: dict = Depends(require_login)):
    num = min(max(num, 1), 2000)
    content = []
    d = _bot_dir()
    for name in ("bot.log", "bot-err.log"):
        p = os.path.join(d, name) if d else ""
        if p and os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    content.extend(f.readlines()[-num:])
            except Exception:
                pass
    if not content:
        return {'log': '（暂无日志，Bot 尚未启动过）'}
    return {'log': "".join(content[-num:])}


def _bot_env_file() -> str:
    d = _bot_dir()
    return os.path.join(d, ".env") if d else ""


def _read_bot_token() -> str:
    env_file = _bot_env_file()
    if not env_file or not os.path.isfile(env_file):
        return ""
    for line in open(env_file, encoding="utf-8", errors="replace"):
        line = line.strip()
        if line.startswith("BOT_TOKEN="):
            return line[len("BOT_TOKEN="):].strip()
    return ""


def _mask_token(token: str) -> str:
    if not token:
        return "（未配置）"
    if len(token) <= 12:
        return token[:3] + "****"
    return token[:4] + "****" + token[-4:] + f"（共{len(token)}位）"


@app.get('/api/bot/token')
def bot_token_info(request: Request = None, _: bool = Depends(require_admin_or_key)):
    token = _read_bot_token()
    return {'configured': token != '', 'masked': _mask_token(token), 'length': len(token),
            'env_exists': bool(_bot_env_file() and os.path.isfile(_bot_env_file()))}


class TokenSave(BaseModel):
    token: str


class TokenTest(BaseModel):
    token: str = ""


@app.put('/api/bot/token')
def bot_token_save(body: TokenSave, _: bool = Depends(require_admin_or_key)):
    token = body.token.strip()
    if not re.match(r'^\d+:[\w\-]{30,}$', token):
        raise HTTPException(status_code=422, detail="TOKEN格式不正确（数字ID+冒号+密钥）")
    env_file = _bot_env_file()
    if not env_file:
        raise HTTPException(status_code=500, detail="未找到机器人目录")
    raw = open(env_file, "rb").read() if os.path.isfile(env_file) else b""
    crlf = b"\r\n" in raw
    if raw:
        try:
            import shutil
            shutil.copy(env_file, env_file + ".bak")
        except Exception:
            pass
        content = raw.decode("utf-8", errors="replace")
        if re.search(r'^BOT_TOKEN=.*$', content, re.M):
            content = re.sub(r'^BOT_TOKEN=.*$', f'BOT_TOKEN={token}', content, flags=re.M)
        else:
            content = content.rstrip("\r\n") + f"\nBOT_TOKEN={token}\n"
    else:
        content = f"BOT_TOKEN={token}\n"
    if crlf:
        content = content.replace("\n", "\r\n")
    with open(env_file, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    return {'message': 'TOKEN已保存，重启Bot后生效'}


@app.post('/api/bot/token/test')
async def bot_token_test(body: TokenTest, _: bool = Depends(require_admin_or_key)):
    token = body.token.strip() or _read_bot_token()
    if not token:
        raise HTTPException(status_code=400, detail="未配置TOKEN")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"连接Telegram失败：{e}")
    if not data.get("ok"):
        raise HTTPException(status_code=422, detail=data.get("description", "TOKEN无效"))
    r = data["result"]
    return {'id': r.get("id"), 'username': "@" + r.get("username", ""),
            'first_name': r.get("first_name", "")}


@app.delete('/api/backup/{name}')
def delete_backup(name: str, _: bool = Depends(require_admin_or_key)):
    filename = _safe_backup_filename(name)
    if filename.startswith(".") or filename.endswith(".db"):
        raise HTTPException(status_code=400, detail="该文件不允许删除")
    path = os.path.join(BACKUP_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="文件不存在")
    os.remove(path)
    return {'message': '删除成功', 'filename': filename}


class PhoneUpdate(BaseModel):
    status: str


@app.put('/api/phone/{phone_id}')
def update_phone(phone_id: int, body: PhoneUpdate, db: Session = Depends(get_db), _: bool = Depends(verify_api_key)):
    if body.status not in ("generated", "valid", "invalid"):
        raise HTTPException(status_code=422, detail="状态非法")
    row = db.query(PhoneNumber).filter(PhoneNumber.id == phone_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="号码不存在")
    row.status = body.status
    row.is_valid = (body.status == "valid")
    db.commit()
    return {'message': '更新成功', 'id': phone_id, 'status': body.status}


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "operator"


class UserUpdate(BaseModel):
    password: str = None
    role: str = None
    status: int = None


def _user_to_dict(u: AdminUser) -> dict:
    return {"id": u.id, "username": u.username, "role": u.role,
            "status": u.status, "login_num": u.login_num}


@app.get('/api/users')
def list_users(request: Request = None, db: Session = Depends(get_db), _: bool = Depends(require_admin_or_key)):
    rows = db.query(AdminUser).order_by(AdminUser.id).all()
    return {'data': [_user_to_dict(u) for u in rows], 'env_admin': ADMIN_USERNAME}


@app.post('/api/users')
def create_user(body: UserCreate, db: Session = Depends(get_db), _: bool = Depends(require_admin_or_key)):
    username = body.username.strip()
    if not username or len(username) > 50:
        raise HTTPException(status_code=422, detail="用户名非法")
    if not body.password or len(body.password) < 6:
        raise HTTPException(status_code=422, detail="密码至少6位")
    if body.role not in ("admin", "operator"):
        raise HTTPException(status_code=422, detail="角色非法")
    if username == ADMIN_USERNAME or db.query(AdminUser).filter(AdminUser.username == username).first():
        raise HTTPException(status_code=409, detail="用户名已存在")
    row = AdminUser(username=username, password_hash=PasswordManager.hash_password(body.password), role=body.role)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'message': '创建成功', 'data': _user_to_dict(row)}


@app.put('/api/users/{uid}')
def update_user(uid: int, body: UserUpdate, request: Request, db: Session = Depends(get_db),
                _: bool = Depends(require_admin_or_key)):
    row = db.query(AdminUser).filter(AdminUser.id == uid).first()
    if not row:
        raise HTTPException(status_code=404, detail="账号不存在")
    me = (get_session(request) or {}).get("username", "")
    if body.role is not None:
        if body.role not in ("admin", "operator"):
            raise HTTPException(status_code=422, detail="角色非法")
        if row.username == me and body.role != "admin":
            raise HTTPException(status_code=400, detail="不能降级自己的管理员权限")
        row.role = body.role
    if body.status is not None:
        if body.status not in (0, 1):
            raise HTTPException(status_code=422, detail="状态非法")
        if row.username == me and body.status == 0:
            raise HTTPException(status_code=400, detail="不能禁用自己")
        row.status = body.status
    if body.password:
        if len(body.password) < 6:
            raise HTTPException(status_code=422, detail="密码至少6位")
        row.password_hash = PasswordManager.hash_password(body.password)
    db.commit()
    return {'message': '更新成功', 'data': _user_to_dict(row)}


class CateIn(BaseModel):
    title: str
    sort: int = 0
    status: int = 1


class GoodsIn(BaseModel):
    cate_id: int = 0
    title: str
    price: float = 0.0
    stock: int = 0
    status: int = 1


@app.get('/api/mall/cate')
def list_cate(db: Session = Depends(get_db), _: bool = Depends(verify_api_key)):
    rows = db.query(MallCate).order_by(MallCate.sort, MallCate.id).all()
    return {'data': [{'id': r.id, 'title': r.title, 'sort': r.sort, 'status': r.status} for r in rows]}


@app.post('/api/mall/cate')
def add_cate(body: CateIn, db: Session = Depends(get_db), _: bool = Depends(require_admin_or_key)):
    if not body.title.strip():
        raise HTTPException(status_code=422, detail="分类名不能为空")
    row = MallCate(title=body.title.strip(), sort=body.sort, status=body.status)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="分类已存在")
    db.refresh(row)
    return {'message': '创建成功', 'id': row.id}


@app.delete('/api/mall/cate/{cid}')
def del_cate(cid: int, db: Session = Depends(get_db), _: bool = Depends(require_admin_or_key)):
    row = db.query(MallCate).filter(MallCate.id == cid).first()
    if not row:
        raise HTTPException(status_code=404, detail="分类不存在")
    db.delete(row)
    db.commit()
    return {'message': '删除成功'}


@app.get('/api/mall/goods')
def list_goods(db: Session = Depends(get_db), _: bool = Depends(verify_api_key)):
    rows = db.query(MallGoods).order_by(MallGoods.id.desc()).all()
    return {'data': [{'id': r.id, 'cate_id': r.cate_id, 'title': r.title,
                      'price': r.price, 'stock': r.stock, 'status': r.status} for r in rows]}


@app.post('/api/mall/goods')
def add_goods(body: GoodsIn, db: Session = Depends(get_db), _: bool = Depends(require_admin_or_key)):
    if not body.title.strip():
        raise HTTPException(status_code=422, detail="商品名不能为空")
    row = MallGoods(cate_id=body.cate_id, title=body.title.strip(),
                    price=body.price, stock=body.stock, status=body.status)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'message': '创建成功', 'id': row.id}


@app.delete('/api/mall/goods/{gid}')
def del_goods(gid: int, db: Session = Depends(get_db), _: bool = Depends(require_admin_or_key)):
    row = db.query(MallGoods).filter(MallGoods.id == gid).first()
    if not row:
        raise HTTPException(status_code=404, detail="商品不存在")
    db.delete(row)
    db.commit()
    return {'message': '删除成功'}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)