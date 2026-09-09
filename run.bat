@echo off
cd /d "%~dp0"
echo Starting TeleBot deployment...
echo Please wait for 5-30 minutes depending on network speed...
wsl -d Ubuntu -e bash -c "cd '/mnt/c/Users/39712/Desktop/bot-telegram1-main' && chmod +x auto_deploy.sh && bash auto_deploy.sh" > deploy_log.txt 2>&1
echo.
echo Deployment command sent. Check deploy_log.txt for results.
pause