# 部署指南：TelegramWeb（前端静态 + FastAPI/DRF 后端）

- 使用 Docker Compose 一次性部署前后端、数据库、缓存、队列、前端
- 使用 Let's Encrypt 提供 TLS 证书
- Nginx 作为 TLS 终止与反向代理
- 后端提供备份导入、JSON 导入等 API

部署步骤请参考以下要点：
- 1) 安装 Docker 与 Docker Compose
- 2) 将域名解析指向服务器 IP
- 3) 获取 TLS 证书：certbot --nginx -d your-domain.com
- 4) docker-compose up -d
- 5) 访问 https://your-domain.com