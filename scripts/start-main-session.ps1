param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class AutoMasConsoleSession {
    [DllImport("kernel32.dll")] public static extern uint WTSGetActiveConsoleSessionId();
}
'@
$current = [Diagnostics.Process]::GetCurrentProcess().SessionId
$console = [AutoMasConsoleSession]::WTSGetActiveConsoleSessionId()
$allowed = $console -ne [uint32]::MaxValue -and $current -eq $console
$desktopFree = $false
$mutex = New-Object Threading.Mutex($false, 'Global\AUTO-MAS-RDP-Desktop-Owner-v1')
try {
    try { $desktopFree = $mutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $desktopFree = $true }
    if ($desktopFree) { $mutex.ReleaseMutex() }
} finally { $mutex.Dispose() }
$allowed = $allowed -and $desktopFree
if ($CheckOnly) {
    @{ allowed=$allowed; currentSession=$current; consoleSession=$console; desktopFree=$desktopFree } | ConvertTo-Json -Compress
    exit 0
}
if (-not $allowed) { exit 0 }
$root = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot)).TrimEnd('\')
$exe = Join-Path $root 'AUTO-MAS.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "未找到程序：$exe" }
Start-Process -FilePath $exe -ArgumentList '--no-browser' -WorkingDirectory $root -WindowStyle Hidden | Out-Null
