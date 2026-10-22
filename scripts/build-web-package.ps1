#Requires -Version 5.1
<# 构建 Node.js + 浏览器 + Python 源码包，不启动或修改本机服务。 #>
param()
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root 'frontend\dist\win-unpacked'
if (Test-Path -LiteralPath $target) { throw "输出目录已存在，请先归档或移走：$target" }
foreach ($relative in @('frontend\dist-browser\browser.html', 'frontend\dist-host\services.cjs')) {
    if (!(Test-Path -LiteralPath (Join-Path $root $relative))) { throw "请先运行 yarn build:web：缺少 $relative" }
}
New-Item -ItemType Directory -Path $target -Force | Out-Null
# 只从版本库白名单收集源码和资源，不携带配置、凭据、日志或临时文件。
$files = & git -c "safe.directory=$($root.Replace('\','/'))" -C $root ls-files
if ($LASTEXITCODE -ne 0) { throw '无法读取源码文件列表' }
foreach ($relative in $files) {
    if ($relative -notmatch '^(app/|res/|plugins/(auto_mas_core|okww_adapter|ok_script_adapter)/|main\.py$|pyproject\.toml$|uv\.lock$|LICENSE$|scripts/install_release\.ps1$|README-RELEASE\.md$|Start-AUTO-MAS\.bat$)') { continue }
    if ($relative -match '(^|/)(__pycache__|tests?)(/|$)|\.py[co]$|\.test\.') { continue }
    $destination = Join-Path $target $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $root $relative) -Destination $destination -Force
}
$frontendTarget = Join-Path $target 'frontend'
New-Item -ItemType Directory -Path (Join-Path $frontendTarget 'web') -Force | Out-Null
foreach ($folder in @('dist-browser', 'dist-host')) {
    Copy-Item -LiteralPath (Join-Path $root "frontend\$folder") -Destination $frontendTarget -Recurse
}
Copy-Item -LiteralPath (Join-Path $root 'frontend\server.js') -Destination $frontendTarget
$modulesTarget = Join-Path $frontendTarget 'node_modules'
New-Item -ItemType Directory -Path $modulesTarget -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $root 'frontend\node_modules\adm-zip') -Destination $modulesTarget -Recurse
foreach ($file in @('host.cjs', 'runtimeLogs.cjs')) {
    Copy-Item -LiteralPath (Join-Path $root "frontend\web\$file") -Destination (Join-Path $frontendTarget 'web')
}
$node = (Get-Command node.exe -ErrorAction Stop).Source
New-Item -ItemType Directory -Path (Join-Path $target 'node') -Force | Out-Null
Copy-Item -LiteralPath $node -Destination (Join-Path $target 'node\node.exe')
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (!(Test-Path -LiteralPath $csc)) { throw '缺少系统 .NET Framework C# 编译器' }
$icon = Join-Path $root 'res\icons\AUTO-MAS.ico'
$common = @('/nologo', '/codepage:65001', '/target:winexe', '/platform:x64', '/optimize+', "/win32icon:$icon", '/r:System.dll', '/r:System.Core.dll', '/r:System.Drawing.dll', '/r:System.Windows.Forms.dll')
$hostOutput = Join-Path $target 'res\ChildSessionHost\AutoMas.ChildSessionHost.exe'
$hostSources = @(Get-ChildItem -LiteralPath (Join-Path $root 'res\ChildSessionHost') -Filter '*.cs' | ForEach-Object { $_.FullName })
& $csc @common "/out:$hostOutput" '/r:Microsoft.CSharp.dll' @hostSources
if ($LASTEXITCODE -ne 0) { throw '远程桌面宿主编译失败' }
$launcherOutput = Join-Path $target 'AUTO-MAS.exe'
$launcherSource = Join-Path $root 'res\Launcher\AutoMasLauncher.cs'
& $csc @common "/out:$launcherOutput" '/r:System.Web.Extensions.dll' $launcherSource
if ($LASTEXITCODE -ne 0) { throw '托盘启动器编译失败' }
@'
本包使用 Node.js + 本机浏览器 + Python 3.12 后端。
首次使用请先安装 Python 3.12，再运行 scripts\install_release.ps1 -NoLaunch 安装依赖。
随后双击 AUTO-MAS.exe。已有用户保留原 config、history 与 Python 环境。
'@ | Set-Content -LiteralPath (Join-Path $target '使用说明.txt') -Encoding UTF8
Write-Host "浏览器版本已打包：$target"
