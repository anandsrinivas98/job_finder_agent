# PowerShell script to register a daily Windows Scheduled Task
# Run this once in PowerShell as Administrator

$TaskName = "DailyAIJobHunter"
$PythonPath = (Get-Command python.exe).Source
$ScriptPath = Join-Path $PSScriptRoot "main.py"
$WorkingDirectory = $PSScriptRoot

Write-Host "Registering Daily Scheduled Task: $TaskName" -ForegroundColor Cyan
Write-Host "Python Path: $PythonPath"
Write-Host "Script: $ScriptPath"

# Trigger: Run daily at 07:00 AM
$Trigger = New-ScheduledTaskTrigger -Daily -At "07:00AM"

# Action: Run Python main.py --run-now
$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument "`"$ScriptPath`" --run-now" -WorkingDirectory $WorkingDirectory

# Settings: Start when available, stop after 2 hours
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)

# Register Scheduled Task
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Daily AI Job Hunter Autonomous Engine" -Force

Write-Host "`n✅ Successfully scheduled Daily Job Hunter! It will run every morning at 07:00 AM." -ForegroundColor Green
Write-Host "To test it immediately, run: Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Yellow
