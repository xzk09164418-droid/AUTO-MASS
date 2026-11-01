param([string]$AppId, [string]$XmlPath, [string]$Tag)
$ErrorActionPreference='Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml([IO.File]::ReadAllText($XmlPath, [Text.Encoding]::UTF8))
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
$toast.Tag=$Tag
$toast.Group='queue-control'
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($AppId)
if ($notifier.Setting.ToString() -ne 'Enabled') { throw ('Windows notification setting: ' + $notifier.Setting) }
$notifier.Show($toast)
