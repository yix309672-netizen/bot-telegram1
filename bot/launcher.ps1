$ErrorActionPreference = "Continue"
$botCmd = "C:\Users\39712\AppData\Local\Programs\Python\Python311\python.exe"
$botScript = "C:\Users\39712\Desktop\bot-telegram1-main\bot\bot.py"
$workDir = "C:\Users\39712\Desktop\bot-telegram1-main\bot"
$logFile = "C:\Users\39712\Desktop\bot-telegram1-main\bot\bot.log"
$errFile = "C:\Users\39712\Desktop\bot-telegram1-main\bot\bot-err.log"
$pidFile = "C:\Users\39712\Desktop\bot-telegram1-main\bot\bot.pid"
if (Test-Path $pidFile) {
    $oldPid = (Get-Content $pidFile -ErrorAction SilentlyContinue).Trim()
    if ($oldPid) {
        $alive = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
        if ($alive) { exit 0 }
    }
}
$proc = Start-Process -FilePath $botCmd -ArgumentList $botScript -WorkingDirectory $workDir -RedirectStandardOutput $logFile -RedirectStandardError $errFile -WindowStyle Hidden -PassThru
$proc.Id | Out-File -FilePath $pidFile -Encoding ascii