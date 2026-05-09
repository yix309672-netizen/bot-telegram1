#!/bin/bash
# 一键部署脚本
# 用于本地 Docker Compose 部署

set -e

echo "=========================================="
echo "TeleBot 本地部署脚本"
echo "=========================================="

# 检查 Docker 和 Docker Compose
if ! command -v docker &> /dev/null; then
    echo "错误：未找到 Docker，请先安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "错误：未找到 docker-compose，请先安装"
    exit 1
fi

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "警告：未找到 .env 文件，将使用默认配置"
    echo "请复制 .env.template 为 .env 并填入你的配置"
    if [ -f .env.template ]; then
        echo "正在复制 .env.template 为 .env..."
        cp .env.template .env
    fi
fi

# 加载环境变量
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# 检查必要的环境变量
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "警告：未设置 TELEGRAM_BOT_TOKEN，机器人将无法启动"
fi

# 创建必要的目录
mkdir -p certs nginx/conf.d

# 启动服务
echo "正在启动 Docker 容器..."
docker-compose up -d --build

echo "等待服务启动..."
sleep 10

# 检查服务状态
echo "检查服务状态："
docker-compose ps

# 测试后端健康接口
echo ""
echo "测试后端健康接口："
if curl -s http://localhost:8000/health | grep -q "ok"; then
    echo "✅ 后端服务正常"
else
    echo "❌ 后端服务异常，请检查日志：docker-compose logs backend"
fi

echo ""
echo "=========================================="
echo "部署完成！"
echo "=========================================="
echo "后端 API: http://localhost:8000"
echo "健康检查: http://localhost:8000/health"
echo "查看日志: docker-compose logs -f"
echo "停止服务: docker-compose down"
echo ""
echo "DuckDNS 域名: ${DOMAIN:-telegramweb.duckdns.org}"
echo "证书申请: 运行 ./tls_setup.sh"
echo "=========================================="
