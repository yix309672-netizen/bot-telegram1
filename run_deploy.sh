#!/bin/bash
set -e
DEPLOY_DIR="/mnt/c/Users/Thikbook/Desktop/telegram-client-login-bot (1)/local-deploy"
cd "$DEPLOY_DIR"
LOG="/tmp/telebot_result.log"
echo "开始：$(date)" > $LOG

# 后台拉取镜像
echo "[1] 后台拉取镜像..." >> $LOG
sudo docker pull mysql:8.0 >> $LOG 2>&1 &
sudo docker pull redis:7 >> $LOG 2>&1 &
sudo docker pull nginx:alpine >> $LOG 2>&1 &
echo "[2] 等待镜像下载完成..." >> $LOG
wait
echo "[3] 镜像下载完成：$(date)" >> $LOG

# 构建本地镜像
echo "[4] 构建本地镜像..." >> $LOG
sudo docker build -t telebot-backend:local ./backend >> $LOG 2>&1
sudo docker build -t telebot-telegram-bot:local ./bot-telegram >> $LOG 2>&1
echo "[5] 构建完成：$(date)" >> $LOG

# 启动服务
echo "[6] 启动所有服务..." >> $LOG
sudo docker-compose up -d >> $LOG 2>&1
echo "[7] 服务已启动：$(date)" >> $LOG

# 等待后端就绪
echo "[8] 等待后端启动（最多60秒）..." >> $LOG
for i in $(seq 1 12); do
    if curl -s http://localhost:8000/health 2>/dev/null | grep -q "ok"; then
        echo "后端就绪！尝试次数：$i" >> $LOG
        break
    fi
    echo "等待中 ($i/12)..." >> $LOG
    sleep 5
done

# 验证结果
echo "" >> $LOG
echo "=== 容器状态 ===" >> $LOG
sudo docker-compose ps >> $LOG 2>&1
echo "" >> $LOG
echo "=== 后端健康检查 ===" >> $LOG
curl -s http://localhost:8000/health >> $LOG 2>&1
echo "" >> $LOG
echo "=== 根路径 ===" >> $LOG
curl -s http://localhost:8000/ >> $LOG 2>&1
echo "" >> $LOG
echo "=== 所有日志 ===" >> $LOG
sudo docker-compose logs --tail=10 >> $LOG 2>&1
echo "" >> $LOG
echo "=======================================" >> $LOG
if curl -s http://localhost:8000/health 2>/dev/null | grep -q "ok"; then
    echo "部署成功！$(date)" >> $LOG
else
    echo "后端未响应，请检查：sudo docker-compose logs" >> $LOG
fi
echo "=======================================" >> $LOG
echo "完成：$(date)" >> $LOG