#Requires -Version 5.1
<#
.SYNOPSIS
    AUTO-MAS (BetterGI 本地远程桌面重构版) 一键安装部署脚本 (仅需运行一次)
.DESCRIPTION
    1. 使用 Windows 10/11 系统自带的 .NET 编译器 (csc.exe) 编译：
       - `res/ChildSessionHost/AutoMas.ChildSessionHost.exe`（复刻 BGI 远程桌面 UI，默认托盘静默运行）
       - `AUTO-MAS.exe`（原生无黑框系统托盘启动器，支持 Node.js 打开浏览器或命令行无窗口直跑）
    2. 自动检测并配置 Python 运行环境与依赖（支持 uv / venv / 系统 Python）。
    3. 初始化默认配置文件 `config/Config.json`（开启本地远程桌面与默认托盘隐藏模式）。
    4. 创建桌面快捷方式（`AUTO-MAS 控制台` 与 `AUTO-MAS 无窗口静默运行`）。
#>

param(
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $RootDir

$VenvPython = Join-Path $RootDir ".venv\Scripts\python.exe"
$LocalPython = Get-ChildItem -LiteralPath (Join-Path $RootDir ".python") -Directory -Filter "cpython-3.12*" -ErrorAction SilentlyContinue |
    ForEach-Object { Join-Path $_.FullName "python.exe" } |
    Where-Object { Test-Path -LiteralPath $_ } |
    Select-Object -First 1
$PythonExe = if (Test-Path -LiteralPath $VenvPython) {
    $VenvPython
} elseif ($LocalPython) {
    $LocalPython
} else {
    "python"
}
$PythonVersion = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0 -or $PythonVersion -ne "3.12") {
    throw "安装需要 Python 3.12；当前检测到 $PythonVersion。请安装 Python 3.12 并重建 .venv。"
}

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  AUTO-MAS · BetterGI 本地远程桌面重构版 一键安装程序" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

# 1. 查找 Windows 内置 C# 编译器 (csc.exe)
$WinDir = $env:WINDIR
if (-not $WinDir) { $WinDir = "C:\Windows" }
$CscCandidates = @(
    (Join-Path $WinDir "Microsoft.NET\Framework64\v4.0.30319\csc.exe"),
    (Join-Path $WinDir "Microsoft.NET\Framework\v4.0.30319\csc.exe")
)
$CscExe = $CscCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

