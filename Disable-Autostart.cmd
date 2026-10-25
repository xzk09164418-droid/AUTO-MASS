@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -File "%~dp0scripts\configure_autostart.ps1" -Disable
if errorlevel 1 echo [AUTO-MAS] Failed to disable startup. See errors above.
pause
