#Requires -Version 5.1
# 为已编译的本机备份安装环境；不启动程序或改写用户配置。
param([string]$Wheelhouse)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

function Find-Python312 {
    $candidates = @(
        (Join-Path $root '.venv\Scripts\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Join-Path $env:ProgramFiles 'Python312\python.exe')
    )
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        $found = & $py.Source -3.12 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0) { $candidates += $found }
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) { $candidates += $python.Source }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            $version = & $candidate -c "import sys; print('%s.%s' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and $version -eq '3.12') { return $candidate }
        }
    }
    return $null
}

$python = Find-Python312
if (-not $python) {
    throw '未找到 Python 3.12。本构建不自动联网下载，请先使用离线安装包安装。'
}
$venv = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venv)) {
    & $python -m venv (Join-Path $root '.venv')
    if ($LASTEXITCODE -ne 0) { throw '创建 Python 环境失败。' }
}
if (-not $Wheelhouse) { $Wheelhouse = Join-Path $root 'offline-wheels' }
& $venv -m pip --version
if ($LASTEXITCODE -ne 0) {
    & $venv -m ensurepip
    if ($LASTEXITCODE -ne 0) { throw '当前 Python 缺少离线 pip，请补齐本地运行环境。' }
}
& $venv -m pip --disable-pip-version-check install --no-index --only-binary=:all: --find-links $Wheelhouse -r (Join-Path $root 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw '离线依赖安装失败，请补齐 offline-wheels 中的依赖包并检查上方错误。' }
& $venv -c "import fastapi,uvicorn,httpx,truststore,win32api; print('Python dependencies OK')"
if ($LASTEXITCODE -ne 0) { throw 'Python 依赖验证失败。' }
& $venv -m pip --disable-pip-version-check install --no-index --only-binary=:all: --find-links $Wheelhouse -r (Join-Path $root 'qt/requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Qt 离线依赖安装失败，请补齐 wheelhouse。' }
& (Join-Path $PSScriptRoot 'configure_autostart.ps1')
Write-Host '环境安装完成，已配置登录自启。可双击 AUTO-MAS.exe 立即启动，或运行 Disable-Autostart.cmd 关闭自启。'
