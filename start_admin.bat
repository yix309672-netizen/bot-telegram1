@echo off
chcp 65001 >nul
title TeleBot Admin Launcher
color 0A
echo ==========================================
echo   Telegram Backend - Launcher
echo ==========================================
echo.
tasklist /FI "IMAGENAME eq mysqld.exe" 2>nul | find /I "mysqld.exe" >nul
if %errorlevel% neq 0 (
    echo [INFO] MySQL not running, trying system service...
    net start | find /i "mysql" >nul && (net start mysql84 2>nul & net start mysql 2>nul)
    timeout /t 2 >nul
)
REM 服务方式起不来时，用项目自带数据目录直起 mysqld（已验证可用）
powershell -command "try { $c=New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',3306); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>nul
if %errorlevel% neq 0 (
    echo [INFO] starting local mysqld with project data...
    start "" /b "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe" --datadir="%~dp0mysql-data" --port=3306
    timeout /t 10 >nul
)
echo [OK] MySQL check done
echo.
echo Starting PHP server on 8080...
start "" /b "C:\Users\39712\AppData\Local\Microsoft\WinGet\Packages\PHP.PHP.8.1_Microsoft.Winget.Source_8wekyb3d8bbwe\php.exe" -S 127.0.0.1:8080 -t "C:\Users\39712\Desktop\bot-telegram1-main\admin\public" "C:\Users\39712\Desktop\bot-telegram1-main\admin\public\router.php"
echo.
echo PHP started, opening browser in 3s...
timeout /t 3 >nul
start "" http://127.0.0.1:8080/admin/login
echo.
echo ==========================================
echo   URL  : http://127.0.0.1:8080/admin/login
echo   Login: admin / admin
echo ==========================================
echo.
pause