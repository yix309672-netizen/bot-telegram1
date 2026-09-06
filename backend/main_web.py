# coding=utf-8
import random
import logging
import os

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, Any, Dict

logger = logging.getLogger(__name__)

app = FastAPI(title="Telegram 安全验证后台")

# 内存数据库
phone_numbers_db = []
sms_records_db = []
backup_files_db = []

# 页面
html_index = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram 安全验证后台</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; }
        h1 { font-size: 28px; margin-bottom: 10px; }
        .nav { display: flex; gap: 10px; flex-wrap: wrap; }
        .nav a { color: white; text-decoration: none; padding: 8px 16px; background: rgba(255,255,255,0.2); border-radius: 4px; }
        .nav a:hover, .nav a.active { background: rgba(255,255,255,0.3); }
        .container { max-width: 1400px; margin: 20px auto; padding: 0 20px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 25px; border-radius: 12px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .stat-card .number { font-size: 42px; font-weight: bold; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .stat-card .label { color: #666; margin-top: 8px; font-size: 14px; }
        .card { background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .card h2 { margin-bottom: 20px; color: #333; font-size: 20px; border-bottom: 2px solid #667eea; padding-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
        .btn { display: inline-block; padding: 10px 20px; background: #667eea; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; text-decoration: none; }
        .btn:hover { background: #5568d3; }
        .btn-success { background: #10b981; }
        .btn-success:hover { background: #059669; }
        .btn-danger { background: #ef4444; }
        .btn-danger:hover { background: #dc2626; }
        .btn-sm { padding: 6px 12px; font-size: 12px; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 6px; color: #555; font-weight: 500; }
        .form-group input, .form-group select, .form-group textarea { width: 100%; padding: 12px; border: 1px solid #e5e7eb; border-radius: 6px; font-size: 14px; }
        .form-group input:focus { outline: none; border-color: #667eea; }
        .toolbar { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 14px; text-align: left; border-bottom: 1px solid #e5e7eb; }
        th { background: #f9fafb; font-weight: 600; color: #374151; }
        tr:hover { background: #f9fafb; }
        .status { padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 500; }
        .status-generated { background: #dbeafe; color: #2563eb; }
        .status-valid { background: #d1fae5; color: #059669; }
        .status-invalid { background: #fee2e2; color: #dc2626; }
        .status-sent { background: #dbeafe; color: #2563eb; }
        .status-delivered { background: #d1fae5; color: #059669; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center; }
        .modal.active { display: flex; }
        .modal-content { background: white; padding: 30px; border-radius: 12px; width: 480px; max-width: 90%; max-height: 90vh; overflow-y: auto; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .modal-header h3 { font-size: 18px; color: #333; }
        .modal-close { background: none; border: none; font-size: 28px; cursor: pointer; color: #999; }
        .empty { text-align: center; padding: 40px; color: #999; }
        .actions { display: flex; gap: 8px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔒 Telegram 安全验证后台</h1>
        <nav class="nav">
            <a href="/" class="active">🏠 首页</a>
            <a href="/phones">📱 号码管理</a>
            <a href="/sms">💬 短信记录</a>
            <a href="/backups">📦 备份管理</a>
        </nav>
    </div>

    <div class="container">
        <div class="stats">
            <div class="stat-card">
                <div class="number" id="stat-phones">–</div>
                <div class="label">📱 总号码数</div>
            </div>
            <div class="stat-card">
                <div class="number" id="stat-valid">–</div>
                <div class="label">✅ 有效号码</div>
            </div>
            <div class="stat-card">
                <div class="number" id="stat-sms">–</div>
                <div class="label">💬 短信总数</div>
            </div>
            <div class="stat-card">
                <div class="number" id="stat-backups">–</div>
                <div class="label">📦 备份总数</div>
            </div>
        </div>

        <div class="card">
            <h2>⚡ 快速操作</h2>
            <div style="display: flex; gap: 12px; flex-wrap: wrap;">
                <button class="btn btn-success" onclick="openModal('generateModal')">➕ 生成号码</button>
                <button class="btn btn-success" onclick="openModal('smsModal')">📤 发送短信</button>
                <button class="btn" onclick="location.href='/phones'">📋 号码列表</button>
                <button class="btn" onclick="location.href='/sms'">📨 短信记录</button>
            </div>
        </div>

        <div class="card">
            <h2>📝 最近操作</h2>
            <div id="recentOps">
                <div class="empty">暂无操作记录</div>
            </div>
        </div>
    </div>

    <!-- 生成号码弹窗 -->
    <div class="modal" id="generateModal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>生成香港号码 (+852)</h3>
                <button class="modal-close" onclick="closeModal('generateModal')">&times;</button>
            </div>
            <div class="form-group">
                <label>生成数量 (1-100)</label>
                <input type="number" id="generateCount" value="10" min="1" max="100">
            </div>
            <button class="btn btn-success" onclick="generatePhones()" style="width: 100%;">生成号码</button>
        </div>
    </div>

    <!-- 发送短信弹窗 -->
    <div class="modal" id="smsModal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>发送短信</h3>
                <button class="modal-close" onclick="closeModal('smsModal')">&times;</button>
            </div>
            <div class="form-group">
                <label>手机号</label>
                <input type="text" id="smsPhone" placeholder="+85212345678">
            </div>
            <div class="form-group">
                <label>短信内容</label>
                <textarea id="smsContent" rows="3" placeholder="输入短信内容"></textarea>
            </div>
            <button class="btn btn-success" onclick="sendSMS()" style="width: 100%;">发送短信</button>
        </div>
    </div>

    <script>
        // 主接口地址（8000）：统计与业务写操作都走主接口，本页只做展示
        const API_BASE = 'http://localhost:8000';
        // 跨端口调8000接口时自动带上登录 Cookie，后台开鉴权后按钮仍可用
        const _rawFetch = window.fetch.bind(window);
        window.fetch = (url, opts = {}) => _rawFetch(url, Object.assign({credentials: 'include'}, opts));
        async function loadStats() {
            try {
                const [p, s] = await Promise.all([
                    fetch(API_BASE + '/api/phone/list').then(r => r.json()),
                    fetch(API_BASE + '/api/sms/list').then(r => r.json()),
                ]);
                const phones = p.data || [];
                document.getElementById('stat-phones').textContent = p.total ?? phones.length;
                document.getElementById('stat-valid').textContent = phones.filter(x => x.status === 'valid').length;
                document.getElementById('stat-sms').textContent = s.total ?? (s.data || []).length;
                document.getElementById('stat-backups').textContent = '–';
            } catch (e) { console.error('统计加载失败', e); }
        }
        loadStats();
        function openModal(id) { document.getElementById(id).classList.add('active'); }
        function closeModal(id) { document.getElementById(id).classList.remove('active'); }

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
                    alert('✅ 生成成功！生成了 ' + data.count + ' 个号码');
                    closeModal('generateModal');
                    loadStats();
                }
            } catch(e) {
                alert('❌ 生成失败: ' + e);
            }
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
                    closeModal('smsModal');
                    loadStats();
                }
            } catch(e) {
                alert('❌ 发送失败: ' + e);
            }
        }
    </script>
</body>
</html>
'''

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
        const API_BASE = 'http://localhost:8000';
        // 跨端口调8000接口时自动带上登录 Cookie，后台开鉴权后按钮仍可用
        const _rawFetch2 = window.fetch.bind(window);
        window.fetch = (url, opts = {}) => _rawFetch2(url, Object.assign({credentials: 'include'}, opts));
        // 本页弹窗是行内 display 样式，直接开关（首页的 class 方案在此页无样式，不可用）
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
        const API_BASE = 'http://localhost:8000';
        // 跨端口调8000接口时自动带上登录 Cookie，后台开鉴权后按钮仍可用
        const _rawFetch3 = window.fetch.bind(window);
        window.fetch = (url, opts = {}) => _rawFetch3(url, Object.assign({credentials: 'include'}, opts));
        async function loadSMS() {
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

html_backups = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>备份管理 - Telegram 后台</title>
    <style>
        * { margin: 0; padding: 0; }
        body { font-family: -apple-system, sans-serif; background: #f5f5f5; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; }
        h1 { font-size: 24px; }
        .container { max-width: 1400px; margin: 20px auto; padding: 0 20px; }
        .card { background: white; border-radius: 12px; padding: 20px; }
        .btn { display: inline-block; padding: 10px 16px; background: #667eea; color: white; border: none; border-radius: 6px; cursor: pointer; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; border-bottom: 1px solid #e5e7eb; }
    </style>
</head>
<body>
    <div class="header"><h1>📦 备份管理</h1></div>
    <div class="container">
        <div class="card">
            <p style="color:#666; text-align:center; padding:40px;">暂无备份数据</p>
        </div>
    </div>
</body>
</html>
'''

# 路由
@app.get("/", response_class=HTMLResponse)
async def home():
    return html_index

@app.get("/phones", response_class=HTMLResponse)
async def phones():
    return html_phones

@app.get("/sms", response_class=HTMLResponse)
async def sms():
    return html_sms

@app.get("/backups", response_class=HTMLResponse)
async def backups():
    return html_backups


# 独立转换服务接口：供 lib/converter_client.to_tdata 调用（默认端口8002）
class ToTdataBackup(BaseModel):
    data: str = ""
    format: str = "telethon_session"


class ToTdataRequest(BaseModel):
    backup: ToTdataBackup = ToTdataBackup()
    options: Dict[str, Any] = {}


@app.get("/health")
async def converter_health():
    # 健康检查：供机器人与部署脚本探活
    return {"status": "ok", "service": "converter", "version": "1.0.0"}


@app.post("/to-tdata")
async def to_tdata(payload: ToTdataRequest):
    # 将 telethon session 字符串转换为 tdata（有 opentele 则真转，否则返回待处理状态）
    session_str = (payload.backup.data or "").strip()
    if not session_str:
        return {"error": "empty_session", "detail": "缺少 session 字符串"}
    try:
        from opentele.td import TDesktop
        from opentele.tl import TelegramClient as TelethonToDesktop
        from opentele.api import API, UseCurrentSession
        api = API.TelegramDesktop.Generate()
        client = TelethonToDesktop(session_str, api=api)
        await client.ToTDesktop(flag=UseCurrentSession)
        return {"status": "ok", "format": "tdata", "detail": "转换成功"}
    except ImportError:
        logger.warning("opentele 未安装，转换请求已受理但未执行")
        return {"status": "queued", "format": "tdata", "detail": "opentele 未安装，需在转换服务环境 pip install opentele 后重试"}
    except Exception as e:
        logger.error(f"转换失败: {e}")
        return {"error": "convert_failed", "detail": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)