# coding=utf-8
"""统一实时监控台（样式改编自 joshhu/uitest #31 Real-time Monitoring，MIT 协议）
单页汇聚统一后端全部功能：指标/图表/日志流/服务健康 + 生成/验证/导入/短信/机器人/转换操作。
"""
# flake8: noqa - 内嵌前端模板

html_console = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TeleBot 实时监控台</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
.font-mono{font-family:'JetBrains Mono',monospace}
.font-sans{font-family:'Inter',sans-serif}
@keyframes pulse-green{0%,100%{opacity:1}50%{opacity:.5}}
.animate-pulse-green{animation:pulse-green 2s ease-in-out infinite}
.op-input{background:#030712;border:1px solid #1f2937;border-radius:.375rem;padding:.4rem .6rem;font-size:.8rem;width:100%;color:#e5e7eb}
.op-input:focus{outline:none;border-color:#16a34a}
.op-btn{background:#15803d;color:#fff;font-size:.8rem;padding:.4rem .8rem;border-radius:.375rem;cursor:pointer}
.op-btn:hover{background:#16a34a}
.op-btn.warn{background:#7c2d12}.op-btn.warn:hover{background:#9a3412}
.op-btn.gray{background:#1f2937;color:#d1d5db}.op-btn.gray:hover{background:#374151}
</style>
</head>
<body class="bg-gray-950 min-h-screen font-sans text-white">
<!-- 状态条 -->
<div id="statusbar" class="bg-green-600 text-white text-center py-1 text-sm font-medium">
<span class="inline-flex items-center gap-2">
<span class="w-2 h-2 bg-white rounded-full animate-pulse"></span>
<span id="statusbar-text">统一后端运行中</span>
</span>
</div>
<!-- 导航 -->
<nav class="bg-gray-900 border-b border-gray-800 px-4 py-3">
<div class="flex justify-between items-center flex-wrap gap-2">
<div class="flex items-center gap-4">
<a href="/admin/" class="text-gray-400 hover:text-white text-sm">&larr; 管理后台</a>
<span class="text-white font-semibold">TeleBot 实时监控台</span>
<a href="/admin/phones" class="text-gray-500 hover:text-white text-sm">号码</a>
<a href="/admin/sms" class="text-gray-500 hover:text-white text-sm">短信</a>
<a href="/admin/backups" class="text-gray-500 hover:text-white text-sm">备份</a>
</div>
<div class="flex items-center gap-4">
<span class="font-mono text-sm text-gray-400">同步: <span id="last-sync" class="text-green-400">--</span></span>
<button id="btn-pause" class="px-3 py-1 bg-gray-800 text-gray-300 rounded text-sm hover:bg-gray-700 cursor-pointer">暂停</button>
</div>
</div>
</nav>
<div class="p-4">
<!-- 指标卡 -->
<div class="grid grid-cols-5 gap-3 mb-4">
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800">
<div class="flex justify-between items-start mb-2"><span class="text-xs text-gray-500">号码总数</span><span class="w-2 h-2 bg-green-500 rounded-full animate-pulse-green"></span></div>
<p id="m-phones" class="text-3xl font-mono font-bold text-green-400">--</p>
<p class="text-xs text-gray-500 mt-2">有效 <span id="m-valid" class="text-white font-mono">--</span></p>
</div>
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800">
<div class="flex justify-between items-start mb-2"><span class="text-xs text-gray-500">短信总数</span><span class="w-2 h-2 bg-blue-500 rounded-full animate-pulse-green"></span></div>
<p id="m-sms" class="text-3xl font-mono font-bold text-blue-400">--</p>
<p class="text-xs text-gray-500 mt-2">状态 queued 入队</p>
</div>
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800">
<div class="flex justify-between items-start mb-2"><span class="text-xs text-gray-500">备份文件</span><span class="w-2 h-2 bg-yellow-500 rounded-full animate-pulse-green"></span></div>
<p id="m-backups" class="text-3xl font-mono font-bold text-yellow-400">--</p>
<p class="text-xs text-gray-500 mt-2"><a href="/admin/backups" class="hover:text-white">查看列表 &rarr;</a></p>
</div>
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800">
<div class="flex justify-between items-start mb-2"><span class="text-xs text-gray-500">审计事件</span><span class="w-2 h-2 bg-purple-500 rounded-full animate-pulse-green"></span></div>
<p id="m-audit" class="text-3xl font-mono font-bold text-purple-400">--</p>
<p class="text-xs text-gray-500 mt-2">变更操作累计</p>
</div>
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800">
<div class="flex justify-between items-start mb-2"><span class="text-xs text-gray-500">机器人</span><span id="bot-dot" class="w-2 h-2 bg-gray-500 rounded-full"></span></div>
<p id="m-bot" class="text-3xl font-mono font-bold text-gray-400">--</p>
<p class="text-xs text-gray-500 mt-2">MTProto 会话后端</p>
</div>
</div>
<!-- 图表 + 服务 -->
<div class="grid grid-cols-3 gap-4 mb-4">
<div class="col-span-2 bg-gray-900 rounded-lg p-4 border border-gray-800">
<div class="flex justify-between items-center mb-4">
<h3 class="text-sm font-semibold">请求量（实时）</h3>
<span class="text-xs text-gray-500">窗口内合计: <span id="req-total" class="text-white font-mono">0</span></span>
</div>
<div id="chart" class="h-48 flex items-end gap-0.5"></div>
<div id="chart-labels" class="flex justify-between text-xs text-gray-600 mt-2"></div>
</div>
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800">
<h3 class="text-sm font-semibold mb-4">服务健康</h3>
<div id="services" class="space-y-3"></div>
</div>
</div>
<!-- 日志流 -->
<div class="bg-gray-900 rounded-lg border border-gray-800 mb-4">
<div class="px-4 py-3 border-b border-gray-800 flex justify-between items-center">
<h3 class="text-sm font-semibold">实时日志流</h3>
<div class="flex gap-2">
<button data-level="ALL" class="log-filter px-2 py-1 bg-green-600 text-xs rounded cursor-pointer">全部</button>
<button data-level="INFO" class="log-filter px-2 py-1 bg-gray-700 text-xs rounded cursor-pointer">INFO</button>
<button data-level="WARN" class="log-filter px-2 py-1 bg-gray-700 text-xs rounded cursor-pointer">WARN</button>
<button data-level="ERROR" class="log-filter px-2 py-1 bg-gray-700 text-xs rounded cursor-pointer">ERROR</button>
</div>
</div>
<div id="logstream" class="p-4 font-mono text-xs space-y-1 h-40 overflow-y-auto bg-gray-950"></div>
</div>
<!-- 操作区 -->
<h3 class="text-sm font-semibold mb-3 text-gray-300">快捷操作（全部功能）</h3>
<div class="grid grid-cols-3 gap-4 mb-4">
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800">
<h4 class="text-sm font-semibold mb-3">生成号码</h4>
<div class="flex gap-2"><input id="gen-count" type="number" value="5" min="1" max="100" class="op-input"><button onclick="opGenerate()" class="op-btn">生成</button></div>
<p id="gen-result" class="font-mono text-xs text-gray-400 mt-2 break-all"></p>
</div>
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800">
<h4 class="text-sm font-semibold mb-3">验证号码（一行一个）</h4>
<textarea id="val-numbers" rows="2" class="op-input" placeholder="+85251234567"></textarea>
<button onclick="opValidate()" class="op-btn mt-2">验证</button>
<p id="val-result" class="font-mono text-xs text-gray-400 mt-2 break-all"></p>
</div>
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800">
<h4 class="text-sm font-semibold mb-3">导入号码（一行一个）</h4>
<textarea id="imp-numbers" rows="2" class="op-input" placeholder="+85251234567"></textarea>
<button onclick="opImport()" class="op-btn mt-2">导入</button>
<p id="imp-result" class="font-mono text-xs text-gray-400 mt-2 break-all"></p>
</div>
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800">
<h4 class="text-sm font-semibold mb-3">发送短信</h4>
<input id="sms-phone" class="op-input mb-2" placeholder="手机号">
<textarea id="sms-content" rows="2" class="op-input" placeholder="内容"></textarea>
<button onclick="opSms()" class="op-btn mt-2">发送</button>
<p id="sms-result" class="font-mono text-xs text-gray-400 mt-2 break-all"></p>
</div>
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800">
<h4 class="text-sm font-semibold mb-3">机器人控制</h4>
<p class="font-mono text-xs text-gray-400 mb-2">状态: <span id="bot-state">--</span></p>
<div class="flex gap-2"><button onclick="opBot('start')" class="op-btn">启动</button><button onclick="opBot('stop')" class="op-btn warn">停止</button><button onclick="refreshAll()" class="op-btn gray">刷新</button></div>
<p id="bot-result" class="font-mono text-xs text-gray-400 mt-2"></p>
</div>
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800">
<h4 class="text-sm font-semibold mb-3">转换测试（session→tdata）</h4>
<textarea id="conv-session" rows="2" class="op-input" placeholder="telethon session 字符串"></textarea>
<button onclick="opConvert()" class="op-btn mt-2">测试转换</button>
<p id="conv-result" class="font-mono text-xs text-gray-400 mt-2 break-all"></p>
</div>
</div>
<!-- 管理功能区（原PHP后台迁移） -->
<h3 class="text-sm font-semibold mb-3 text-gray-300">管理功能（需管理员登录）</h3>
<div class="grid grid-cols-3 gap-4 mb-4">
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800">
<h4 class="text-sm font-semibold mb-3">系统配置</h4>
<div id="cfg-list" class="font-mono text-xs text-gray-400 mb-2 max-h-32 overflow-y-auto"></div>
<input id="cfg-key" class="op-input mb-2" placeholder="键">
<input id="cfg-value" class="op-input mb-2" placeholder="值">
<div class="flex gap-2"><button onclick="cfgSave()" class="op-btn">保存</button><button onclick="cfgLoad()" class="op-btn gray">刷新</button></div>
</div>
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800">
<h4 class="text-sm font-semibold mb-3">文件上传</h4>
<input id="up-file" type="file" class="op-input mb-2">
<button onclick="upGo()" class="op-btn">上传</button>
<div id="up-list" class="font-mono text-xs text-gray-400 mt-2 max-h-32 overflow-y-auto"></div>
</div>
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800">
<h4 class="text-sm font-semibold mb-3">机器人TOKEN</h4>
<p class="font-mono text-xs text-gray-400 mb-2">当前: <span id="token-masked">--</span></p>
<input id="token-input" type="password" class="op-input mb-2" placeholder="新TOKEN">
<div class="flex gap-2"><button onclick="tokenSave()" class="op-btn">保存</button><button onclick="tokenTest()" class="op-btn gray">测试链接</button></div>
<p id="token-result" class="font-mono text-xs text-gray-400 mt-2 break-all"></p>
</div>
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800">
<h4 class="text-sm font-semibold mb-3">账号管理</h4>
<div id="user-list" class="font-mono text-xs text-gray-400 mb-2 max-h-32 overflow-y-auto"></div>
<input id="user-name" class="op-input mb-2" placeholder="用户名">
<input id="user-pass" type="password" class="op-input mb-2" placeholder="密码（≥6位）">
<div class="flex gap-2"><button onclick="userAdd('operator')" class="op-btn">建操作员</button><button onclick="userAdd('admin')" class="op-btn warn">建管理员</button></div>
</div>
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800">
<h4 class="text-sm font-semibold mb-3">备份文件</h4>
<div id="bak-list" class="font-mono text-xs text-gray-400 mb-2 max-h-32 overflow-y-auto"></div>
<button onclick="bakLoad()" class="op-btn gray">刷新</button>
</div>
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800">
<h4 class="text-sm font-semibold mb-3">机器人日志</h4>
<pre id="bot-log" class="font-mono text-xs text-gray-400 bg-gray-950 p-2 rounded max-h-40 overflow-y-auto">--</pre>
<button onclick="botLogLoad()" class="op-btn gray mt-2">刷新</button>
</div>
</div>
<div class="grid grid-cols-3 gap-4 mb-4">
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800 col-span-2">
<h4 class="text-sm font-semibold mb-3">操作审计（最近20条）</h4>
<div id="audit-list" class="font-mono text-xs text-gray-400 max-h-40 overflow-y-auto"></div>
<button onclick="auditLoad()" class="op-btn gray mt-2">刷新</button>
</div>
<div class="bg-gray-900 rounded-lg p-4 border border-gray-800">
<h4 class="text-sm font-semibold mb-3">商城（分类/商品）</h4>
<div class="flex gap-2 mb-2"><input id="cate-title" class="op-input" placeholder="新分类名"><button onclick="cateAdd()" class="op-btn">加分类</button></div>
<div id="cate-list" class="font-mono text-xs text-gray-400 mb-2 max-h-24 overflow-y-auto"></div>
<div class="flex gap-2 mb-2"><input id="goods-title" class="op-input" placeholder="商品名"><input id="goods-price" type="number" step="0.01" class="op-input" placeholder="价格"></div>
<button onclick="goodsAdd()" class="op-btn">加商品</button>
<div id="goods-list" class="font-mono text-xs text-gray-400 mt-2 max-h-24 overflow-y-auto"></div>
</div>
</div>
</div>
<footer class="bg-gray-900 border-t border-gray-800 px-4 py-3 flex justify-between items-center">
<span class="text-gray-600 text-xs">UI style adapted from joshhu/uitest #31 Real-time Monitoring (MIT)</span>
<a href="/admin/" class="text-gray-400 hover:text-white text-sm">管理后台 &rarr;</a>
</footer>
<script>
let paused = false, logLevel = 'ALL';
document.getElementById('btn-pause').onclick = function(){ paused = !paused; this.textContent = paused ? '继续' : '暂停'; };
document.querySelectorAll('.log-filter').forEach(b => b.onclick = function(){
  logLevel = this.dataset.level;
  document.querySelectorAll('.log-filter').forEach(x => x.className = 'log-filter px-2 py-1 bg-gray-700 text-xs rounded cursor-pointer');
  this.className = 'log-filter px-2 py-1 bg-green-600 text-xs rounded cursor-pointer';
  refreshAll();
});
async function jget(url){ const r = await fetch(url); return r.json(); }
async function jpost(url, body){
  const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  return {status:r.status, data:await r.json()};
}
function dotColor(ok){ return ok ? 'bg-green-500' : 'bg-red-500'; }
function levelColor(l){ return l==='ERROR' ? 'text-red-400' : (l==='WARN' ? 'text-yellow-400' : 'text-green-400'); }
async function refreshAll(){
  if (paused) return;
  try {
    const ov = await jget('/api/metrics/overview');
    document.getElementById('m-phones').textContent = ov.phones;
    document.getElementById('m-valid').textContent = ov.valid_phones;
    document.getElementById('m-sms').textContent = ov.sms;
    document.getElementById('m-backups').textContent = ov.backups;
    document.getElementById('m-audit').textContent = ov.audit;
    const st = await jget('/api/system/status');
    const svc = document.getElementById('services');
    svc.innerHTML = Object.values(st).map(s =>
      '<div class="flex items-center justify-between"><div class="flex items-center gap-2">' +
      '<span class="w-2 h-2 rounded-full ' + dotColor(s.ok) + '"></span>' +
      '<span class="text-sm">' + s.label + '</span></div></div>').join('');
    const botOk = st.bot.ok;
    document.getElementById('bot-dot').className = 'w-2 h-2 rounded-full ' + (botOk ? 'bg-green-500 animate-pulse-green' : 'bg-gray-500');
    const botEl = document.getElementById('m-bot');
    botEl.textContent = botOk ? '运行中' : '已停止';
    botEl.className = 'text-3xl font-mono font-bold ' + (botOk ? 'text-green-400' : 'text-gray-400');
    document.getElementById('bot-state').textContent = botOk ? '运行中' : '已停止';
    const allOk = Object.values(st).every(s => s.ok);
    const bar = document.getElementById('statusbar');
    bar.className = (allOk ? 'bg-green-600' : 'bg-yellow-600') + ' text-white text-center py-1 text-sm font-medium';
    document.getElementById('statusbar-text').textContent = allOk ? '统一后端运行中' : '部分服务异常';
    const rc = await jget('/api/metrics/recent');
    const max = Math.max(1, ...rc.buckets);
    document.getElementById('chart').innerHTML = rc.buckets.map(v => {
      const h = Math.max(4, Math.round(v / max * 100));
      const c = v >= max && max > 3 ? 'bg-yellow-500' : 'bg-green-500';
      return '<div class="flex-1 ' + c + ' rounded-t transition-all" style="height:' + h + '%"></div>';
    }).join('');
    const lbs = rc.labels;
    document.getElementById('chart-labels').innerHTML =
      '<span>' + (lbs[0]||'--') + '</span><span>' + (lbs[Math.floor(lbs.length/2)]||'--') + '</span><span>Now</span>';
    document.getElementById('req-total').textContent = rc.buckets.reduce((a,b)=>a+b,0);
    const rows = rc.entries.filter(e => logLevel==='ALL' || e.level===logLevel).map(e =>
      '<p><span class="text-gray-500">' + e.t + '</span> <span class="' + levelColor(e.level) + '">[' + e.level + ']</span> ' +
      e.method + ' ' + e.path + ' <span class="text-gray-500">' + e.status + '</span></p>').join('')
      || '<p class="text-gray-600">暂无日志</p>';
    document.getElementById('logstream').innerHTML = rows;
    document.getElementById('last-sync').textContent = new Date().toLocaleTimeString('zh-CN', {hour12:false});
  } catch(e){ console.error(e); }
}
function lines(id){ return document.getElementById(id).value.split('\\n').map(s=>s.trim()).filter(Boolean); }
async function opGenerate(){
  const n = parseInt(document.getElementById('gen-count').value) || 5;
  const r = await jpost('/api/phone/generate', {count:n});
  document.getElementById('gen-result').textContent = r.status===200 ? '生成'+r.data.count+'个: '+(r.data.data.map(x=>x.number).join(', ')) : '失败: '+JSON.stringify(r.data);
  refreshAll();
}
async function opValidate(){
  const r = await jpost('/api/phone/validate', {numbers:lines('val-numbers')});
  document.getElementById('val-result').textContent = r.status===200 ? r.data.data.map(x=>x.number+':'+(x.is_valid?'有效':'无效')).join(' | ') : '失败: '+JSON.stringify(r.data);
  refreshAll();
}
async function opImport(){
  const r = await jpost('/api/phone/import', {numbers:lines('imp-numbers')});
  document.getElementById('imp-result').textContent = r.status===200 ? ('新增'+r.data.imported+'，重复'+r.data.skipped_dup+'，非法'+r.data.skipped_invalid.length) : '失败: '+JSON.stringify(r.data);
  refreshAll();
}
async function opSms(){
  const r = await jpost('/api/sms/send', {phone:document.getElementById('sms-phone').value, content:document.getElementById('sms-content').value, sender:'Console'});
  document.getElementById('sms-result').textContent = r.status===200 ? ('已入队 id='+r.data.sms_id) : '失败: '+JSON.stringify(r.data);
  refreshAll();
}
async function opBot(act){
  const r = await jpost('/api/bot/'+act, {});
  document.getElementById('bot-result').textContent = r.data.message || JSON.stringify(r.data);
  setTimeout(refreshAll, 1500);
}
async function opConvert(){
  const r = await jpost('/to-tdata', {backup:{data:document.getElementById('conv-session').value, format:'telethon_session'}, options:{}});
  document.getElementById('conv-result').textContent = JSON.stringify(r.data).slice(0, 200);
}
async function cfgLoad(){
  const r = await jget('/api/system/config');
  document.getElementById('cfg-list').innerHTML = (r.data||[]).map(c=>'<div>'+c.key+' = '+(c.value||'').slice(0,40)+'</div>').join('') || '暂无配置（需登录）';
}
async function cfgSave(){
  const key = document.getElementById('cfg-key').value.trim();
  const value = document.getElementById('cfg-value').value;
  const resp = await fetch('/api/system/config', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({key, value})});
  const d = await resp.json();
  alert(d.message || d.detail || JSON.stringify(d));
  cfgLoad(); refreshAll();
}
async function upGo(){
  const f = document.getElementById('up-file').files[0];
  if (!f) { alert('请选择文件'); return; }
  const fd = new FormData(); fd.append('file', f);
  const r = await fetch('/api/upload', {method:'POST', body:fd});
  const d = await r.json();
  alert(d.message || d.detail || JSON.stringify(d));
  upLoad(); refreshAll();
}
async function upLoad(){
  const r = await jget('/api/upload/list?limit=20');
  document.getElementById('up-list').innerHTML = (r.data||[]).map(x=>'<div>'+x.filename+' ('+x.size+'B)</div>').join('') || '暂无';
}
async function tokenLoad(){
  const r = await fetch('/api/bot/token'); const d = await r.json();
  document.getElementById('token-masked').textContent = d.masked || d.detail || '--';
}
async function tokenSave(){
  const token = document.getElementById('token-input').value.trim();
  const r = await fetch('/api/bot/token', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({token})});
  const d = await r.json();
  document.getElementById('token-result').textContent = d.message || d.detail || JSON.stringify(d);
  tokenLoad();
}
async function tokenTest(){
  const token = document.getElementById('token-input').value.trim();
  const r = await jpost('/api/bot/token/test', {token});
  document.getElementById('token-result').textContent = r.status===200 ? ('连通: '+r.data.username) : ('失败: '+JSON.stringify(r.data));
}
async function userLoad(){
  const r = await fetch('/api/users'); const d = await r.json();
  if (!d.data) { document.getElementById('user-list').innerHTML = '需管理员登录'; return; }
  document.getElementById('user-list').innerHTML = d.data.map(u =>
    '<div>'+u.username+' ['+u.role+'] '+(u.status?'启用':'禁用')+
    ' <a href="javascript:userToggle('+u.id+','+(u.status?0:1)+')" class="text-blue-400">启/禁</a>'+
    ' <a href="javascript:userPwd('+u.id+')" class="text-yellow-400">改密</a></div>').join('') || '暂无';
}
async function userAdd(role){
  const username = document.getElementById('user-name').value.trim();
  const password = document.getElementById('user-pass').value;
  const r = await jpost('/api/users', {username, password, role});
  alert(r.data.message || r.data.detail || JSON.stringify(r.data));
  userLoad();
}
async function userToggle(id, status){
  const r = await fetch('/api/users/'+id, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status})});
  alert((await r.json()).message || '完成'); userLoad();
}
async function userPwd(id){
  const password = prompt('输入新密码（≥6位）:');
  if (!password) return;
  const r = await fetch('/api/users/'+id, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({password})});
  alert((await r.json()).message || '完成');
}
async function bakLoad(){
  document.getElementById('bak-list').innerHTML = '备份目录文件请见 <a href="/admin/backups" class="text-blue-400">备份管理页</a>（支持删除）';
}
async function botLogLoad(){
  const r = await fetch('/api/bot/log?num=50'); const d = await r.json();
  document.getElementById('bot-log').textContent = d.log || JSON.stringify(d);
}
async function auditLoad(){
  const r = await jget('/api/audit/logs?limit=20');
  if (!r.data) { document.getElementById('audit-list').innerHTML = '需登录查看'; return; }
  document.getElementById('audit-list').innerHTML = r.data.map(a =>
    '<div>['+a.method+'] '+a.path+' → '+a.status+' <span class="text-gray-600">'+a.username+' '+a.ip+'</span></div>').join('') || '暂无';
}
async function mallLoad(){
  const c = await jget('/api/mall/cate');
  document.getElementById('cate-list').innerHTML = (c.data||[]).map(x =>
    '<div>['+x.id+'] '+x.title+' <a href="javascript:cateDel('+x.id+')" class="text-red-400">删</a></div>').join('') || '暂无';
  const g = await jget('/api/mall/goods');
  document.getElementById('goods-list').innerHTML = (g.data||[]).map(x =>
    '<div>['+x.id+'] '+x.title+' ¥'+x.price+' x'+x.stock+' <a href="javascript:goodsDel('+x.id+')" class="text-red-400">删</a></div>').join('') || '暂无';
}
async function cateAdd(){
  const title = document.getElementById('cate-title').value.trim();
  if (!title) return;
  const r = await jpost('/api/mall/cate', {title});
  alert(r.data.message || r.data.detail || JSON.stringify(r.data)); mallLoad();
}
async function cateDel(id){
  if (!confirm('删除分类 '+id+'？')) return;
  await fetch('/api/mall/cate/'+id, {method:'DELETE'}); mallLoad();
}
async function goodsAdd(){
  const title = document.getElementById('goods-title').value.trim();
  const price = parseFloat(document.getElementById('goods-price').value) || 0;
  if (!title) return;
  const r = await jpost('/api/mall/goods', {title, price});
  alert(r.data.message || r.data.detail || JSON.stringify(r.data)); mallLoad();
}
async function goodsDel(id){
  if (!confirm('删除商品 '+id+'？')) return;
  await fetch('/api/mall/goods/'+id, {method:'DELETE'}); mallLoad();
}
function mgmtRefresh(){ cfgLoad(); upLoad(); tokenLoad(); userLoad(); botLogLoad(); auditLoad(); mallLoad(); document.getElementById('bak-list').innerHTML = '备份目录文件请见 <a href="/admin/backups" class="text-blue-400">备份管理页</a>'; }
refreshAll();
setInterval(refreshAll, 3000);
mgmtRefresh();
</script>
</body>
</html>"""
