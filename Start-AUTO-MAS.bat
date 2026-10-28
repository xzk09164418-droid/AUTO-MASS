@echo off
:: 优先交给无窗口托盘启动器，批处理不再等待 Node.js 服务退出。
if exist "%~dp0AUTO-MAS.exe" (
    start "" "%~dp0AUTO-MAS.exe" %*
    exit /b
)

chcp 65001 >nul
cd /d "%~dp0"

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [AUTO-MAS] 缺少 Python 3.12 虚拟环境，请先运行 Install-AUTO-MAS.bat。
    exit /b 1
)
"%~dp0.venv\Scripts\python.exe" -c "import sys, fastapi; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [AUTO-MAS] 需要 Python 3.12 和完整依赖，请先运行 Install-AUTO-MAS.bat。
    exit /b 1
)

:: 若尚未编译远程桌面宿主，自动执行一次静默构建
if not exist "%~dp0res\ChildSessionHost\AutoMas.ChildSessionHost.exe" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_release.ps1" -NoLaunch
    if errorlevel 1 exit /b 1
)

:: 优先通过 Node.js 启动前后端分离服务并调用系统浏览器
where node >nul 2>&1
if %errorLevel% equ 0 (
    echo [AUTO-MAS] 正在通过 Node.js 启动前后端分离服务并打开系统浏览器...
    node "%~dp0frontend\server.js" %*
    exit /b
)

:: 无 Node 时仅启动后端，不能向未经身份核验的固定端口打开浏览器。
echo [AUTO-MAS] Node.js 不可用，仅启动后端；请安装 Node.js 后使用浏览器控制台。
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0main.py" %*
) else (
    python "%~dp0main.py" %*
)
