# 独立于 MAS 与 Child Session 的测试回退保护。Arm 必须由管理员显式执行。
[CmdletBinding()]
param(
    [ValidateSet('Prepare', 'Arm', 'Cancel', 'Status', 'DailyStatus', 'Watch')]
    [string]$Action = 'Status',
    [Parameter(Mandatory = $true)][string]$Root,
    [string]$Baseline,
    [string]$RunId,
    [switch]$UUVerified,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath($Root).TrimEnd('\')
$pointer = Join-Path $Root 'data/rdp_test_guard/active.json'

function Write-JsonAtomic($Path, $Value) {
    $temporary = $Path + '.' + [guid]::NewGuid().ToString('N') + '.tmp'
    try {
        [IO.File]::WriteAllText($temporary, ($Value | ConvertTo-Json -Depth 15), [Text.UTF8Encoding]::new($false))
        if (Test-Path -LiteralPath $Path) { [IO.File]::Replace($temporary, $Path, [NullString]::Value) }
        else { [IO.File]::Move($temporary, $Path) }
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary }
    }
}
function Read-Json($Path) { Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json }
function Get-Hash($Path) {
    if (Test-Path -LiteralPath $Path -PathType Leaf) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash }
    return $null
}
function Resolve-Target($Relative) {
    $target = [IO.Path]::GetFullPath((Join-Path $Root $Relative))
    if (-not $target.StartsWith($Root + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw '回退目标超出工作目录'
    }
    # 不允许恢复操作穿过符号链接或 junction。
    $part = $target
    while ($part -and $part.Length -ge $Root.Length) {
        if ((Test-Path -LiteralPath $part) -and ((Get-Item -LiteralPath $part -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw '回退目标包含重解析点'
        }
        $part = [IO.Path]::GetDirectoryName($part)
    }
    return $target
}
function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not ([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw '需要管理员权限安装跨注销、跨重启的看门狗'
    }
}
function Assert-UU {
    $service = Get-Service -Name 'MuMuRemoteService'
    if ($service.Status -ne 'Running' -or $service.StartType -ne 'Automatic') {
        throw 'UU 远程服务必须处于运行及自动启动状态'
    }
}
function Get-Run {
    $active = Read-Json $pointer
    if ($RunId -and $active.runId -ne $RunId) { throw '当前看门狗与指定轮次不一致' }
    if ($active.runId -notmatch '^[a-f0-9]{32}$') { throw '看门狗轮次无效' }
    $directory = Join-Path $env:ProgramData ('AutoMasRecovery\' + $active.runId)
    $manifest = Read-Json (Join-Path $directory 'manifest.json')
    if ($manifest.root -ne $Root -or $manifest.runId -ne $active.runId) { throw '看门狗实例不匹配' }
    return @{ directory = $directory; manifest = $manifest; state = (Join-Path $directory 'state.json') }
}

# 日常恢复不依赖临时测试轮次；仍要求 UU 服务运行且自动启动。
if ($Action -eq 'DailyStatus') {
    Assert-UU
    @{ ready=$true; mode='daily' } | ConvertTo-Json -Compress
    exit
}

if ($Action -eq 'Prepare') {
    Assert-Admin
    if (-not $Baseline) { throw '必须指定已确认的基线提交' }
    $commit = (& git -C $Root rev-parse --verify "$Baseline^{commit}").Trim()
    if ($LASTEXITCODE -ne 0 -or $commit -notmatch '^[a-f0-9]{40}$') { throw '基线提交无效' }
    if (Test-Path -LiteralPath $pointer) {
        $prior = Get-Run
        if ((Read-Json $prior.state).status -in @('armed', 'reverting', 'rebootIssued')) { throw '上一轮保护仍有效，不能覆盖' }
    }
    $id = [guid]::NewGuid().ToString('N')
    $directory = Join-Path $env:ProgramData ('AutoMasRecovery\' + $id)
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    # SYSTEM 执行的脚本、清单及备份必须不可被非管理员替换。
    & icacls.exe $directory /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-11:(OI)(CI)RX' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw '无法保护看门狗目录' }
    Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $directory 'guard.ps1')
    $paths = @(& git -C $Root diff --name-only $commit -- app frontend res scripts main.py Start-AUTO-MAS.bat remote_script_controller.py README-RELEASE.md changelog.d)
    if ($LASTEXITCODE -ne 0) { throw '读取改动列表失败' }
    $paths += @(& git -C $Root ls-files --others --exclude-standard -- app frontend res scripts changelog.d)
    if ($LASTEXITCODE -ne 0) { throw '读取新增文件列表失败' }
    # 运行时编译产物通常被 Git 忽略，但测试可能替换它们，也必须原样备份。
    foreach ($binary in @('res/ChildSessionHost/AutoMas.ChildSessionHost.exe', 'AUTO-MAS.exe')) {
        $paths += $binary
    }
    $files = @()
    foreach ($relative in ($paths | Sort-Object -Unique)) {
        $target = Resolve-Target $relative
        $backup = Join-Path $directory ('file-' + $files.Count)
        $exists = Test-Path -LiteralPath $target -PathType Leaf
        # 保存测试前工作区原样内容，包括已经写好的修复，不回滚用户先前的工作。
        if ($exists) { Copy-Item -LiteralPath $target -Destination $backup }
        $files += @{ relative = $relative; existed = $exists; hash = (Get-Hash $target); backup = [IO.Path]::GetFileName($backup) }
    }
    # 登录与自启只备份白名单；不读取密码、LSA secret 或 UU 配置。
    $registry = @()
    $registrySpecs = @(
        @{ path='HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'; names=@('AutoAdminLogon', 'ForceAutoLogon', 'DefaultUserName', 'DefaultDomainName') },
        @{ path='HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\PasswordLess\Device'; names=@('DevicePasswordLessBuildVersion') }
    )
    foreach ($spec in $registrySpecs) {
        $key = Get-Item -LiteralPath $spec.path -ErrorAction SilentlyContinue
        foreach ($name in $spec.names) {
            $exists = $key -and ($key.GetValueNames() -contains $name)
            $registry += @{ path=$spec.path; name=$name; existed=[bool]$exists; value=$(if ($exists) {$key.GetValue($name)} else {$null}); kind=$(if ($exists) {$key.GetValueKind($name).ToString()} else {'String'}) }
        }
    }
    $logonKey = Get-Item -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
    if ($logonKey.GetValueNames() -notcontains 'DefaultPassword') {
        $registry += @{ path='HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'; name='DefaultPassword'; existed=$false; value=$null; kind='String' }
    }
    $startup = Get-ScheduledTask -TaskName 'AUTO-MAS_AutoStart' -ErrorAction SilentlyContinue
    if ($startup) { Export-ScheduledTask -TaskName 'AUTO-MAS_AutoStart' | Set-Content -LiteralPath (Join-Path $directory 'startup.xml') -Encoding Unicode }
    $manifest = @{ version=1; runId=$id; root=$Root; baseline=$commit; files=$files; registry=$registry; startupExisted=[bool]$startup }
    Write-JsonAtomic (Join-Path $directory 'manifest.json') $manifest
    Write-JsonAtomic (Join-Path $directory 'state.json') @{ status='prepared'; runId=$id }
    New-Item -ItemType Directory -Path (Split-Path $pointer) -Force | Out-Null
    Write-JsonAtomic $pointer @{ runId=$id }
    @{ status='prepared'; runId=$id; files=$files.Count } | ConvertTo-Json -Compress
    exit
}

$run = Get-Run
$manifest = $run.manifest
$state = Read-Json $run.state
$taskName = 'AUTO-MAS-RecoveryGuard-' + $manifest.runId
$cancelFile = Join-Path (Split-Path $pointer) ($manifest.runId + '.cancel')

if ($Action -eq 'Arm') {
    Assert-Admin
    Assert-UU
    if (-not $UUVerified) { throw '必须先从另一设备确认 UU 能实际控制本机，再传入 UUVerified' }
    if ($state.status -ne 'prepared') { throw '每轮只能启用一次，必须重新 Prepare' }
    if ($Root.Contains('"')) { throw '目录包含不支持的引号' }
    $worker = Join-Path $run.directory 'guard.ps1'
    $arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $worker + '" -Action Watch -Root "' + $Root + '" -RunId ' + $manifest.runId
    $actionSpec = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument $arguments
    $triggers = @((New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(3)), (New-ScheduledTaskTrigger -AtStartup))
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)
    Register-ScheduledTask -TaskName $taskName -Action $actionSpec -Trigger $triggers -Settings $settings -User 'SYSTEM' -RunLevel Highest -Force | Out-Null
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    Write-JsonAtomic $run.state @{ status='armed'; runId=$manifest.runId; deadline=($now+1800); uuVerifiedAt=$now; heartbeat=0; taskName=$taskName }
    Start-ScheduledTask -TaskName $taskName
    @{ status='armed'; runId=$manifest.runId; deadline=($now+1800) } | ConvertTo-Json -Compress
    exit
}
if ($Action -eq 'Cancel') {
    if ($state.status -eq 'cancelled') { $state | ConvertTo-Json -Compress; exit }
    if ($state.status -ne 'armed') { throw '该轮未运行或已开始回退，不能报告取消成功' }
    [IO.File]::WriteAllText($cancelFile, $manifest.runId)
    for ($i=0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 1
        $state = Read-Json $run.state
        if ($state.status -eq 'cancelled') { $state | ConvertTo-Json -Compress; exit }
        if ($state.status -ne 'armed') { throw '看门狗已开始回退，取消未确认' }
    }
    throw '取消请求已写入，但看门狗尚未确认；保护仍可能有效'
}
if ($Action -eq 'Status') {
    Assert-UU
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    $ready = $state.status -eq 'armed' -and $task.State -eq 'Running' -and ($now-$state.heartbeat) -lt 15 -and ($state.deadline-$now) -gt 90
    @{ ready=[bool]$ready; status=$state.status; runId=$manifest.runId; deadline=$state.deadline; uuVerifiedAt=$state.uuVerifiedAt; heartbeat=$state.heartbeat } | ConvertTo-Json -Compress
    exit
}

# Watch 由受保护副本运行，注销用户或重启后仍按原始 deadline 执行，不重新计时。
Assert-Admin
if ($state.status -ne 'armed') { exit }
while ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() -lt $state.deadline) {
    if (Test-Path -LiteralPath $cancelFile) {
        $state.status = 'cancelled'
        Write-JsonAtomic $run.state $state
        exit
    }
    $state.heartbeat = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    Write-JsonAtomic $run.state $state
    Start-Sleep -Seconds 2
}
if (Test-Path -LiteralPath $cancelFile) { $state.status='cancelled'; Write-JsonAtomic $run.state $state; exit }
if ($DryRun) { @{ status='dryRun'; files=$manifest.files.Count } | ConvertTo-Json -Compress; exit }
$state.status = 'reverting'
Write-JsonAtomic $run.state $state
try {
    # 校验全部备份后才开始恢复，不启动或停止 UU 的任何组件。
    foreach ($file in $manifest.files) {
        $null = Resolve-Target $file.relative
        if ($file.existed -and (Get-Hash (Join-Path $run.directory $file.backup)) -ne $file.hash) { throw '回退备份校验失败' }
    }
    # 仅结束本工作目录的 MAS 进程，避免运行中的 EXE 锁住回退文件。UU 不在目标集合中。
    $ownedExecutables = @(
        (Join-Path $Root 'AUTO-MAS.exe'),
        (Join-Path $Root 'res/ChildSessionHost/AutoMas.ChildSessionHost.exe'),
        (Join-Path $Root '.venv/Scripts/python.exe'),
        (Join-Path $Root '.venv/Scripts/pythonw.exe')
    )
    $serverScript = Join-Path $Root 'frontend/server.js'
    foreach ($candidate in @(Get-CimInstance Win32_Process)) {
        $owned = $candidate.ExecutablePath -in $ownedExecutables
        if (-not $owned -and $candidate.Name -eq 'node.exe' -and $candidate.CommandLine) {
            $owned = $candidate.CommandLine.Contains($serverScript)
        }
        if ($owned) {
            $process = Get-Process -Id $candidate.ProcessId -ErrorAction SilentlyContinue
            if ($process -and [Math]::Abs(($process.StartTime - $candidate.CreationDate).TotalSeconds) -lt 1) {
                Stop-Process -InputObject $process -Force
            }
        }
    }
    foreach ($file in $manifest.files) {
        $target = Resolve-Target $file.relative
        if ($file.existed) { Copy-Item -LiteralPath (Join-Path $run.directory $file.backup) -Destination $target -Force }
        elseif (Test-Path -LiteralPath $target -PathType Leaf) { Remove-Item -LiteralPath $target }
    }
    foreach ($entry in $manifest.registry) {
        if ($entry.existed) {
            New-ItemProperty -LiteralPath $entry.path -Name $entry.name -Value $entry.value -PropertyType $entry.kind -Force | Out-Null
        } else { Remove-ItemProperty -LiteralPath $entry.path -Name $entry.name -ErrorAction SilentlyContinue }
    }
    if ($manifest.startupExisted) {
        Register-ScheduledTask -TaskName 'AUTO-MAS_AutoStart' -Xml (Get-Content -LiteralPath (Join-Path $run.directory 'startup.xml') -Raw) -Force | Out-Null
    } else { Unregister-ScheduledTask -TaskName 'AUTO-MAS_AutoStart' -Confirm:$false -ErrorAction SilentlyContinue }
    # 先持久化终态：即使重启或 shutdown 失败也不再次发起重启。
    $state.status = 'rebootIssued'
    Write-JsonAtomic $run.state $state
    & "$env:SystemRoot\System32\shutdown.exe" /r /t 0 /d p:0:0 /c 'AUTO-MAS 测试超时，已回退本轮设置'
    if ($LASTEXITCODE -ne 0) { throw '回退完成，但系统拒绝重启' }
} catch {
    $state.status = 'failed'
    $state | Add-Member -NotePropertyName error -NotePropertyValue $_.Exception.Message -Force
    Write-JsonAtomic $run.state $state
    throw
}
