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
<h2>机器人凭证（三件套）</h2>
<p style="font-family:monospace;font-size:13px;color:#555;margin-bottom:8px;">TOKEN: <span id="token-masked">--</span></p>
<p style="font-family:monospace;font-size:13px;color:#555;margin-bottom:8px;">API_ID: <span id="env-api-id">--</span> · HASH: <span id="env-api-hash">--</span></p>
<input id="token-input" type="password" placeholder="新BOT_TOKEN（空=不改）" style="width:100%;padding:10px;border:1px solid #e5e7eb;border-radius:6px;margin-bottom:8px;">
<input id="env-api-id-input" placeholder="新API_ID（空=不改）" style="width:100%;padding:10px;border:1px solid #e5e7eb;border-radius:6px;margin-bottom:8px;">
<input id="env-api-hash-input" type="password" placeholder="新API_HASH（空=不改）" style="width:100%;padding:10px;border:1px solid #e5e7eb;border-radius:6px;margin-bottom:8px;">
<div>
<button class="btn" onclick="envSave()">保存全部</button>
<button class="btn btn-gray" onclick="tokenTest()">测试链接</button>
</div>
<p id="token-result" style="font-family:monospace;font-size:13px;color:#555;margin-top:8px;word-break:break-all;"></p>
</div>
<div class="card">
<h2>运行日志（最新200行）</h2>
<pre id="botlog">加载中...</pre>
</div>
</div>
<script>
async function errText(r){ const d = (r && r.data) || {}; return d.message || d.detail || JSON.stringify(d); }
async function envLoad(){
  const r = await fetch('/api/bot/env'); const d = await r.json();
  document.getElementById('token-masked').textContent = d.bot_token_masked || d.detail || '--';
  document.getElementById('env-api-id').textContent = d.api_id || '（未配置）';
  document.getElementById('env-api-hash').textContent = d.api_hash_masked || '（未配置）';
}
async function envSave(){
  const body = {bot_token: document.getElementById('token-input').value.trim(),
    api_id: document.getElementById('env-api-id-input').value.trim(),
    api_hash: document.getElementById('env-api-hash-input').value.trim()};
  const r = await fetch('/api/bot/env', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const d = await r.json();
  document.getElementById('token-result').textContent = errText({data:d});
  if (r.status === 200) { document.getElementById('token-input').value = ''; document.getElementById('env-api-id-input').value = ''; document.getElementById('env-api-hash-input').value = ''; }
  envLoad(); botRefresh();
}
async function tokenTest(){
  const token = document.getElementById('token-input').value.trim();
  const r = await fetch('/api/bot/token/test', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({token})});
  const d = await r.json();
  document.getElementById('token-result').textContent = r.status===200 ? ('连通: '+d.username) : ('失败: '+errText({data:d}));
}
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
<div class="card">
<h2>导入号码（一行一个）</h2>
<textarea id="imp-numbers" rows="4" placeholder="+85251234567"></textarea>
<button class="btn" onclick="toolImport()">导入</button>
<div id="imp-result" class="result">尚未导入</div>
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
async function toolImport(){
  const nums = document.getElementById('imp-numbers').value.split('\\n').map(s=>s.trim()).filter(Boolean);
  if(!nums.length){ alert('请先填写号码'); return; }
  const r = await jpost('/api/phone/import', {numbers:nums});
  document.getElementById('imp-result').textContent =
    r.status === 200 ? ('新增'+r.data.imported+'，重复'+r.data.skipped_dup+'，非法'+r.data.skipped_invalid.length) : ('失败：'+JSON.stringify(r.data));
}
</script>
</body>
</html>"""

html_convert = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>转换测试 - Telegram 后台</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f5f5}
.header{background:linear-gradient(135deg,#0ea5e9 0%,#1e40af 100%);color:white;padding:20px}
h1{font-size:24px}
.container{max-width:1000px;margin:20px auto;padding:0 20px}
.card{background:white;border-radius:12px;padding:24px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,0.1)}
.btn{display:inline-block;padding:10px 20px;background:#0ea5e9;color:white;border:none;border-radius:6px;cursor:pointer;font-size:14px}
.btn:hover{background:#0284c7}
textarea{width:100%;padding:10px;border:1px solid #e5e7eb;border-radius:6px;font-size:14px;margin-bottom:10px}
.result{font-family:monospace;font-size:13px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;padding:10px;margin-top:10px;white-space:pre-wrap;word-break:break-all}
.result a{color:#0ea5e9}
</style>
</head>
<body>
<div class="header"><h1>🔄 转换测试（session→tdata）</h1></div>
<div class="container">
<div class="card">
<p style="color:#666;margin-bottom:10px;">粘贴 telethon session 字符串（见备份文件夹 telethon密钥.txt），转换成功后点下载拿包，解压出 tdata 拷到电脑版目录即登录。</p>
<textarea id="conv-session" rows="4" placeholder="telethon session 字符串"></textarea>
<button class="btn" onclick="convGo()">测试转换</button>
<div id="conv-result" class="result">尚未测试</div>
</div>
</div>
<script>
async function convGo(){
  const el = document.getElementById('conv-result');
  el.textContent = '转换中...';
  try {
    const r = await fetch('/to-tdata', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({backup:{data:document.getElementById('conv-session').value, format:'telethon_session'}, options:{}})});
    const d = await r.json();
    if (d.file) {
      el.innerHTML = '转换成功：' + d.file + ' <a href="' + d.download + '">点此下载</a>';
    } else {
      el.textContent = JSON.stringify(d).slice(0, 300);
    }
  } catch(e){ el.textContent = '失败：' + e; }
}
</script>
</body>
</html>"""

