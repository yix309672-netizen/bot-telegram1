# TeleBot - Telegram 全功能项目

## 服务架构

| 服务         | 端口     | 说明                          |
|------------|--------|-----------------------------|
| backend    | 8000   | Python FastAPI 主接口（号码/短信/备份/登录） |
| converter  | 8002   | 会话转换服务（session 转 tdata，供机器人调用） |
| bot        | -      | Telegram 机器人（长轮询）               |
| db (MySQL) | 3306   | 数据库（连不上自动回退本地 SQLite）            |
| redis      | 6379   | 缓存（连不上自动降级内存）                 |
| nginx      | 80/443 | 反向代理                        |

## 目录结构

```
项目根目录/
├── bot/                 # Telegram 机器人
│   ├── bot.py           # 主机器人逻辑（长轮询，会话登录，备份转换，lib缺失自动降级）
│   ├── Dockerfile
│   └── requirements.txt
├── backend/             # FastAPI 后端
│   ├── main_api.py      # 主接口（端口8000：号码/短信/备份/登录/JWT/CORS/限流/审计）
│   ├── main_web.py      # 展示页+转换服务（端口8002：/to-tdata）
│   ├── dialaxy.py       # 自动化号码采集（无头+回写主接口）
│   ├── core/            # 核心层：database/SQLAlchemy / jwt_manager / cache/Redis / crypto / security
│   ├── config/          # 配置层：security.py 安全配置
│   ├── data/            # 本地 SQLite（自动生成，不入库）
│   ├── Dockerfile
│   └── requirements.txt
├── admin/               # PHP ThinkPHP 后台（含机器人TOKEN链接独立页 strategy.bot_token）
├── lib/                 # 共享库
│   └── converter_client.py  # 转换服务客户端
├── scripts/             # 工具脚本：start_converter / test_api冒烟 / import_phones导入
├── tests/               # pytest 测试（16+ 用例）
├── nginx/               # 反向代理配置
├── deploy/              # 部署方案和文档
├── docs/                # 项目文档
├── .env                 # 环境变量（已忽略，照 .env.example 配）
├── docker-compose.yml   # Docker 编排（含 converter 服务）
└── requirements.txt     # 全项目依赖汇总
```

## 快速开始

### 1. 环境准备

- Python 3.11+
- Docker Desktop + Docker Compose（容器部署）
- MySQL 8.0 + Redis 7（可选，不装自动降级）

### 2. 配置环境变量

```bash
# 复制环境变量文件
cp .env.example .env

# 编辑 .env 填入真实值
# 必须设置 BOT_TOKEN / API_ID / API_HASH
# 生产环境：ENABLE_AUTH=true + API_KEY + ADMIN_PASSWORD_HASH（见下）
```

### 3. 本地开发

```bash
# 创建虚拟环境（推荐）
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动主接口
uvicorn backend.main_api:app --reload --port 8000

# 启动转换服务（新开终端）
python scripts/start_converter.py

# 启动机器人（新开终端）
python bot/bot.py

# 冒烟测试
python scripts/test_api.py
```

### 4. Docker 部署

```bash
# 启动所有服务（含 converter）
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## API 接口（8000）

鉴权双轨：`X-API-Key` 请求头（外部程序）或登录 Cookie（页面按钮已自动带）。

### 号码管理

| 方法   | 路径                | 说明       |
|------|-------------------|----------|
| POST | /api/phone/generate | 生成香港号码   |
| POST | /api/phone/validate | 验证号码（同步回写库内状态） |
| POST | /api/phone/import   | 批量导入号码（去重+校验） |
| GET  | /api/phone/list     | 号码列表（status/limit/offset） |
| DELETE | /api/phone/{id}   | 按ID删除     |

### 短信管理

| 方法   | 路径          | 说明       |
|------|-------------|----------|
| POST | /api/sms/send | 发送短信（入队，投递由客户端执行） |
| GET  | /api/sms/list | 短信记录（limit/offset） |

### 备份管理

| 方法   | 路径                  | 说明     |
|------|---------------------|--------|
| POST | /api/backup/import      | 导入备份文件 |
| POST | /api/backup/import_json | JSON 导入备份 |

### 转换服务（8002）

| 方法 | 路径       | 说明              |
|----|----------|-----------------|
| GET | /health  | 健康检查            |
| POST | /to-tdata | session 转 tdata（需 opentele） |

## 生产安全配置

```bash
# 生成管理员密码哈希（argon2）
python -c "from backend.core.crypto import PasswordManager; print(PasswordManager.hash_password('你的强密码'))"
# 把输出填入 .env 的 ADMIN_PASSWORD_HASH，并删掉 ADMIN_PASSWORD 明文
```

- 登录防爆破：5 次失败锁定 IP 15 分钟
- 接口限流：同一 IP 每分钟最多 100 次（超限 429）
- 审计日志：变更加库表 `audit_logs`，记录操作人/IP/路径
- 密钥：`JWT_SECRET` 不设则自动生成落盘，重启不掉线

## 注意事项

1. 号码生成支持香港（+852），前缀 5/6/9 开头
2. 机器人使用 Telethon 协议登录，需配置 API_ID/API_HASH
3. 支持代理轮换（SOCKS5），防限流
4. 转换服务无 opentele 时返回 queued 状态，需 `pip install opentele` 后重试
5. 测试：`pytest tests/ -q --ignore=tests/security_tests`
