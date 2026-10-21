#Requires -Version 5.1

[CmdletBinding(SupportsShouldProcess)]
param()

$ErrorActionPreference = "Stop"
$RootDir = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot)).TrimEnd('\')
$VenvDir = Join-Path $RootDir ".venv"
$LauncherExe = Join-Path $RootDir "AUTO-MAS.exe"
$HostExe = Join-Path $RootDir "res\ChildSessionHost\AutoMas.ChildSessionHost.exe"
$MainPy = Join-Path $RootDir "main.py"
$ServerJs = Join-Path $RootDir "frontend\server.js"
$WrapperPy = Join-Path $RootDir "app\utils\platform\windows\child_session_wrapper.py"
$Comparison = [StringComparison]::OrdinalIgnoreCase

Write-Host "正在清理当前目录的安装环境: $RootDir" -ForegroundColor Cyan

# 先关闭由此目录启动的服务，避免移动后残留旧路径进程。
try {
    $SavedWhatIf = $WhatIfPreference
    $WhatIfPreference = $false
    $Processes = Get-CimInstance Win32_Process -ErrorAction Stop
} catch {
    throw "无法检查正在运行的进程；请以有权访问进程列表的账户重试。$_"
} finally {
    $WhatIfPreference = $SavedWhatIf
}

$OwnedProcesses = @($Processes | Where-Object {
    $exe = [string]$_.ExecutablePath
    $command = [string]$_.CommandLine
    $name = [string]$_.Name
    $isLauncher = $exe.Equals($LauncherExe, $Comparison)
    $isHost = $exe.Equals($HostExe, $Comparison)
    $isPython = $name -in @("python.exe", "pythonw.exe") -and (
        $exe.StartsWith((Join-Path $VenvDir "Scripts") + '\', $Comparison) -or
        $command.IndexOf($MainPy, $Comparison) -ge 0 -or
        $command.IndexOf($WrapperPy, $Comparison) -ge 0
    )
    $isNode = $name -eq "node.exe" -and $command.IndexOf($ServerJs, $Comparison) -ge 0
    $isLauncher -or $isHost -or $isPython -or $isNode
})

foreach ($process in $OwnedProcesses) {
    if ($PSCmdlet.ShouldProcess("$($process.Name) (PID $($process.ProcessId))", "停止当前安装的进程")) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

if (-not $WhatIfPreference) {
    Start-Sleep -Milliseconds 500
    $StillRunning = @($OwnedProcesses | Where-Object {
        Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
    })
    if ($StillRunning.Count -gt 0) {
        throw "仍有 AUTO-MAS 进程在运行，请先退出后重试。"
    }
}

# 只删除本安装创建、且仍指向当前目录的快捷方式。
$ShortcutTargets = @($LauncherExe, (Join-Path $RootDir "Start-AUTO-MAS.bat"), (Join-Path $RootDir "Start-Headless.bat"))
$DesktopDirs = @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("CommonDesktopDirectory")) |
    Where-Object { $_ } | Select-Object -Unique
$Shell = New-Object -ComObject WScript.Shell
foreach ($desktop in $DesktopDirs) {
    foreach ($name in @("AUTO-MAS 控制台.lnk", "AUTO-MAS 静默后台运行.lnk")) {
        $shortcutPath = Join-Path $desktop $name
        if (-not (Test-Path -LiteralPath $shortcutPath)) { continue }
        $shortcut = $Shell.CreateShortcut($shortcutPath)
        if (-not ($ShortcutTargets | Where-Object { $_.Equals($shortcut.TargetPath, $Comparison) })) {
            Write-Host "保留其他安装的快捷方式: $shortcutPath"
            continue
        }
        if ($PSCmdlet.ShouldProcess($shortcutPath, "删除当前安装的快捷方式")) {
            Remove-Item -LiteralPath $shortcutPath -Force
        }
    }
}

# Windows 虚拟环境记录绝对路径，移动目录前必须移除并在新位置重建。
if (Test-Path -LiteralPath $VenvDir) {
    $venvItem = Get-Item -LiteralPath $VenvDir -Force
    if (-not $venvItem.PSIsContainer -or
        ($venvItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        -not (Test-Path -LiteralPath (Join-Path $VenvDir "pyvenv.cfg")) -or
        [IO.Path]::GetFullPath($venvItem.FullName).TrimEnd('\') -ne $VenvDir) {
        throw "`.venv 不是当前目录中的普通 Python 虚拟环境，已停止清理。"
    }
    if ($PSCmdlet.ShouldProcess($VenvDir, "删除需在新位置重建的虚拟环境")) {
        Remove-Item -LiteralPath $VenvDir -Recurse -Force
    }
}

if ($WhatIfPreference) {
    Write-Host "预览完成，未删除任何文件或停止进程。" -ForegroundColor Yellow
} else {
    Write-Host "清理完成。配置和用户数据已保留；移动目录后请运行 Install-AUTO-MAS.bat 重建环境。" -ForegroundColor Green
}