html_system = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>系统管理 - Telegram 后台</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f5f5}
.header{background:linear-gradient(135deg,#7c3aed 0%,#4c1d95 100%);color:white;padding:20px}
h1{font-size:24px}
.container{max-width:1200px;margin:20px auto;padding:0 20px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
.card{background:white;border-radius:12px;padding:24px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,0.1)}
.card h2{margin-bottom:14px}
.btn{display:inline-block;padding:8px 18px;background:#7c3aed;color:white;border:none;border-radius:6px;cursor:pointer;font-size:14px;margin-right:8px}
.btn:hover{background:#6d28d9}
.btn-gray{background:#6b7280}.btn-gray:hover{background:#4b5563}
input{width:100%;padding:10px;border:1px solid #e5e7eb;border-radius:6px;font-size:14px;margin-bottom:10px}
.list{font-family:monospace;font-size:13px;max-height:260px;overflow:auto;margin-bottom:10px}
.list div{padding:4px 0;border-bottom:1px solid #f3f4f6}
pre{background:#111827;color:#d1d5db;padding:12px;border-radius:8px;max-height:300px;overflow:auto;font-size:12px}
</style>
</head>
<body>
<div class="header"><h1>⚙️ 系统管理</h1></div>
<div class="container">
<div class="grid">
<div class="card"><h2>系统配置</h2><div id="cfg-list" class="list"></div>
<input id="cfg-key" placeholder="键"><input id="cfg-value" placeholder="值">
<button class="btn" onclick="cfgSave()">保存</button><button class="btn btn-gray" onclick="cfgLoad()">刷新</button></div>
<div class="card"><h2>文件上传</h2><input id="up-file" type="file">
<button class="btn" onclick="upGo()">上传</button><div id="up-list" class="list" style="margin-top:10px;"></div></div>
</div>
<div class="grid">
<div class="card"><h2>账号管理</h2><div id="user-list" class="list"></div>
<input id="user-name" placeholder="用户名"><input id="user-pass" type="password" placeholder="密码（≥6位）">
<button class="btn" onclick="userAdd('operator')">建操作员</button><button class="btn btn-gray" onclick="userAdd('admin')">建管理员</button></div>
<div class="card"><h2>操作审计（最新50条）</h2><div id="audit-list" class="list"></div>
<button class="btn btn-gray" onclick="auditLoad()">刷新</button></div>
</div>
</div>
<script>
async function jget(u){ const r = await fetch(u); return r.json(); }
async function cfgLoad(){
  const d = await jget('/api/system/config');
  document.getElementById('cfg-list').innerHTML = (d.data||[]).map(c=>'<div>'+c.key+' = '+(c.value||'').slice(0,50)+'</div>').join('') || '暂无';
}
async function cfgSave(){
  const r = await fetch('/api/system/config', {method:'PUT', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({key:document.getElementById('cfg-key').value.trim(), value:document.getElementById('cfg-value').value})});
  alert((await r.json()).message || '完成'); cfgLoad();
}
async function upGo(){
  const f = document.getElementById('up-file').files[0];
  if(!f){ alert('请选择文件'); return; }
  const fd = new FormData(); fd.append('file', f);
  const r = await fetch('/api/upload', {method:'POST', body:fd});
  alert((await r.json()).message || '完成'); upLoad();
}
async function upLoad(){
  const d = await jget('/api/upload/list?limit=50');
  document.getElementById('up-list').innerHTML = (d.data||[]).map(x=>'<div>'+x.filename+' ('+x.size+'B)</div>').join('') || '暂无';
}
async function userLoad(){
  const d = await jget('/api/users');
  if(!d.data){ document.getElementById('user-list').innerHTML = '需管理员登录'; return; }
  document.getElementById('user-list').innerHTML = d.data.map(u=>'<div>'+u.username+' ['+u.role+'] '+(u.status?'启用':'禁用')+
    ' <a href="javascript:userToggle('+u.id+','+(u.status?0:1)+')">启/禁</a>'+
    ' <a href="javascript:userPwd('+u.id+')">改密</a></div>').join('') || '暂无';
}
async function userAdd(role){
  const r = await fetch('/api/users', {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({username:document.getElementById('user-name').value.trim(), password:document.getElementById('user-pass').value, role})});
  alert((await r.json()).message || '完成'); userLoad();
}
async function userToggle(id, status){
  const r = await fetch('/api/users/'+id, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status})});
  alert((await r.json()).message || '完成'); userLoad();
}
async function userPwd(id){
  const p = prompt('输入新密码（≥6位）:'); if(!p) return;
  const r = await fetch('/api/users/'+id, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({password:p})});
  alert((await r.json()).message || '完成');
}
async function auditLoad(){
  const d = await jget('/api/audit/logs?limit=50');
  if(!d.data){ document.getElementById('audit-list').innerHTML = '需登录查看'; return; }
  document.getElementById('audit-list').innerHTML = d.data.map(a=>'<div>['+a.method+'] '+a.path+' → '+a.status+' '+a.username+'</div>').join('') || '暂无';
}
cfgLoad(); upLoad(); userLoad(); auditLoad();
</script>
</body>
</html>"""

html_mall = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>商城 - Telegram 后台</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f5f5}
.header{background:linear-gradient(135deg,#f59e0b 0%,#b45309 100%);color:white;padding:20px}
h1{font-size:24px}
.container{max-width:1200px;margin:20px auto;padding:0 20px}
.grid{display:grid;grid-template-columns:1fr 2fr;gap:20px}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
.card{background:white;border-radius:12px;padding:24px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,0.1)}
.card h2{margin-bottom:14px}
.btn{display:inline-block;padding:8px 18px;background:#f59e0b;color:white;border:none;border-radius:6px;cursor:pointer;font-size:14px;margin-right:8px}
.btn:hover{background:#d97706}
.btn-danger{background:#ef4444}.btn-danger:hover{background:#dc2626}
input{width:100%;padding:10px;border:1px solid #e5e7eb;border-radius:6px;font-size:14px;margin-bottom:10px}
.list{font-family:monospace;font-size:13px;max-height:300px;overflow:auto;margin-bottom:10px}
.list div{padding:4px 0;border-bottom:1px solid #f3f4f6}
a.del{color:#dc2626;margin-left:8px}
</style>
</head>
<body>
<div class="header"><h1>🛍 商城</h1></div>
<div class="container">
<div class="grid">
<div class="card"><h2>分类</h2><div id="cate-list" class="list"></div>
<input id="cate-title" placeholder="新分类名"><button class="btn" onclick="cateAdd()">加分类</button></div>
<div class="card"><h2>商品</h2><div id="goods-list" class="list"></div>
<input id="goods-title" placeholder="商品名"><input id="goods-price" type="number" step="0.01" placeholder="价格">
<button class="btn" onclick="goodsAdd()">加商品</button></div>
</div>
</div>
<script>
async function jget(u){ const r = await fetch(u); return r.json(); }
async function jpost(u, b){
  const r = await fetch(u, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(b)});
  return {status:r.status, data:await r.json()};
}
async function mallLoad(){
  const c = await jget('/api/mall/cate');
  document.getElementById('cate-list').innerHTML = (c.data||[]).map(x=>'<div>['+x.id+'] '+x.title+'<a class="del" href="javascript:cateDel('+x.id+')">删</a></div>').join('') || '暂无';
  const g = await jget('/api/mall/goods');
  document.getElementById('goods-list').innerHTML = (g.data||[]).map(x=>'<div>['+x.id+'] '+x.title+' ¥'+x.price+' x'+x.stock+'<a class="del" href="javascript:goodsDel('+x.id+')">删</a></div>').join('') || '暂无';
}
async function cateAdd(){
  const t = document.getElementById('cate-title').value.trim(); if(!t) return;
  const r = await jpost('/api/mall/cate', {title:t});
  alert(r.data.message || r.data.detail || '完成'); mallLoad();
}
async function cateDel(id){ if(!confirm('删除分类'+id+'？')) return; await fetch('/api/mall/cate/'+id, {method:'DELETE'}); mallLoad(); }
async function goodsAdd(){
  const t = document.getElementById('goods-title').value.trim(); if(!t) return;
  const r = await jpost('/api/mall/goods', {title:t, price:parseFloat(document.getElementById('goods-price').value)||0});
  alert(r.data.message || r.data.detail || '完成'); mallLoad();
}
async function goodsDel(id){ if(!confirm('删除商品'+id+'？')) return; await fetch('/api/mall/goods/'+id, {method:'DELETE'}); mallLoad(); }
mallLoad();
</script>
</body>
</html>"""

html_desktop = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>桌面切换 - Telegram 后台</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f5f5}
.header{background:linear-gradient(135deg,#0891b2 0%,#155e75 100%);color:white;padding:20px}
h1{font-size:24px}
.container{max-width:1000px;margin:20px auto;padding:0 20px}
.card{background:white;border-radius:12px;padding:24px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,0.1)}
.btn{display:inline-block;padding:8px 18px;background:#0891b2;color:white;border:none;border-radius:6px;cursor:pointer;font-size:14px}
.btn:hover{background:#0e7490}
.list{font-family:monospace;font-size:14px;margin-bottom:10px}
.list div{padding:8px 0;border-bottom:1px solid #f3f4f6}
a.go{color:#0891b2;margin-left:10px}
p.tip{color:#666;font-size:13px;margin-top:10px}
</style>
</head>
<body>
<div class="header"><h1>🖥 桌面多号切换（本机）</h1></div>
<div class="container">
<div class="card">
<div id="tg-list" class="list">加载中...</div>
<button class="btn" onclick="tgLoad()">刷新</button>
<p class="tip">切换自动备份当前上线号；完整tdata优先于转换包；仅本机有效。</p>
</div>
</div>
<script>
async function tgLoad(){
  const r = await fetch('/api/telegram/accounts'); const d = await r.json();
  if(!d.data){ document.getElementById('tg-list').innerHTML = '需登录查看'; return; }
  document.getElementById('tg-list').innerHTML = d.data.map(x=>'<div>'+x.phone+'（'+(x.tdata==='full'?'完整':x.tdata==='zip'?'转换包':'无数据')+'）'+
    (x.tdata?'<a class="go" href="#" data-p="'+x.phone+'" onclick="tgSwitch(this.dataset.p);return false;">切换上线</a>':'')+'</div>').join('') || '暂无号码';
}
async function tgSwitch(phone){
  if(!confirm('切换到 '+phone+'？当前客户端将被替换（已自动备份）。')) return;
  const r = await fetch('/api/telegram/switch', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({phone})});
  alert((await r.json()).message || '完成'); tgLoad();
}
tgLoad();
</script>
</body>
</html>"""
