# 空密码方案只在已启用独立保护且确认 UU 可用后安装；不设置或更改账户密码。
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Root, [switch]$Apply)
$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath($Root).TrimEnd('\')
if (-not $Apply) {
    Write-Output '待安装：验证本地账户空密码，配置控制台自动登录及当前用户登录后的 MAS 自启。需要 -Apply，且看门狗必须已运行。'
    exit
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not ([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw '需要管理员权限' }
if ($Root.Contains('"')) { throw '目录包含不支持的引号' }
$guard = & "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root 'scripts/rdp-recovery-guard.ps1') -Action Status -Root $Root
if ($LASTEXITCODE -ne 0 -or -not ($guard | ConvertFrom-Json).ready) { throw 'UU 验证与回退看门狗未就绪' }
$account = $identity.Name.Split('\')
if ($account.Count -ne 2 -or $account[0] -ne $env:COMPUTERNAME) { throw '此空密码方案仅适用于当前本地账户，不转换微软或域账户' }
$logonPath = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
if ((Get-Item -LiteralPath $logonPath).GetValueNames() -contains 'DefaultPassword') {
    throw '已有自动登录密码配置；为避免读取或覆盖凭据，停止自动配置，请先人工检查'
}
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class AutoMasBlankLogon {
    [DllImport("advapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    public static extern bool LogonUser(string user, string domain, string password, int type, int provider, out IntPtr token);
    [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr token);
}
'@
$token = [IntPtr]::Zero
if (-not [AutoMasBlankLogon]::LogonUser($account[1], $account[0], '', 2, 0, [ref]$token)) {
    throw '空密码本地登录验证失败；不修改密码、不降低 RDP 身份验证要求'
}
[AutoMasBlankLogon]::CloseHandle($token) | Out-Null
$launcher = Join-Path $Root 'AUTO-MAS.exe'
if (Test-Path -LiteralPath $launcher) {
    $action = New-ScheduledTaskAction -Execute $launcher -WorkingDirectory $Root
} else {
    $batch = Join-Path $Root 'Start-AUTO-MAS.bat'
    if (-not (Test-Path -LiteralPath $batch)) { throw '找不到 MAS 启动入口' }
    $action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\cmd.exe" -Argument ('/d /c ""' + $batch + '""') -WorkingDirectory $Root
}
$principal = New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Highest
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity.Name
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName 'AUTO-MAS_AutoStart' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
New-ItemProperty -LiteralPath $logonPath -Name DefaultUserName -Value $account[1] -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $logonPath -Name DefaultDomainName -Value $account[0] -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $logonPath -Name DefaultPassword -Value '' -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $logonPath -Name AutoAdminLogon -Value '1' -PropertyType String -Force | Out-Null
Write-Output '空密码自动登录与 MAS 登录自启已配置；尚未经过重启验收。未修改账户密码、NLA 或 UU。'
