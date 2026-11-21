@echo off
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

:: 无窗口静默启动模式：不弹出 Qt 窗口，远程桌面默认在系统托盘静默运行
:: 用法示例：
::   Start-Headless.bat --auto-run
::   Start-Headless.bat --run-queue first
::   Start-Headless.bat --run-script <ScriptUUID>

if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0qt\main.py" --headless %*
    exit /b
)

if exist "%~dp0.venv\Scripts\python.exe" (
    start "" /B "%~dp0.venv\Scripts\python.exe" "%~dp0qt\main.py" --headless %*
    exit /b
)

start "" /B python "%~dp0qt\main.py" --headless %*
