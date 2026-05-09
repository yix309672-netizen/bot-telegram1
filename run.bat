@echo off
cd /d C:\workspace\TeleBot\local-deploy\bot-telegram
echo Starting TeleBot deployment...
echo Please wait for 5-30 minutes depending on network speed...
wsl -d Ubuntu -e bash -c "cd '/mnt/c/workspace/TeleBot/local-deploy/bot-telegram' && chmod +x auto_deploy.sh && bash auto_deploy.sh" > deploy_log.txt 2>&1
echo.
echo Deployment command sent. Check deploy_log.txt for results.
echo When finished, run: type C:\workspace\TeleBot\local-deploy\bot-telegram\deploy_log.txt
pause