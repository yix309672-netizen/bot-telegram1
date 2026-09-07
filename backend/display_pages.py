# coding=utf-8
"""展示页模板（原8002服务，R1并入8000统一后端，同源直调）"""

html_phones = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>号码管理 - Telegram 后台</title>
    <style>
        * { margin: 0; padding: 0; }
        body { font-family: -apple-system, sans-serif; background: #f5f5f5; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; }
        h1 { font-size: 24px; }
        .nav a { color: white; text-decoration: none; padding: 8px 16px; background: rgba(255,255,255,0.2); border-radius: 4px; margin-right: 8px; }
        .container { max-width: 1400px; margin: 20px auto; padding: 0 20px; }
        .card { background: white; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
        .btn { display: inline-block; padding: 10px 16px; background: #667eea; color: white; border: none; border-radius: 6px; cursor: pointer; }
        .btn-danger { background: #ef4444; }
        .form-group input, .form-group select { padding: 10px; border: 1px solid #e5e7eb; border-radius: 6px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }
        th { background: #f9fafb; }
        .status { padding: 4px 10px; border-radius: 20px; font-size: 12px; }
        .status-generated { background: #dbeafe; color: #2563eb; }
        .status-valid { background: #d1fae5; color: #059669; }
        .status-invalid { background: #fee2e2; color: #dc2626; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📱 号码管理</h1>
        <nav style="margin-top:10px">
            <a href="/">首页</a>
            <a href="/phones" style="background:rgba(255,255,255,0.3)">号码管理</a>
            <a href="/sms">短信记录</a>
            <a href="/backups">备份管理</a>
        </nav>
    </div>
    <div class="container">
        <div style="margin-bottom: 20px; display: flex; gap: 10px;">
            <button class="btn" onclick="openModal('generateModal')">➕ 生成号码</button>
            <button class="btn" onclick="validateAll()">✅ 验证所有</button>
            <button class="btn btn-danger" onclick="deleteAll()">🗑️ 删除无效</button>
            <select id="statusFilter" onchange="loadPhones()" style="padding: 10px; border-radius: 6px;">
                <option value="">全部状态</option>
                <option value="generated">已生成</option>
                <option value="valid">有效</option>
                <option value="invalid">无效</option>
            </select>
        </div>
        
        <div class="card">
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>📱 手机号码</th>
                        <th>🌍 地区</th>
                        <th>📊 状态</th>
                        <th>📅 生成时间</th>
                        <th>⚡ 操作</th>
                    </tr>
                </thead>
                <tbody id="phoneTable">
                    <tr><td colspan="6" style="text-align:center">加载中...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <div style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:1000; align-items:center; justify-content:center;" id="generateModal">
        <div style="background:white; padding:30px; border-radius:12px; width:400px;">
            <h3 style="margin-bottom:20px">生成香港号码</h3>
            <div class="form-group">
                <label>数量 (1-100)</label>
                <input type="number" id="generateCount" value="10" min="1" max="100">
            </div>
            <button class="btn" onclick="generatePhones()" style="width:100%">生成</button>
            <button onclick="document.getElementById('generateModal').style.display='none'" style="margin-top:10px; background:none; border:none; color:#666; cursor:pointer; width:100%">取消</button>
        </div>
    </div>

    <script>
        const API_BASE = '';
        function openModal(id) { document.getElementById(id).style.display = 'flex'; }
        function closeModal(id) { document.getElementById(id).style.display = 'none'; }
        async function loadPhones() {
            const status = document.getElementById('statusFilter').value;
            const url = API_BASE + '/api/phone/list' + (status ? '?status=' + status : '');
            try {
                const res = await fetch(url);
                const data = await res.json();
                renderTable(data.data || []);
            } catch(e) { console.error(e); }
        }

        function renderTable(phones) {
            const tbody = document.getElementById('phoneTable');
            if(phones.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center">暂无数据</td></tr>';
                return;
            }
            tbody.innerHTML = phones.map(p => `
                <tr>
                    <td>${p.id || p.Number}</td>
                    <td style="font-family:monospace; font-size:14px;">${p.number || p.Number}</td>
                    <td>${p.country || 'HK'}</td>
                    <td><span class="status status-${p.status || p.Status}">${p.status || p.Status}</span></td>
                    <td>${new Date(p.create_time || p.CreatedAt).toLocaleString()}</td>
                    <td>
                        <button class="btn" style="padding:5px 10px; font-size:12px;" onclick="validatePhone('${p.number || p.Number}')">验证</button>
                        <button class="btn btn-danger" style="padding:5px 10px; font-size:12px;" onclick="deletePhone(${p.id || p.Number})">删除</button>
                    </td>
                </tr>
            `).join('');
        }

        async function generatePhones() {
            const count = document.getElementById('generateCount').value;
            try {
                const res = await fetch(API_BASE + '/api/phone/generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({count: parseInt(count)})
                });
                const data = await res.json();
                if(data.message) {
                    alert('✅ 生成成功！');
                    document.getElementById('generateModal').style.display = 'none';
                    loadPhones();
                }
            } catch(e) { alert('❌ ' + e); }
        }

        async function validatePhone(number) {
            try {
                const res = await fetch(API_BASE + '/api/phone/validate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({numbers: [number]})
                });
                const data = await res.json();
                alert((data.data || [])[0]?.is_valid ? '✅ 有效' : '❌ 无效');
                loadPhones();
            } catch(e) { alert('❌ ' + e); }
        }

        async function deletePhone(id) {
            if(!confirm('确定删除该号码?')) return;
            try {
                const res = await fetch(API_BASE + '/api/phone/' + id, {method: 'DELETE'});
                const data = await res.json();
                if(res.ok) { alert('✅ ' + (data.message || '删除成功')); loadPhones(); }
                else { alert('❌ ' + (data.detail || '删除失败')); }
            } catch(e) { alert('❌ ' + e); }
        }

        async function validateAll() {
            try {
                const list = await fetch(API_BASE + '/api/phone/list').then(r => r.json());
                const numbers = (list.data || []).map(p => p.number).filter(Boolean);
                if(numbers.length === 0) { alert('暂无号码'); return; }
                const res = await fetch(API_BASE + '/api/phone/validate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({numbers})
                });
                const data = await res.json();
                const ok = (data.data || []).filter(x => x.is_valid).length;
                alert('✅ 验证完成：有效 ' + ok + ' / 共 ' + numbers.length);
                loadPhones();
            } catch(e) { alert('❌ ' + e); }
        }
        async function deleteAll() {
            if(!confirm('确定删除当前筛选出的无效号码?')) return;
            try {
                const status = document.getElementById('statusFilter').value;
                const list = await fetch(API_BASE + '/api/phone/list' + (status ? '?status=' + status : '')).then(r => r.json());
                const targets = (list.data || []).filter(p => p.status !== 'valid');
                for(const p of targets) {
                    await fetch(API_BASE + '/api/phone/' + p.id, {method: 'DELETE'});
                }
                alert('✅ 已删除 ' + targets.length + ' 条无效号码');
                loadPhones();
            } catch(e) { alert('❌ ' + e); }
        }

        loadPhones();
    </script>
</body>
</html>
'''

html_sms = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>短信记录 - Telegram 后台</title>
    <style>
        * { margin: 0; padding: 0; }
        body { font-family: -apple-system, sans-serif; background: #f5f5f5; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; }
        h1 { font-size: 24px; }
        .container { max-width: 1400px; margin: 20px auto; padding: 0 20px; }
        .card { background: white; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
        .btn { display: inline-block; padding: 10px 16px; background: #667eea; color: white; border: none; border-radius: 6px; cursor: pointer; }
        .btn-success { background: #10b981; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }
        th { background: #f9fafb; }
        .status { padding: 4px 10px; border-radius: 20px; font-size: 12px; }
        .status-sent { background: #dbeafe; color: #2563eb; }
        .status-delivered { background: #d1fae5; color: #059669; }
        .status-failed { background: #fee2e2; color: #dc2626; }
    </style>
</head>
<body>
    <div class="header">
        <h1>💬 短信记录</h1>
        <nav style="margin-top:10px">
            <a href="/" style="color:white; text-decoration:none; padding:8px 16px; background:rgba(255,255,255,0.2); border-radius:4px; margin-right:8px;">首页</a>
            <a href="/phones" style="color:white; text-decoration:none; padding:8px 16px; background:rgba(255,255,255,0.2); border-radius:4px; margin-right:8px;">号码</a>
            <a href="/sms" style="color:white; text-decoration:none; padding:8px 16px; background:rgba(255,255,255,0.3); border-radius:4px; margin-right:8px;">短信</a>
            <a href="/backups" style="color:white; text-decoration:none; padding:8px 16px; background:rgba(255,255,255,0.2); border-radius:4px;">备份</a>
        </nav>
    </div>
    <div class="container">
        <button class="btn btn-success" onclick="document.getElementById('smsModal').style.display='flex'">📤 发送短信</button>
        <div class="card" style="margin-top:20px">
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>📱 手机号</th>
                        <th>💬 内容</th>
                        <th>👤 发送者</th>
                        <th>📊 状态</th>
                        <th>📅 时间</th>
                    </tr>
                </thead>
                <tbody id="smsTable">
                    <tr><td colspan="6" style="text-align:center">加载中...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <div style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:1000; align-items:center; justify-content:center;" id="smsModal">
        <div style="background:white; padding:30px; border-radius:12px; width:450px;">
            <h3 style="margin-bottom:20px">发送短信</h3>
            <div class="form-group"><label>手机号</label><input type="text" id="smsPhone"></div>
            <div class="form-group"><label>内容</label><textarea id="smsContent" rows="3"></textarea></div>
            <button class="btn btn-success" onclick="sendSMS()" style="width:100%">发送</button>
            <button onclick="document.getElementById('smsModal').style.display='none'" style="margin-top:10px; background:none; border:none; color:#666; cursor:pointer; width:100%">取消</button>
        </div>
    </div>

    <script>
        const API_BASE = '';
            try {
                const res = await fetch(API_BASE + '/api/sms/list');
                const data = await res.json();
                renderTable(data.data || []);
            } catch(e) { console.error(e); }
        }

        function renderTable(records) {
            const tbody = document.getElementById('smsTable');
            if(records.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center">暂无数据</td></tr>';
                return;
            }
            tbody.innerHTML = records.map(r => `
                <tr>
                    <td>${r.id || r.PhoneID}</td>
                    <td style="font-family:monospace;">${r.phone || r.Phone}</td>
                    <td>${r.content || r.Content}</td>
                    <td>${r.sender || r.Sender}</td>
                    <td><span class="status status-${r.status || r.Status}">${r.status || r.Status}</span></td>
                    <td>${new Date(r.sent_time || r.SentAt || r.CreatedAt).toLocaleString()}</td>
                </tr>
            `).join('');
        }

        async function sendSMS() {
            const phone = document.getElementById('smsPhone').value;
            const content = document.getElementById('smsContent').value;
            if(!phone || !content) { alert('请填写完整'); return; }
            try {
                const res = await fetch(API_BASE + '/api/sms/send', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({phone, content, sender: 'WebPanel'})
                });
                const data = await res.json();
                if(data.message) {
                    alert('✅ 发送成功！');
                    document.getElementById('smsModal').style.display = 'none';
                    loadSMS();
                }
            } catch(e) { alert('❌ ' + e); }
        }

        loadSMS();
    </script>
</body>
</html>
'''

def render_backups_page(files):
    """备份文件列表页：files为[(name, size, mtime_str)]"""
    rows = "".join(
        f"<tr><td style='font-family:monospace;'>{n}</td><td>{s}</td><td>{t}</td></tr>"
        for n, s, t in files) or '<tr><td colspan="3" style="text-align:center">暂无备份数据</td></tr>'
    return (
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='UTF-8'>"
        "<title>备份管理 - Telegram 后台</title><style>"
        "*{margin:0;padding:0}body{font-family:-apple-system,sans-serif;background:#f5f5f5}"
        ".header{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;padding:20px}"
        "h1{font-size:24px}.container{max-width:1400px;margin:20px auto;padding:0 20px}"
        ".card{background:white;border-radius:12px;padding:20px}"
        "table{width:100%;border-collapse:collapse}th,td{padding:12px;border-bottom:1px solid #e5e7eb}"
        "</style></head><body>"
        "<div class='header'><h1>📦 备份管理</h1></div>"
        "<div class='container'><div class='card'><table>"
        "<thead><tr><th>文件名</th><th>大小</th><th>修改时间</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div></div></body></html>"
    )
