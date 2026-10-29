# 必须在主桌面运行；关闭窗口等同取消，不提前安排系统重启。
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$form = New-Object Windows.Forms.Form
$form.Text = 'AUTO-MAS 恢复失败'
$form.Size = New-Object Drawing.Size(470, 220)
$form.StartPosition = 'CenterScreen'
$form.TopMost = $true
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$label = New-Object Windows.Forms.Label
$label.Location = New-Object Drawing.Point(20, 20)
$label.Size = New-Object Drawing.Size(420, 80)
$confirm = New-Object Windows.Forms.Button
$confirm.Text = '确认，立即重启'
$confirm.Location = New-Object Drawing.Point(90, 115)
$confirm.Size = New-Object Drawing.Size(140, 32)
$cancel = New-Object Windows.Forms.Button
$cancel.Text = '取消重启'
$cancel.Location = New-Object Drawing.Point(250, 115)
$cancel.Size = New-Object Drawing.Size(120, 32)
$confirm.Add_Click({ $form.DialogResult = [Windows.Forms.DialogResult]::OK; $form.Close() })
$cancel.Add_Click({ $form.DialogResult = [Windows.Forms.DialogResult]::Cancel; $form.Close() })
$form.CancelButton = $cancel
$form.Controls.AddRange(@($label, $confirm, $cancel))
$clock = [Diagnostics.Stopwatch]::StartNew()
$timer = New-Object Windows.Forms.Timer
$timer.Interval = 200
$timer.Add_Tick({
    $seconds = [Math]::Max(0, 60 - [int][Math]::Floor($clock.Elapsed.TotalSeconds))
    $label.Text = "远程桌面恢复失败，$seconds 秒后将自动重启电脑。`r`n已尽力保存任务进度；未保存的其他程序内容可能丢失。`r`n取消后保持暂停，不会再次自动弹出倒计时。"
    if ($seconds -eq 0) { $form.DialogResult = [Windows.Forms.DialogResult]::OK; $form.Close() }
})
$label.Text = '60 秒后将自动重启电脑。确认立即重启，取消则保持暂停。'
$timer.Start()
try { $result = $form.ShowDialog() }
finally { $timer.Stop(); $timer.Dispose(); $form.Dispose() }
if ($result -eq [Windows.Forms.DialogResult]::OK) { exit 0 }
exit 2
