@echo off
chcp 65001 >nul
title AUTO-MAS 一键安装部署程序 (BetterGI 远程桌面重构版)

:: 自动请求管理员权限（启用 Windows Child Sessions 所需）
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo 正在请求管理员权限以完成首次安装与 Windows 远程桌面分身配置...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_release.ps1"
if errorlevel 1 echo [AUTO-MAS] 安装失败，请检查上方错误信息。
pause
