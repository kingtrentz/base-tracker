@echo off
title Base Tracker auto-update setup
cd /d "%~dp0"
findstr /c:"PASTE_TOKEN_HERE" github_token.txt >nul 2>nul
if not errorlevel 1 (
  echo Your GitHub token isn't in github_token.txt yet.
  echo Make a fine-grained token for kingtrentz/base-tracker with Contents: Read and write,
  echo paste it into github_token.txt, save, and run this again.
  pause
  exit /b 1
)
for /f "delims=" %%P in ('where pythonw') do (
  set "PYW=%%P"
  goto :found
)
:found
echo Running the first update...
python base_pull.py
if errorlevel 1 (
  echo The first update hit a problem. Open run_log.txt in this folder to see why.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$a=New-ScheduledTaskAction -Execute '%PYW%' -Argument '\"%~dp0base_pull.py\"' -WorkingDirectory '%~dp0'; $n=Get-Date; $start=$n.Date.AddHours($n.Hour).AddMinutes(2); while($start -le $n){$start=$start.AddMinutes(5)}; $t=New-ScheduledTaskTrigger -Once -At $start -RepetitionInterval (New-TimeSpan -Minutes 5); $s=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 4); Register-ScheduledTask -TaskName 'Base Tracker - auto-update' -Action $a -Trigger $t -Settings $s -Description 'Every-5-min Clash level pull & push alerts for kingtrentz/base-tracker' -Force | Out-Null; if($?){'Task created (every 5 min). First run: ' + $start.ToString('h:mm tt')}"
echo.
echo All set: https://kingtrentz.github.io/base-tracker/
pause
