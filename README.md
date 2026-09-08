# TeleBot - Telegram 全功能项目

## 服务架构

| 服务         | 端口     | 说明                          |
|------------|--------|-----------------------------|
| backend    | 8000   | Python FastAPI 统一后端（号码/短信/备份/登录/展示页/会话转换） |
| bot        | -      | Telegram 机器人（长轮询，经统一后端转 tdata）               |
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
├── backend/             # FastAPI 统一后端（单端口8000）
│   ├── main_api.py      # 统一入口（业务接口/管理页/展示页/转换/登录/JWT/CORS/限流/审计）
│   ├── display_pages.py # 展示页模板（号码/短信/备份）
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

# 启动统一后端（含展示页与转换服务）
python scripts/start_converter.py

# 启动机器人（新开终端）
python bot/bot.py

# 冒烟测试
python scripts/test_api.py
```

### 4. Docker 部署

```bash
# 启动所有服务
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

### 短信管理（队列状态机）

| 方法   | 路径          | 说明       |
|------|-------------|----------|
| POST | /api/sms/send | 入队（queued） |
| POST | /api/sms/claim | worker认领最老件（→sending，超时5分钟自动回收） |
| POST | /api/sms/{id}/complete | 回执 sent/failed（失败<3次回队列，≥3次终结） |
| POST | /api/sms/{id}/requeue | 失败件重发（管理员） |
| GET  | /api/sms/list | 短信记录（limit/offset/status过滤） |

投递由机器人内 worker 执行（`SMS_WORKER_ENABLED=true`，轮询 `SMS_POLL_INTERVAL` 秒，
发送会话 `SMS_SENDER_SESSION`，无会话时只认领占位不吞件）。

## 防封说明

- Bot API 轮询（getUpdates）是官方接口，24 小时开着不会封号
- 真正危险的是：死 token 无限重启 hammer、MTProto 频繁重连、失败重试风暴，本项目已处理：
  - Token 无效（Unauthorized）秒停不重试；连续 5 次启动后 60 秒内崩溃熔断停机
  - 无人使用 `IDLE_STOP_MINUTES` 分钟（默认 30，0 关闭）自动停机，需用时后台点启动
  - Telethon 会话按需连接，短信发送会话无配置时不建 MTProto 连接

### 备份管理

| 方法   | 路径                  | 说明     |
|------|---------------------|--------|
| POST | /api/backup/import      | 导入备份文件 |
| POST | /api/backup/import_json | JSON 导入备份 |

### 转换接口（统一后端8000，同源）

| 方法 | 路径       | 说明              |
|----|----------|-----------------|
| GET | /health  | 健康检查            |
| POST | /to-tdata | session 转 tdata（需 opentele） |

### 展示页与监控台（统一后端8000）
| 页面 | 路径（登录态/公开别名） |
|----|------------------|
| 号码管理 | /admin/phones · /phones |
| 短信记录 | /admin/sms · /sms |
| 备份管理 | /admin/backups · /backups |
| 实时监控台 | /admin/console · /console |

实时监控台（UI 改编自 joshhu/uitest #31，MIT）：指标卡/请求图表/日志流/服务健康
3 秒轮询，外加生成/验证/导入/短信/机器人启停/转换测试六组快捷操作。
聚合接口：`/api/metrics/overview` `/api/metrics/recent` `/api/system/status`（公开只读）。

## 桌面多号切换（Windows本机）

- 命令行：`python scripts/switch_telegram.py --list` 查看，`python scripts/switch_telegram.py <号码>` 切换
- 网页：监控台“桌面多号切换”卡一键切换；接口 `/api/telegram/accounts` + `/api/telegram/switch`（需管理员）
- 切换自动备份当前上线号（`live_backup_*.zip`），tdata 优先用完整目录、其次转换包

## R2：PHP后台已迁移（admin/ 退役）

原 ThinkPHP 后台全部功能已搬入统一后端，对照表：

| PHP 模块 | Python 替代 |
|---|---|
| strategy.phone（号码增删改查/生成/导入） | /api/phone/*（generate/validate/import/list/PUT改状态/DELETE） |
| strategy.sms（短信群发/记录） | /api/sms/send + /api/sms/list |
| strategy.backup（备份上传/列表） | /api/backup/import(+文件列表页/DELETE删文件） |
| strategy.bot（启停/日志） | /api/bot/start|stop|status|log |
| system.bot_config（TOKEN） | /api/bot/token（查看脱敏/保存/测试getMe） |
| system.config（站点配置） | /api/system/config（键值增改查） |
| system.uploadfile（附件） | /api/upload（100MB内）+ /api/upload/list |
| system.log（操作日志） | audit_logs 表 + /api/audit/logs |
| system.admin/auth（账号角色） | admin_users 表 + /api/users（admin/operator 双角色） |
| mall.cate/goods（商城示例） | /api/mall/cate + /api/mall/goods |

角色说明：`admin` 全权，`operator` 只读与非破坏操作（删除/启停/密钥/账号管理仅 admin）。
数据迁移：`python scripts/migrate_php.py`（需 MySQL 在线，幂等可重跑；PHP 密码哈希不可复用，迁入账号需重置密码）。
PHP 目录保留归档不再启动；vendor 下的 PHP8.1 补丁仅具历史意义。

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
