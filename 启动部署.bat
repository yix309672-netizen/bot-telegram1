@echo off
chcp 65001 >nul
echo ========================================
echo TeleBot 全自动部署
echo ========================================
echo 开始时间: %date% %time%
echo.

echo 正在启动 Ubuntu 并执行部署脚本...
echo 如果需要密码，请输入你的 WSL 用户密码
echo.

wsl -d Ubuntu -e bash -c "cd '/mnt/c/workspace/TeleBot/local-deploy/bot-telegram' && chmod +x auto_deploy.sh && bash auto_deploy.sh 2>&1 | tee /tmp/deploy_log.txt"

echo.
echo ========================================
echo 部署执行完成
echo 检查日志: wsl -d Ubuntu -e bash -c "cat /tmp/deploy_log.txt"
echo ========================================
pause