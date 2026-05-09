#!/bin/bash
set -euo pipefail

DEPLOY_DIR="/mnt/c/workspace/TeleBot/local-deploy/bot-telegram"
cd "$DEPLOY_DIR"
echo "开始自动部署：$(date)" | tee /tmp/deploy_log.txt

# 启动Docker daemon（后台运行）
echo "[1/7] 启动Docker..." | tee -a /tmp/deploy_log.txt
sudo service docker start 2>>/tmp/deploy_log.txt || sudo service docker restart 2>>/tmp/deploy_log.txt
sleep 3

# 拉取所有镜像（后台下载）
echo "[2/7] 拉取镜像（后台）..." | tee -a /tmp/deploy_log.txt
sudo docker pull mysql:8.0 2>&1 | tee -a /tmp/deploy_log.txt &
sudo docker pull redis:7-alpine 2>&1 | tee -a /tmp/deploy_log.txt &
sudo docker pull nginx:alpine 2>&1 | tee -a /tmp/deploy_log.txt &
wait

# 构建本地镜像
echo "[3/7] 构建本地镜像..." | tee -a /tmp/deploy_log.txt
sudo docker build -t telebot-backend:local ./backend 2>&1 | tee -a /tmp/deploy_log.txt
sudo docker build -t telebot-bot:local ./bot 2>&1 | tee -a /tmp/deploy_log.txt

# 启动所有服务
echo "[4/7] 启动所有服务..." | tee -a /tmp/deploy_log.txt
sudo docker-compose up -d 2>&1 | tee -a /tmp/deploy_log.txt

# 等待服务启动
echo "[5/7] 等待服务就绪..." | tee -a /tmp/deploy_log.txt
for i in $(seq 1 12); do
    if curl -s http://localhost:8000/health 2>/dev/null | grep -q "ok"; then
        echo "后端已就绪！尝试次数：$i" | tee -a /tmp/deploy_log.txt
        break
    fi
    echo "等待中 ($i/12)..." | tee -a /tmp/deploy_log.txt
    sleep 5
done

# 验证所有服务
echo "[6/7] 验证服务状态..." | tee -a /tmp/deploy_log.txt
echo "=== 容器状态 ===" | tee -a /tmp/deploy_log.txt
sudo docker-compose ps 2>&1 | tee -a /tmp/deploy_log.txt
echo "=== 后端健康接口 ===" | tee -a /tmp/deploy_log.txt
curl -s http://localhost:8000/health 2>&1 | tee -a /tmp/deploy_log.txt
echo "" | tee -a /tmp/deploy_log.txt
echo "=== 根路径 ===" | tee -a /tmp/deploy_log.txt
curl -s http://localhost:8000/ 2>&1 | tee -a /tmp/deploy_log.txt

echo "" | tee -a /tmp/deploy_log.txt
echo "=========================================" | tee -a /tmp/deploy_log.txt
if curl -s http://localhost:8000/health 2>/dev/null | grep -q "ok"; then
    echo "部署成功！$(date)" | tee -a /tmp/deploy_log.txt
else
    echo "部署可能完成但后端未响应，请检查：sudo docker-compose logs" | tee -a /tmp/deploy_log.txt
fi
echo "=========================================" | tee -a /tmp/deploy_log.txt