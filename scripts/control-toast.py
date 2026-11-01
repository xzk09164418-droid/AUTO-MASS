"""在主桌面注册并发送独立的、带操作按钮的队列控制通知。"""

import base64
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import winreg
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import pythoncom
from win32com.client import Dispatch
from win32com.propsys import propsys, pscon


def show(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    root = Path(__file__).resolve().parents[1]
    source = root / "res/QueueControlToast/Program.cs"
    executable = source.with_name("QueueControlToast.exe")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    stamp = source.with_suffix(".sha256")
    if not executable.exists() or not stamp.exists() or stamp.read_text() != digest:
        compiler = (
            Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        )
        subprocess.run(
            [
                str(compiler),
                "/nologo",
                "/target:winexe",
                "/r:System.Web.Extensions.dll",
                f"/out:{executable}",
                str(source),
            ],
            check=True,
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        stamp.write_text(digest)
    suffix = hashlib.sha256(str(root).lower().encode()).hexdigest()[:12]
    scheme = "automas-control-" + suffix
    app_id = "AUTO-MAS.Control." + suffix
    prog_id = app_id + ".Protocol"
    # 管理员启动时同步机器级协议，兼容通知入口无法识别用户级关联的环境。
    if ctypes.windll.shell32.IsUserAnAdmin():
        machine_path = "Software\\Classes\\" + scheme
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, machine_path) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:AUTO-MAS Queue Control")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(
            winreg.HKEY_LOCAL_MACHINE, machine_path + "\\shell\\open\\command"
        ) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{executable}" "%1"')
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, "Software\\Classes\\" + scheme
    ) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:AUTO-MAS Queue Control")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER,
        "Software\\Classes\\" + scheme + "\\shell\\open\\command",
    ) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{executable}" "%1"')
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER,
        "Software\\Classes\\" + prog_id + "\\shell\\open\\command",
    ) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{executable}" "%1"')
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, "Software\\Classes\\" + prog_id + "\\Application"
    ) as key:
        winreg.SetValueEx(key, "ApplicationName", 0, winreg.REG_SZ, "AUTO-MAS 队列控制")
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, "Software\\Classes\\" + prog_id + "\\DefaultIcon"
    ) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{executable}",0')
    capability_path = "Software\\AUTO-MAS\\QueueControl\\" + suffix + "\\Capabilities"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, capability_path) as key:
        winreg.SetValueEx(key, "ApplicationName", 0, winreg.REG_SZ, "AUTO-MAS 队列控制")
        winreg.SetValueEx(
            key, "ApplicationDescription", 0, winreg.REG_SZ, "处理队列通知按钮"
        )
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, capability_path + "\\UrlAssociations"
    ) as key:
        winreg.SetValueEx(key, scheme, 0, winreg.REG_SZ, prog_id)
    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, "Software\\RegisteredApplications"
    ) as key:
        winreg.SetValueEx(key, app_id, 0, winreg.REG_SZ, capability_path)
    # 通知 Shell 刷新关联缓存，首次注册后即可从原生通知打开协议。
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    shortcut = (
        Path(os.environ["APPDATA"])
        / "Microsoft/Windows/Start Menu/Programs"
        / ("AUTO-MAS 队列控制-" + suffix + ".lnk")
    )
    pythoncom.CoInitialize()
    try:
        link = Dispatch("WScript.Shell").CreateShortcut(str(shortcut))
        link.TargetPath = str(executable)
        link.WorkingDirectory = str(root)
        link.Save()
        properties = propsys.SHGetPropertyStoreFromParsingName(str(shortcut), None, 2)
        properties.SetValue(pscon.PKEY_AppUserModel_ID, propsys.PROPVARIANTType(app_id))
        properties.Commit()
    finally:
        pythoncom.CoUninitialize()
    actions = ""
    if data["buttons"]:
        for action, label in [("pause", "暂停"), ("continue", "跳过等待")]:
            payload = {
                key: data[key] for key in ("port", "instanceId", "taskId", "token")
            }
            payload["action"] = action
            encoded = (
                base64.urlsafe_b64encode(json.dumps(payload).encode())
                .decode()
                .rstrip("=")
            )
            uri = scheme + "://control/" + encoded
            actions += f'<action content={quoteattr(label)} activationType="protocol" arguments={quoteattr(uri)}/>'
    xml = (
        '<toast duration="long"><visual><binding template="ToastGeneric"><text>'
        + escape(data["title"])
        + "</text><text>"
        + escape(data["message"])
        + "</text></binding></visual>"
        + ("<actions>" + actions + "</actions>" if actions else "")
        + "</toast>"
    )
    # XML 作为 UTF-8 文件传递，不将标题或任务名拼进 PowerShell 命令。
    path.with_suffix(".xml").write_text(xml, encoding="utf-8")
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(root / "scripts/control-toast.ps1"),
            "-AppId",
            app_id,
            "-XmlPath",
            str(path.with_suffix(".xml")),
            "-Tag",
            data["taskId"].replace("-", "")[:16],
        ],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        timeout=15,
    )
    if result.returncode:
        try:
            detail = result.stderr.decode("utf-8")
        except UnicodeDecodeError:
            detail = result.stderr.decode("gb18030", errors="replace")
        raise RuntimeError(detail.strip() or "原生控制通知发送失败")


if __name__ == "__main__":
    show(Path(sys.argv[1]))
