# TeleBot - Telegram 全功能项目

## 服务架构

| 服务         | 端口     | 说明                |
|------------|--------|-------------------|
| backend    | 8000   | Python FastAPI 后端 |
| bot        | -      | Telegram 机器人（长轮询） |
| db (MySQL) | 3306   | 数据库               |
| redis      | 6379   | 缓存                |
| nginx      | 80/443 | 反向代理              |

## 目录结构

```
项目根目录/
├── bot/                 # Telegram 机器人
│   ├── bot.py           # 主机器人逻辑
│   ├── converter_integration.py  # 备份转换集成
│   ├── Dockerfile
│   └── requirements.txt
├── backend/             # FastAPI 后端
│   ├── main_api.py      # API 服务（端口8000）
│   ├── main_web.py      # Web 管理界面（端口8002）
│   ├── dialaxy.py       # 自动化号码采集
│   ├── Dockerfile
│   └── requirements.txt
├── lib/                 # 共享库
│   └── converter_client.py  # 转换服务客户端
├── scripts/             # 工具脚本
├── tests/               # 测试文件
├── nginx/               # 反向代理配置
├── deploy/              # 部署方案和文档
├── docs/                # 项目文档
├── .env                 # 环境变量
├── docker-compose.yml   # Docker 编排
└── requirements.txt     # 全项目依赖汇总
```

## 快速开始

### 1. 环境准备

- Python 3.11+
- Docker Desktop + Docker Compose（容器部署）
- MySQL 8.0 + Redis 7（本地开发）

### 2. 配置环境变量

```bash
# 复制环境变量文件
cp .env.example .env

# 编辑 .env 填入真实值
# 必须设置 BOT_TOKEN
```

### 3. 本地开发

```bash
# 创建虚拟环境（推荐）
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动后端
uvicorn backend.main_api:app --reload --port 8000

# 启动机器人（新开终端）
python bot/bot.py

# Web 管理界面
uvicorn backend.main_web:app --reload --port 8002
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

## API 接口

### 号码管理

| 方法   | 路径              | 说明     |
|------|-----------------|--------|
| POST | /phone/generate | 生成香港号码 |
| POST | /phone/validate | 验证号码   |
| GET  | /phone/list     | 号码列表   |

### 短信管理

| 方法   | 路径        | 说明   |
|------|-----------|------|
| POST | /sms/send | 发送短信 |
| GET  | /sms/list | 短信记录 |

### 备份管理

| 方法   | 路径                  | 说明        |
|------|---------------------|-----------|
| POST | /backup/import      | 导入备份文件    |
| POST | /backup/import_json | JSON 导入备份 |
| GET  | /health             | 健康检查      |

## 注意事项

1. 号码生成支持香港（+852），前缀 5/6/9 开头
2. 机器人使用 Telethon 协议登录，需配置 API_ID/API_HASH
3. 支持代理轮换（SOCKS5），防限流
4. 原旧文件备份在 `_old/` 目录中