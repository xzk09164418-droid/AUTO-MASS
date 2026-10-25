#Requires -Version 5.1
# 为已编译的本机备份安装环境；不启动程序或改写用户配置。
param()
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

function Install-WindowsPackage([string]$packageId) {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "缺少 winget。请先安装 Python 3.12（https://www.python.org/downloads/windows/）和 Node.js LTS（https://nodejs.org/），再运行本脚本。缺少的软件包：$packageId"
    }
    & $winget.Source install --id $packageId --exact --source winget --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "安装 $packageId 失败，退出码 $LASTEXITCODE" }
}

$python = Find-Python312
if (-not $python) {
    Install-WindowsPackage 'Python.Python.3.12'
    $python = Find-Python312
    if (-not $python) { throw '未找到 Python 3.12，请重新打开终端后重试。' }
}
$node = Get-Command node.exe -ErrorAction SilentlyContinue
$nodePath = if ($node) { $node.Source } else { Join-Path $env:ProgramFiles 'nodejs\node.exe' }
$nodeReady = $false
if (Test-Path -LiteralPath $nodePath) {
    & $nodePath -e "process.exit(Number(process.versions.node.split('.')[0]) >= 22 ? 0 : 1)"
    $nodeReady = $LASTEXITCODE -eq 0
}
if (-not $nodeReady) {
    Install-WindowsPackage 'OpenJS.NodeJS.LTS'
    $nodePath = Join-Path $env:ProgramFiles 'nodejs\node.exe'
    if (-not (Test-Path -LiteralPath $nodePath)) { throw '未找到 Node.js，请重新打开终端后重试。' }
}
$venv = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venv)) {
    & $python -m venv (Join-Path $root '.venv')
    if ($LASTEXITCODE -ne 0) { throw '创建 Python 环境失败。' }
}
& $venv -m pip install -r (Join-Path $root 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw '安装 Python 依赖失败，请检查网络及上方错误。' }
& $venv -c "import fastapi,uvicorn,httpx,truststore,win32api; print('Python dependencies OK')"
if ($LASTEXITCODE -ne 0) { throw 'Python 依赖验证失败。' }
& $nodePath -e "require('./frontend/node_modules/adm-zip'); console.log('Node dependency OK')"
if ($LASTEXITCODE -ne 0) { throw 'Node 运行依赖验证失败。' }
Write-Host '环境安装完成。请双击 AUTO-MAS.exe，并允许管理员授权。不会自动运行队列。'
