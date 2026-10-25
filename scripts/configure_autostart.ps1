#Requires -Version 5.1
# 以交互式登录任务启动托盘，保证远程桌面及界面处于当前用户会话。
param([switch]$Disable)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot)).TrimEnd('\')
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $arguments = '-NoProfile -File "' + $PSCommandPath + '"'
    if ($Disable) { $arguments += ' -Disable' }
    $process = Start-Process powershell.exe -Verb RunAs -ArgumentList $arguments -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw '设置开机自启失败，请检查管理员窗口中的错误。' }
    return
}
$hash = [Security.Cryptography.SHA256]::Create()
try {
    $key = [BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($root.ToLowerInvariant()))).Replace('-', '').Substring(0, 16)
} finally { $hash.Dispose() }
$taskName = 'AUTO-MAS-Startup-' + $key
if ($Disable) {
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existing) { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false }
    Write-Host '已关闭此目录的登录自启。'
    return
}
$exe = Join-Path $root 'AUTO-MAS.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "未找到程序：$exe" }
$user = $identity.User.Value
$action = New-ScheduledTaskAction -Execute $exe -Argument '--no-browser' -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$taskPrincipal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $taskPrincipal -Settings $settings -Description 'AUTO-MAS 当前用户登录后启动托盘及后端，不自动弹出浏览器。' -Force | Out-Null
Write-Host "已开启登录自启：$taskName"
Write-Host '不会立即启动程序。原配置中的定时队列仍会按计划执行。'
