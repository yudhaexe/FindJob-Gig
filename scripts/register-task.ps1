# Registers a Windows Task Scheduler entry that runs due schedules every 30 minutes,
# even when the app is closed. Remove with: schtasks /Delete /TN FindJobGig /F
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { Write-Error "Run 'npm i' first (backend\.venv not found)."; exit 1 }
$backend = Join-Path $root "backend"
$action = New-ScheduledTaskAction -Execute $python -Argument "-m scraper.cli schedule run-due" -WorkingDirectory $backend
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "FindJobGig" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "Registered 'FindJobGig' (every 30 min). Check with: fjg schedule status"
