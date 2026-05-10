# coding=utf-8
import json
import os
import logging
import hashlib
import secrets
import subprocess

from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Depends, Request
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="TeleBot API")
BACKUP_DIR = '/backups'
os.makedirs(BACKUP_DIR, exist_ok=True)

API_KEY = os.getenv("API_KEY")
ENABLE_AUTH = os.getenv("ENABLE_AUTH", "false").lower() == "true"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))

phone_numbers_db = []
sms_records_db = []
sessions = {}

# Bot process reference
bot_process = None

def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if not ENABLE_AUTH:
        return True
    if not API_KEY:
        logger.warning("API_KEY未配置，已禁用认证")
        return True
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True

def get_session(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        return sessions[session_id]
    return None

def require_login(request: Request):
    session = get_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session

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
  <a href="/api/phone/generate" class="btn" target="_blank">🔧 测试生成</a>
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
def login_page(request: Request):
    session = get_session(request)
    if session:
        return HTMLResponse(ADMIN_HOME.replace('{{phone_count}}', str(len(phone_numbers_db))).replace('{{sms_count}}', str(len(sms_records_db))))
    return HTMLResponse(LOGIN_PAGE)

@app.post('/admin/login', response_class=HTMLResponse)
def login(request: Request, login_req: LoginRequest):
    if login_req.username == ADMIN_USERNAME and hash_password(login_req.password) == hash_password(ADMIN_PASSWORD):
        session_id = secrets.token_hex(16)
        sessions[session_id] = {'username': ADMIN_USERNAME}
        response = HTMLResponse(ADMIN_HOME.replace('{{phone_count}}', str(len(phone_numbers_db))).replace('{{sms_count}}', str(len(sms_records_db))))
        response.set_cookie('session_id', session_id, httponly=True, max_age=86400)
        return response
    return HTMLResponse(LOGIN_PAGE + "<script>alert('用户名或密码错误')</script>")

@app.get('/admin/logout')
def logout(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        del sessions[session_id]
    response = HTMLResponse(status_code=302)
    response.delete_cookie("session_id")
    response.headers["Location"] = "/admin/login"
    return response

@app.get('/admin/', response_class=HTMLResponse)
def admin_home(request: Request):
    require_login(request)
    return HTMLResponse(ADMIN_HOME.replace('{{phone_count}}', str(len(phone_numbers_db))).replace('{{sms_count}}', str(len(sms_records_db))))

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
    path = os.path.join(BACKUP_DIR, file.filename)
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
def generate_phone(request: PhoneGenerateRequest, _: bool = Depends(verify_api_key)):
    count = min(max(request.count, 1), 100)
    generated = []
    for i in range(count):
        phone_id = len(phone_numbers_db) + i + 1
        phone = generate_hk_number()
        phone_numbers_db.append({
            'id': phone_id, 'number': phone, 'country': 'HK',
            'status': 'generated', 'is_valid': False
        })
        generated.append({'id': phone_id, 'number': phone, 'country': 'HK', 'status': 'generated'})
    logger.info(f"生成号码数量: {len(generated)}")
    return {'message': '生成成功', 'data': generated, 'count': len(generated)}

@app.post('/api/phone/validate')
def validate_phone(request: ValidatePhoneRequest, _: bool = Depends(verify_api_key)):
    results = []
    for num in request.numbers:
        is_valid = len(num) == 11 and num.startswith('+852') and num[3] in '569'
        results.append({'number': num, 'is_valid': is_valid, 'status': 'valid' if is_valid else 'invalid'})
    return {'data': results}

@app.get('/api/phone/list')
def list_phones(status: Optional[str] = None):
    phones = phone_numbers_db
    if status:
        phones = [p for p in phones if p['status'] == status]
    return {'data': phones, 'total': len(phones)}

@app.post('/api/sms/send')
def send_sms(request: SendSMSRequest, _: bool = Depends(verify_api_key)):
    phone = request.phone
    if len(phone) == 9:
        phone = f"+852{phone}"
    logger.info(f"[SMS] 发送到 {phone}: {request.content}")
    sms_id = len(sms_records_db) + 1
    sms_records_db.append({
        'id': sms_id, 'phone': phone, 'content': request.content,
        'sender': request.sender, 'status': 'sent'
    })
    return {'message': '发送成功', 'sms_id': sms_id, 'phone': phone, 'status': 'sent'}

@app.get('/api/sms/list')
def list_sms():
    return {'data': sms_records_db, 'total': len(sms_records_db)}

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
        # Assuming bot is located at /workspace/bot/bot.py and we are in /workspace
        bot_process = subprocess.Popen(['python', 'bot/bot.py'], cwd='/workspace')
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