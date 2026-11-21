@echo off
cd /d "%~dp0"
if exist "%~dp0AUTO-MAS.exe" (
    start "" "%~dp0AUTO-MAS.exe" %*
    exit /b
)
if exist "%~dp0python\pythonw.exe" (
    start "" "%~dp0python\pythonw.exe" "%~dp0qt\main.py" %*
    exit /b
)
if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0qt\main.py" %*
    exit /b
)
echo [AUTO-MAS] Missing Python environment. Run Install-AUTO-MAS.bat first.
exit /b 1
