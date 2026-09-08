# coding=utf-8
"""BOT控制台 + 生成验证单页模板"""
# flake8: noqa - 内嵌前端模板

html_bot = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>BOT控制台 - Telegram 后台</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f5f5}
.header{background:linear-gradient(135deg,#16a34a 0%,#065f46 100%);color:white;padding:20px}
h1{font-size:24px}
.container{max-width:1000px;margin:20px auto;padding:0 20px}
.card{background:white;border-radius:12px;padding:24px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,0.1)}
.btn{display:inline-block;padding:10px 20px;background:#16a34a;color:white;border:none;border-radius:6px;cursor:pointer;font-size:14px;margin-right:8px}
.btn:hover{background:#15803d}
.btn-danger{background:#ef4444}.btn-danger:hover{background:#dc2626}
.btn-gray{background:#6b7280}.btn-gray:hover{background:#4b5563}
.dot{font-size:20px}
pre#botlog{background:#111827;color:#d1d5db;padding:12px;border-radius:8px;max-height:420px;overflow:auto;font-size:12px}
.status-line{font-size:16px;margin-bottom:12px}
</style>
</head>
<body>
<div class="header"><h1>🤖 BOT控制台</h1></div>
<div class="container">
<div class="card">
<div class="status-line"><span id="dot" class="dot">⚪</span> <span id="stext">查询中...</span></div>
<div>
<button class="btn" onclick="botStart()">启动 Bot</button>
<button class="btn btn-danger" onclick="botStop()">停止 Bot</button>
<button class="btn btn-gray" onclick="botRefresh()">刷新状态</button>
</div>
</div>
<div class="card">
<h2>运行日志（最新200行）</h2>
<pre id="botlog">加载中...</pre>
</div>
</div>
<script>
async function botRefresh(){
  try {
    const s = await (await fetch('/api/bot/status')).json();
    const run = s.status === 'running';
    document.getElementById('dot').textContent = run ? '🟢' : '🔴';
    document.getElementById('stext').textContent = run ? 'Bot 运行中' : 'Bot 未运行';
    const l = await (await fetch('/api/bot/log?num=200')).json();
    document.getElementById('botlog').textContent = l.log || JSON.stringify(l);
  } catch(e){ document.getElementById('stext').textContent = '查询失败：' + e; }
}
async function botStart(){
  if(!confirm('确认启动 Bot？')) return;
  const r = await (await fetch('/api/bot/start', {method:'POST'})).json();
  alert(r.message || JSON.stringify(r)); setTimeout(botRefresh, 3000);
}
async function botStop(){
  if(!confirm('确认停止 Bot？')) return;
  const r = await (await fetch('/api/bot/stop', {method:'POST'})).json();
  alert(r.message || JSON.stringify(r)); botRefresh();
}
botRefresh();
</script>
</body>
</html>"""

html_phone_tool = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>生成验证号码 - Telegram 后台</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f5f5}
.header{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;padding:20px}
h1{font-size:24px}
.container{max-width:1000px;margin:20px auto;padding:0 20px}
.card{background:white;border-radius:12px;padding:24px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,0.1)}
.card h2{margin-bottom:14px}
.btn{display:inline-block;padding:10px 20px;background:#667eea;color:white;border:none;border-radius:6px;cursor:pointer;font-size:14px}
.btn:hover{background:#5568d3}
input,textarea{width:100%;padding:10px;border:1px solid #e5e7eb;border-radius:6px;font-size:14px;margin-bottom:10px}
.result{font-family:monospace;font-size:13px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;padding:10px;margin-top:10px;white-space:pre-wrap;word-break:break-all;max-height:260px;overflow:auto}
</style>
</head>
<body>
<div class="header"><h1>📱 生成号码 / 验证号码</h1></div>
<div class="container">
<div class="card">
<h2>生成香港号码</h2>
<input id="gen-count" type="number" value="10" min="1" max="100">
<button class="btn" onclick="toolGenerate()">生成</button>
<div id="gen-result" class="result">尚未生成</div>
</div>
<div class="card">
<h2>验证号码（一行一个）</h2>
<textarea id="val-numbers" rows="4" placeholder="+85251234567"></textarea>
<button class="btn" onclick="toolValidate()">验证</button>
<div id="val-result" class="result">尚未验证</div>
</div>
</div>
<script>
async function jpost(url, body){
  try {
    const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    let d = {};
    try { d = await r.json(); } catch(e){ d = {detail:'非JSON响应'}; }
    return {status:r.status, data:d};
  } catch(e){ return {status:0, data:{detail:'网络不通：'+e}}; }
}
async function toolGenerate(){
  const n = parseInt(document.getElementById('gen-count').value) || 10;
  const r = await jpost('/api/phone/generate', {count:n});
  document.getElementById('gen-result').textContent =
    r.status === 200 ? ('生成'+r.data.count+'个：\\n' + r.data.data.map(x=>x.number).join('\\n')) : ('失败：'+JSON.stringify(r.data));
}
async function toolValidate(){
  const nums = document.getElementById('val-numbers').value.split('\\n').map(s=>s.trim()).filter(Boolean);
  if(!nums.length){ alert('请先填写号码'); return; }
  const r = await jpost('/api/phone/validate', {numbers:nums});
  document.getElementById('val-result').textContent =
    r.status === 200 ? r.data.data.map(x=>x.number+' → '+(x.is_valid?'✅有效':'❌无效')).join('\\n') : ('失败：'+JSON.stringify(r.data));
}
</script>
</body>
</html>"""
