@echo off
chcp 65001 >nul
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\uninstall_release.ps1" %*
set "result=%errorlevel%"
if not "%result%"=="0" echo [AUTO-MAS] 清理未完成，请检查上方错误信息。
pause
exit /b %result%
