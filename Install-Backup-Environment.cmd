@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -File "%~dp0scripts\install_backup_env.ps1"
if errorlevel 1 echo [AUTO-MAS] Installation failed. See errors above.
pause
