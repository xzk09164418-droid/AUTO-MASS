#Requires -Version 5.1
param([Parameter(Mandatory=$true)][string]$Root, [switch]$PlanOnly)
$ErrorActionPreference = 'Stop'
$rootPath = (Resolve-Path -LiteralPath $Root).Path.TrimEnd('\')
$launcher = Join-Path $rootPath 'AUTO-MAS.exe'
$recovery = Join-Path $rootPath 'data\desktop_recovery'
if (!(Test-Path -LiteralPath $launcher -PathType Leaf)) { throw 'Missing AUTO-MAS.exe' }
$configPath = Join-Path $rootPath 'config\Config.json'
$config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
$rdpEnabled = $config.ChildSession.Enabled -eq $true
# 只认本安装的完整入口路径，不按通用进程名结束其他软件。
$entries = @((Join-Path $rootPath 'main.py'), (Join-Path $rootPath 'frontend\server.js'))
$hostExe = Join-Path $rootPath 'res\ChildSessionHost\AutoMas.ChildSessionHost.exe'
$inventory = @(Get-CimInstance Win32_Process)
$selected = @{}
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
        if ($item.ProcessId -eq $PID -or $selected.ContainsKey([int]$item.ProcessId)) { continue }
        if ($selected.ContainsKey([int]$item.ParentProcessId)) {
            $parent = $selected[[int]$item.ParentProcessId]
            if ($item.CreationDate -ge $parent.CreationDate) {
                $selected[[int]$item.ProcessId] = $item
                $added = $true
            }
        }
    }
} while ($added)
foreach ($directory in @((Join-Path $rootPath 'data'), $recovery, (Join-Path $rootPath 'data\force-restart-backups'))) {
    if ((Test-Path -LiteralPath $directory) -and ((Get-Item -LiteralPath $directory).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Recovery paths must not be symbolic links or junctions' }
}
if ($PlanOnly) {
    [pscustomobject]@{root=$rootPath;rdpEnabled=$rdpEnabled;processIds=@($selected.Keys);recovery=$recovery} | ConvertTo-Json
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
    if (Test-Path -LiteralPath $recovery) {
        $resolved = (Resolve-Path -LiteralPath $recovery).Path
        if ($resolved -ne (Join-Path $rootPath 'data\desktop_recovery') -or ((Get-Item -LiteralPath $resolved).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Unsafe recovery directory' }
        $backup = Join-Path $rootPath ('data\force-restart-backups\' + [Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $backup -Force | Out-Null
        Move-Item -LiteralPath $resolved -Destination (Join-Path $backup 'desktop_recovery')
    }
    # 不转发旧启动参数和恢复环境变量；正常启动及普通重启完全不走本路径。
    Remove-Item Env:AUTO_MAS_DESKTOP_RECOVERY -ErrorAction SilentlyContinue
    Start-Process -FilePath $launcher -WorkingDirectory $rootPath -WindowStyle Hidden
    'Force restart completed; old recovery state archived.' | Set-Content -LiteralPath (Join-Path $logDir 'force-restart.log') -Encoding UTF8
} catch {
    $_ | Out-String | Set-Content -LiteralPath (Join-Path $logDir 'force-restart.log') -Encoding UTF8
    Add-Type -AssemblyName System.Windows.Forms
    [Windows.Forms.MessageBox]::Show(('强制重启未完成，请查看 debug\force-restart.log。' + [Environment]::NewLine + $_.Exception.Message),'AUTO-MAS') | Out-Null
    exit 1
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
