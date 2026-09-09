#!/bin/bash
# TLS 证书申请脚本（Let's Encrypt）
# 使用 certbot 为 DuckDNS 域名申请免费证书

set -e

DOMAIN="${DOMAIN:-telegramweb.duckdns.org}"
EMAIL="${EMAIL:-yix309672@gmail.com}"
CERTS_DIR="./certs"

echo "正在为域名 $DOMAIN 申请 Let's Encrypt 证书..."

# 检查 certbot 是否安装
if ! command -v certbot &> /dev/null; then
    echo "未找到 certbot，正在安装..."
    apt-get update && apt-get install -y certbot
fi

# 创建证书目录
mkdir -p "$CERTS_DIR"

# 使用 certbot 的独立模式申请证书
# 注意：需要暂时停止占用 80 端口的服务
certbot certonly \
    --standalone \
    --preferred-challenges http \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN"

# 复制证书到项目目录
if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$CERTS_DIR/"
    cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$CERTS_DIR/"
    echo "证书已保存到 $CERTS_DIR/"
else
    echo "证书申请失败，请检查域名解析和防火墙设置"
    exit 1
fi

echo "证书申请完成！"
echo "证书路径："
echo "  - 公钥: $CERTS_DIR/fullchain.pem"
echo "  - 私钥: $CERTS_DIR/privkey.pem"
