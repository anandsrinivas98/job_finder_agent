# PowerShell script to register a daily Windows Scheduled Task
# Run this once in PowerShell as Administrator

$TaskName = "DailyAIJobHunter"
$PythonPath = (Get-Command python.exe).Source
$ScriptPath = Join-Path $PSScriptRoot "main.py"
$WorkingDirectory = $PSScriptRoot

Write-Host "Registering Daily Scheduled Task: $TaskName" -ForegroundColor Cyan
Write-Host "Python Path: $PythonPath"
Write-Host "Script: $ScriptPath"

# Trigger: Run daily at 08:00 AM
$Trigger = New-ScheduledTaskTrigger -Daily -At "08:00AM"

# Action: Run Python main.py --run-now
$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument "`"$ScriptPath`" --run-now" -WorkingDirectory $WorkingDirectory

# Settings
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Register Task
Register-ScheduledTask -TaskName $TaskName -Trigger $Trigger -Action $Action -Settings $Settings -Description "Automated Daily AI Job Hunting Agent" -Force

Write-Host "`n✅ Successfully scheduled Daily Job Hunter! It will run every morning at 08:00 AM." -ForegroundColor Green
Write-Host "To test it immediately, run: Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Yellow
