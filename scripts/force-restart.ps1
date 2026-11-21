#Requires -Version 5.1
param([Parameter(Mandatory=$true)][string]$Root, [switch]$PlanOnly, [ValidateSet('Qt')][string]$Frontend = 'Qt')
$ErrorActionPreference = 'Stop'
# 预检查失败也必须可见，避免助手尚未进入清理阶段就静默退出。
trap {
    if (!$PlanOnly) {
        Add-Type -AssemblyName System.Windows.Forms
        [Windows.Forms.MessageBox]::Show(('强制重启预检查失败：' + $_.Exception.Message), 'AUTO-MAS') | Out-Null
    }
    throw $_
}
$rootPath = (Resolve-Path -LiteralPath $Root).Path.TrimEnd('\')
$launcher = Join-Path $rootPath 'AUTO-MAS.exe'
$recovery = Join-Path $rootPath 'data\desktop_recovery'
$runtimeNames = @('external-processes', 'desktop_recovery', 'child_session_jobs', 'queue-control-notices', 'hotkey-capture.json', 'hotkey-capture-relay.json', 'hotkey-relay-status.json', 'hotkey-relay-status.tmp')
$runtimePaths = @($runtimeNames | ForEach-Object { Join-Path $rootPath ('data\' + $_) })
$configPath = Join-Path $rootPath 'config\Config.json'
$config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
$rdpEnabled = $config.ChildSession.Enabled -eq $true
# 只认本安装的完整入口路径，不按通用进程名结束其他软件。
$entries = @((Join-Path $rootPath 'main.py'), (Join-Path $rootPath 'qt\main.py'))
$hostExe = Join-Path $rootPath 'res\ChildSessionHost\AutoMas.ChildSessionHost.exe'
$inventory = @(Get-CimInstance Win32_Process)
$selected = @{}
$python = @((Join-Path $rootPath 'python\python.exe'), (Join-Path $rootPath '.venv\Scripts\python.exe')) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (!$python) { throw 'Python runtime required for external occupancy cleanup' }
if ($Frontend -eq 'Qt' -and !(Test-Path -LiteralPath (Join-Path $rootPath 'qt\main.py') -PathType Leaf)) { throw 'Missing Qt frontend' }
$stateTool = Join-Path $PSScriptRoot 'force-restart-state.py'
$planText = & $python $stateTool plan --root $rootPath
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect external occupancy records' }
$externalPlan = ($planText -join "`n") | ConvertFrom-Json
$externalWarnings = @($externalPlan.warnings)
$protectedIds = @($PID)
$ancestorId = $PID
while ($ancestorId) {
    $ancestor = $inventory | Where-Object { $_.ProcessId -eq $ancestorId } | Select-Object -First 1
    if (!$ancestor -or !$ancestor.ParentProcessId -or $protectedIds -contains [int]$ancestor.ParentProcessId) { break }
    $ancestorId = [int]$ancestor.ParentProcessId
    $protectedIds += $ancestorId
}
# 已登记身份必须同时匹配 PID、创建时间和会话，不能按调用方名称猜测进程。
foreach ($identity in $externalPlan.processes) {
    $item = $inventory | Where-Object { $_.ProcessId -eq $identity.pid } | Select-Object -First 1
    if (!$item) { continue }
    $created = ([DateTimeOffset]$item.CreationDate).ToUnixTimeMilliseconds() / 1000.0
    if ([Math]::Abs($created - [double]$identity.createdAt) -gt 0.01 -or $item.SessionId -ne $identity.sessionId -or $item.SessionId -eq 0 -or $protectedIds -contains [int]$item.ProcessId -or $item.Name -match '^(mumuremote|uuconsolegate)' -or $item.ExecutablePath -eq $launcher) {
        $externalWarnings += ('未结束外部程序（身份不一致或属于保护进程）：' + $identity.caller)
        continue
    }
    $selected[[int]$item.ProcessId] = $item
}
foreach ($item in $inventory) {
    $owned = $item.ExecutablePath -eq $launcher -or ($rdpEnabled -and $item.ExecutablePath -eq $hostExe)
    if ($item.Name -match '^(pythonw?|node)\.exe$') {
        foreach ($entry in $entries) {
            if ($item.CommandLine -match ('(?:^|[\s"])' + [regex]::Escape($entry) + '(?:"|\s|$)')) { $owned = $true }
        }
    }
    if ($owned) { $selected[[int]$item.ProcessId] = $item }
}
# 快照扩展进程树，排除独立助手自身；先停父进程，避免继续派生或回写恢复记录。
do {
    $added = $false
    foreach ($item in $inventory) {
        if ($protectedIds -contains [int]$item.ProcessId -or $item.Name -match '^(mumuremote|uuconsolegate)' -or $selected.ContainsKey([int]$item.ProcessId)) { continue }
        if ($selected.ContainsKey([int]$item.ParentProcessId)) {
            $parent = $selected[[int]$item.ParentProcessId]
            if ($item.CreationDate -ge $parent.CreationDate) {
                $selected[[int]$item.ProcessId] = $item
                $added = $true
            }
        }
    }
} while ($added)
foreach ($directory in (@((Join-Path $rootPath 'data'), (Join-Path $rootPath 'data\force-restart-backups')) + $runtimePaths)) {
    if ((Test-Path -LiteralPath $directory) -and ((Get-Item -LiteralPath $directory).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Recovery paths must not be symbolic links or junctions' }
}
if ($PlanOnly) {
    [pscustomobject]@{root=$rootPath;rdpEnabled=$rdpEnabled;processIds=@($selected.Keys);recovery=$recovery;warnings=$externalWarnings} | ConvertTo-Json
    exit 0
}
$mutex = New-Object Threading.Mutex($false, ('Local\AUTO-MAS-force-' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($rootPath)).Replace('\','_').Replace('/','_')))
if (!$mutex.WaitOne(0)) { exit 0 }
$logDir = Join-Path $rootPath 'debug'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
try {
    foreach ($item in @($selected.Values | Sort-Object CreationDate)) {
        $current = Get-CimInstance Win32_Process -Filter "ProcessId=$($item.ProcessId)"
        if ($current -and $current.CreationDate -eq $item.CreationDate) {
            Stop-Process -Id $item.ProcessId -Force -ErrorAction Stop
        }
    }
    foreach ($item in $selected.Values) {
        $running = Get-Process -Id $item.ProcessId -ErrorAction SilentlyContinue
        if ($running -and !$running.WaitForExit(10000)) { throw "Process did not exit: $($item.ProcessId)" }
    }
    if ($rdpEnabled) {
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class MasForceSession {
 [DllImport("wtsapi32.dll", SetLastError=true)] public static extern bool WTSGetChildSessionId(out uint id);
 [DllImport("wtsapi32.dll", SetLastError=true)] public static extern bool WTSLogoffSession(IntPtr server,uint id,bool wait);
}
"@
        [uint32]$sessionId = 0
        if ([MasForceSession]::WTSGetChildSessionId([ref]$sessionId)) {
            if ($sessionId -ne [uint32]::MaxValue -and ![MasForceSession]::WTSLogoffSession([IntPtr]::Zero,$sessionId,$true)) { throw 'Cannot log off MAS child session' }
        } elseif ([Runtime.InteropServices.Marshal]::GetLastWin32Error() -ne 1168) { throw 'Cannot query MAS child session' }
    }
    $backup = Join-Path $rootPath ('data\force-restart-backups\' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    & $python $stateTool reset --root $rootPath --backup $backup
    if ($LASTEXITCODE -ne 0) { throw 'External occupancy reset failed; old state retained in backup' }
    # 只移走明确的运行数据；日志、配置、历史、缓存和看门狗均保持原样。
    foreach ($runtimePath in $runtimePaths) {
        if (!(Test-Path -LiteralPath $runtimePath)) { continue }
        $resolved = (Resolve-Path -LiteralPath $runtimePath).Path
        if ($resolved -ne $runtimePath -or ((Get-Item -LiteralPath $resolved).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Unsafe runtime state path' }
        Move-Item -LiteralPath $resolved -Destination (Join-Path $backup (Split-Path $runtimePath -Leaf))
    }
    # 不转发旧启动参数和恢复环境变量；正常启动及普通重启完全不走本路径。
    Remove-Item Env:AUTO_MAS_DESKTOP_RECOVERY -ErrorAction SilentlyContinue
    $pythonw = Join-Path (Split-Path $python -Parent) 'pythonw.exe'
    if (!(Test-Path -LiteralPath $pythonw)) { $pythonw = $python }
    Start-Process -FilePath $pythonw -ArgumentList ('"' + (Join-Path $rootPath 'qt\main.py') + '"') -WorkingDirectory $rootPath -WindowStyle Hidden
    (@('Force restart completed; old runtime state archived.') + $externalWarnings) | Set-Content -LiteralPath (Join-Path $logDir 'force-restart.log') -Encoding UTF8
    if ($externalWarnings.Count -gt 0) {
        Add-Type -AssemblyName System.Windows.Forms
        [Windows.Forms.MessageBox]::Show(("占用已清除并重新启动，但以下外部程序未能确认结束：`n" + ($externalWarnings -join "`n")), 'AUTO-MAS 强制重启报告') | Out-Null
    }
} catch {
    $_ | Out-String | Set-Content -LiteralPath (Join-Path $logDir 'force-restart.log') -Encoding UTF8
    Add-Type -AssemblyName System.Windows.Forms
    [Windows.Forms.MessageBox]::Show(('强制重启未完成，请查看 debug\force-restart.log。' + [Environment]::NewLine + $_.Exception.Message),'AUTO-MAS') | Out-Null
    exit 1
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