$IconPath = Join-Path $RootDir "res\icons\AUTO-MAS.ico"
$IconArg = if (Test-Path -LiteralPath $IconPath) { "/win32icon:`"$IconPath`"" } else { "" }

if ($CscExe) {
    Write-Host "[1/4] 正在使用系统内置编译器编译 BetterGI 风格远程桌面宿主 (AutoMas.ChildSessionHost.exe)..." -ForegroundColor Yellow
    $HostDir = Join-Path $RootDir "res\ChildSessionHost"
    $HostOut = Join-Path $HostDir "AutoMas.ChildSessionHost.exe"
    $CsFiles = Get-ChildItem -LiteralPath $HostDir -Filter "*.cs" | ForEach-Object { $_.FullName }

    $CscArgs = @(
        "/nologo",
        "/codepage:65001",
        "/target:winexe",
        "/platform:x64",
        "/optimize+",
        "/out:$HostOut",
        "/r:System.dll",
        "/r:System.Core.dll",
        "/r:System.Drawing.dll",
        "/r:System.Windows.Forms.dll",
        "/r:Microsoft.CSharp.dll"
    )
    if ($IconArg) { $CscArgs += $IconArg }
    $CscArgs += $CsFiles

    & $CscExe @CscArgs
    if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $HostOut)) {
        Write-Host "  -> 成功生成远程桌面宿主: $HostOut" -ForegroundColor Green
    } else {
        throw "csc.exe 编译远程桌面宿主失败，请检查上方错误。"
    }

    Write-Host "[2/4] 正在编译原生无窗口托盘启动器 (AUTO-MAS.exe)..." -ForegroundColor Yellow
    $LauncherCs = Join-Path $RootDir "res\Launcher\AutoMasLauncher.cs"
    $LauncherOut = Join-Path $RootDir "AUTO-MAS.exe"
    $LauncherArgs = @(
        "/nologo",
        "/codepage:65001",
        "/target:winexe",
        "/platform:x64",
        "/optimize+",
        "/out:$LauncherOut",
        "/r:System.dll",
        "/r:System.Core.dll",
        "/r:System.Drawing.dll",
        "/r:System.Windows.Forms.dll",
        "/r:System.Web.Extensions.dll"
    )
    if ($IconArg) { $LauncherArgs += $IconArg }
    $LauncherArgs += $LauncherCs

    & $CscExe @LauncherArgs
    if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $LauncherOut)) {
        Write-Host "  -> 成功生成启动器: $LauncherOut" -ForegroundColor Green
    } else {
        throw "csc.exe 编译启动器失败，请检查上方错误。"
    }
} else {
    throw "缺少可用的 .NET Framework C# 编译器；请安装 .NET Framework 开发工具后重试。"
}

# 2. 配置 Python 运行环境
Write-Host "[3/4] 正在检查并配置 Python 依赖环境..." -ForegroundColor Yellow
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "  -> 检测到 uv，正在同步虚拟环境..." -ForegroundColor Cyan
    uv sync
    if ($LASTEXITCODE -ne 0) { throw "uv sync 失败，请检查上方错误。" }
} else {
    if (-not (Test-Path -LiteralPath (Join-Path $RootDir ".venv\Scripts\python.exe"))) {
        Write-Host "  -> 正在创建 .venv 虚拟环境并安装核心依赖..." -ForegroundColor Cyan
        & $PythonExe -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "创建 Python 虚拟环境失败。" }
    }
    & $VenvPython -m pip --version > $null 2>&1
    if ($LASTEXITCODE -ne 0) {
        & $VenvPython -m ensurepip --upgrade
        if ($LASTEXITCODE -ne 0) { throw "无法为虚拟环境安装 pip。" }
    }
    & $VenvPython -m pip install -r (Join-Path $RootDir "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "安装 Python 依赖失败，请检查上方错误。" }
}

# 3. 初始化默认配置 (默认开启远程桌面且默认托盘隐藏运行)
$ConfigDir = Join-Path $RootDir "config"
if (-not (Test-Path -LiteralPath $ConfigDir)) {
    New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null
}
$ConfigJsonPath = Join-Path $ConfigDir "Config.json"
if (-not (Test-Path -LiteralPath $ConfigJsonPath)) {
    $DefaultConfig = @{
        ChildSession = @{
            Enabled = $true
            HostPort = 36165
            Resolution = "2560x1440"
            WatchMode = $true
            AudioMuted = $true
            StartHidden = $true
            WaitExternalLease = $true
        }
        Hotkey = @{
            Enabled = $true
            ToggleStartStop = "Ctrl+Alt+S"
            PreviousTask = "Ctrl+Alt+Left"
            NextTask = "Ctrl+Alt+Right"
        }
    } | ConvertTo-Json -Depth 5
    Set-Content -LiteralPath $ConfigJsonPath -Value $DefaultConfig -Encoding UTF8
    Write-Host "  -> 已生成默认配置 config/Config.json（远程桌面默认托盘运行已启用）" -ForegroundColor Green
}

# 4. 创建桌面快捷方式
Write-Host "[4/4] 正在创建桌面快捷方式..." -ForegroundColor Yellow
try {
    $WshShell = New-Object -ComObject WScript.Shell
    $DesktopDir = [Environment]::GetFolderPath("Desktop")
    $TargetExe = if (Test-Path -LiteralPath (Join-Path $RootDir "AUTO-MAS.exe")) {
        Join-Path $RootDir "AUTO-MAS.exe"
    } else {
        Join-Path $RootDir "Start-AUTO-MAS.bat"
    }

    $Shortcut1 = $WshShell.CreateShortcut((Join-Path $DesktopDir "AUTO-MAS 控制台.lnk"))
    $Shortcut1.TargetPath = $TargetExe
    $Shortcut1.WorkingDirectory = $RootDir
    if (Test-Path -LiteralPath $IconPath) { $Shortcut1.IconLocation = $IconPath }
    $Shortcut1.Description = "启动 AUTO-MAS（Node.js 调用系统浏览器打开控制台，远程桌面在托盘静默运行）"
    $Shortcut1.Save()

    $Shortcut2 = $WshShell.CreateShortcut((Join-Path $DesktopDir "AUTO-MAS 静默后台运行.lnk"))
    $Shortcut2.TargetPath = if (Test-Path -LiteralPath (Join-Path $RootDir "AUTO-MAS.exe")) {
        Join-Path $RootDir "AUTO-MAS.exe"
    } else {
        Join-Path $RootDir "Start-Headless.bat"
    }
    $Shortcut2.Arguments = "--headless --auto-run"
    $Shortcut2.WorkingDirectory = $RootDir
    if (Test-Path -LiteralPath $IconPath) { $Shortcut2.IconLocation = $IconPath }
    $Shortcut2.Description = "无窗口直接运行 AUTO-MAS 默认队列（不开浏览器窗口，远程桌面托盘运行）"
    $Shortcut2.Save()

    Write-Host "  -> 已在桌面创建快捷方式：「AUTO-MAS 控制台」与「AUTO-MAS 静默后台运行」" -ForegroundColor Green
} catch {
    throw "创建桌面快捷方式失败: $_"
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "  安装完成！后续使用无需再次安装：" -ForegroundColor Green
Write-Host "  1. 双击桌面【AUTO-MAS 控制台】或运行 Start-AUTO-MAS.bat 即可通过浏览器管理；" -ForegroundColor White
Write-Host "  2. 双击【AUTO-MAS 静默后台运行】或运行 Start-Headless.bat --auto-run 即可无窗口直接运行；" -ForegroundColor White
Write-Host "  3. 本地远程桌面默认最小化在系统托盘运行，双击托盘图标可呼出 BGI 风格远程桌面窗口。" -ForegroundColor White
Write-Host "================================================================" -ForegroundColor Green

if (-not $NoLaunch) {
    Write-Host "正在为您启动 AUTO-MAS..." -ForegroundColor Cyan
    if (Test-Path -LiteralPath (Join-Path $RootDir "AUTO-MAS.exe")) {
        Start-Process -FilePath (Join-Path $RootDir "AUTO-MAS.exe") -WorkingDirectory $RootDir
    } else {
        Start-Process -FilePath (Join-Path $RootDir "Start-AUTO-MAS.bat") -WorkingDirectory $RootDir
    }
}
