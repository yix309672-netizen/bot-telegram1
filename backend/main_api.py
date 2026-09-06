# coding=utf-8
import json
import os
import sys
import logging
import hashlib
import secrets
import subprocess
from datetime import timedelta

from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

if __package__ in (None, ""):
    # 目录方式运行（Docker WORKDIR /app 内 uvicorn main_api:app）
    from core.database import get_db, init_db, PhoneNumber, SmsRecord, AuditLog, SessionLocal
    from core.jwt_manager import JWTManager
    from core.cache import cache
    from core.security import SecurityUtils
    from core.crypto import PasswordManager
else:
    # 包方式运行（pytest / uvicorn backend.main_api:app）
    from .core.database import get_db, init_db, PhoneNumber, SmsRecord, AuditLog, SessionLocal
    from .core.jwt_manager import JWTManager
    from .core.cache import cache
    from .core.security import SecurityUtils
    from .core.crypto import PasswordManager

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
        return {"user_id": payload.get("sub"), "username": payload.get("username")}
    except Exception:
        return None

def require_login(request: Request):
    session = get_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session


def _db_counts(db: Session):
    # 后台首页统计走数据库实时查询
    phone_count = db.query(PhoneNumber).count()
    sms_count = db.query(SmsRecord).count()
    return phone_count, sms_count


def _phone_to_dict(p: PhoneNumber) -> dict:
    return {"id": p.id, "number": p.number, "country": p.country,
            "status": p.status, "is_valid": p.is_valid}


def _sms_to_dict(s: SmsRecord) -> dict:
    return {"id": s.id, "phone": s.phone, "content": s.content,
            "sender": s.sender, "status": s.status}

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

ADMIN_HOME = HTML_TEMPLATE.replace("{% block content %}{% endblock %}", """
<div class="stats">
  <div class="stat-card">
    <div class="num">{{ phone_count }}</div>
    <div>📱 号码总数</div>
  </div>
  <div class="stat-card">
    <div class="num">{{ sms_count }}</div>
    <div>💬 短信总数</div>
  </div>
</div>
<div class="card">
  <h2>快速操作</h2>
  <a href="/admin/phones" class="btn">📱 号码管理</a>
  <a href="/admin/sms" class="btn">💬 短信记录</a>
  <button class="btn" onclick="fetch('/api/phone/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({count:1})}).then(r=>r.json()).then(d=>alert('生成成功：'+(d.data[0]?d.data[0].number:'')))">🔧 测试生成</button>
</div>
""")

PHONES_PAGE = HTML_TEMPLATE.replace("{% block content %}{% endblock %}", """
<div class="card">
  <h2>📱 号码管理</h2>
  <div style="margin-bottom:15px">
    <button class="btn" onclick="generatePhones()">➕ 生成号码</button>
    <button class="btn" onclick="location.reload()">🔄 刷新</button>
  </div>
  <table>
    <thead><tr><th>ID</th><th>号码</th><th>地区</th><th>状态</th></tr></thead>
    <tbody id="tbody"></tbody>
  </table>
</div>
<script>
function loadPhones(){fetch('/api/phone/list').then(r=>r.json()).then(d=>{
  document.getElementById('tbody').innerHTML=d.data.map(p=>`<tr><td>${p.id}</td><td>${p.number}</td><td>${p.country||'HK'}</td><td>${p.status}</td></tr>`).join('')||'<tr><td colspan="4">暂无数据</td></tr>'
})}
function generatePhones(){fetch('/api/phone/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({count:10})}).then(r=>r.json()).then(d=>{alert('生成成功');loadPhones()})}
loadPhones();
</script>
""")

SMS_PAGE = HTML_TEMPLATE.replace("{% block content %}{% endblock %}", """
<div class="card">
  <h2>💬 短信记录</h2>
  <table>
    <thead><tr><th>ID</th><th>手机号</th><th>内容</th><th>发送者</th><th>状态</th></tr></thead>
    <tbody id="tbody"></tbody>
  </table>
</div>
<script>
fetch('/api/sms/list').then(r=>r.json()).then(d=>{
  document.getElementById('tbody').innerHTML=d.data.map(s=>`<tr><td>${s.id}</td><td>${s.phone}</td><td>${s.content}</td><td>${s.sender}</td><td>${s.status}</td></tr>`).join('')||'<tr><td colspan="5">暂无数据</td></tr>'
});
</script>
""")

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

@app.get('/api/', include_in_schema=False)
def api_root():
    return {
        'service': 'TeleBot API',
        'version': '1.0.0',
        'endpoints': [
            '/api/health',
            '/api/phone/list',
            '/api/phone/generate',
            '/api/phone/validate',
            '/api/sms/list',
            '/api/sms/send',
            '/api/backup/import',
            '/api/backup/import_json',
        ]
    }

@app.get('/admin/login', response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    session = get_session(request)
    if session:
        phone_count, sms_count = _db_counts(db)
        return HTMLResponse(ADMIN_HOME.replace('{{phone_count}}', str(phone_count)).replace('{{sms_count}}', str(sms_count)))
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
    if username == ADMIN_USERNAME and _verify_admin_password(password):
        _clear_login_fail(client_ip)
        token = jwt_manager.create_access_token(user_id=1, username=ADMIN_USERNAME, role="admin", expires_delta=timedelta(hours=12))
        phone_count, sms_count = _db_counts(db)
        response = HTMLResponse(ADMIN_HOME.replace('{{phone_count}}', str(phone_count)).replace('{{sms_count}}', str(sms_count)))
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
    phone_count, sms_count = _db_counts(db)
    return HTMLResponse(ADMIN_HOME.replace('{{phone_count}}', str(phone_count)).replace('{{sms_count}}', str(sms_count)))

@app.get('/admin/phones', response_class=HTMLResponse)
def admin_phones(request: Request):
    require_login(request)
    return HTMLResponse(PHONES_PAGE)

@app.get('/admin/sms', response_class=HTMLResponse)
def admin_sms(request: Request):
    require_login(request)
    return HTMLResponse(SMS_PAGE)

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
def delete_phone(phone_id: int, db: Session = Depends(get_db), _: bool = Depends(verify_api_key)):
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
def list_sms(limit: int = 200, offset: int = 0, db: Session = Depends(get_db), _: bool = Depends(verify_api_key)):
    limit = min(max(limit, 1), 1000)
    q = db.query(SmsRecord).order_by(SmsRecord.id.desc())
    total = q.count()
    rows = q.offset(max(offset, 0)).limit(limit).all()
    return {'data': [_sms_to_dict(s) for s in rows], 'total': total}

@app.get('/api/bot/status')
def get_bot_status():
    global bot_process
    is_running = False
    if bot_process is not None:
        if bot_process.poll() is None:
            is_running = True
    return {'status': 'running' if is_running else 'stopped'}

@app.post('/api/bot/start')
def start_bot():
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
def stop_bot():
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)