"""3D 增强组件（可选安装）。

增强动态效果挡位需要 Qt Quick 3D，它在 PySide6-Addons 包里（下载约 161 MB，安装后约 420 MB），默认不安装：
- 用户在设置里选「增强」且组件缺失时，二次确认后用当前解释器的 pip 下载安装，版本与 PySide6 保持一致；
- 切回减少 / 标准挡位时不立即删除，只写入删除标记；用户退出程序、下次启动加载完毕并空闲后，
  再在后台删除（见 EnhancedComponent.cleanupPending）。删除前又切回增强挡位则取消标记、保留文件。
- 用户选择的挡位保存在 config/QtClient.json，下次启动沿用。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, QProcess, Signal, Slot

ROOT_DIR = Path(__file__).resolve().parents[2]
PACKAGE = "PySide6-Addons"
REMOVE_MARKER = ROOT_DIR / "config" / "QtEnhancedRemove.flag"
CLIENT_CONFIG = ROOT_DIR / "config" / "QtClient.json"
MOTIONS = ("reduced", "standard", "enhanced")


def _pyside_dir() -> Path:
    import PySide6

    return Path(PySide6.__file__).resolve().parent


def _version() -> str:
    import PySide6

    return PySide6.__version__


def is_installed() -> bool:
    return (_pyside_dir() / "qml" / "QtQuick3D").is_dir()


def saved_motion() -> str:
    """上次选择的动态效果挡位（没有记录时为标准）。"""

    try:
        motion = json.loads(CLIENT_CONFIG.read_text(encoding="utf-8")).get("motion", "")
    except (OSError, ValueError, AttributeError):
        motion = ""
    return motion if motion in MOTIONS else "standard"


def save_motion(motion: str) -> None:
    try:
        data = json.loads(CLIENT_CONFIG.read_text(encoding="utf-8")) if CLIENT_CONFIG.exists() else {}
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    data["motion"] = motion
    try:
        CLIENT_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CLIENT_CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


class EnhancedComponent(QObject):
    """暴露给 QML：state = installed / missing / installing / removing / pending-remove / error。"""

    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        if not is_installed():
            REMOVE_MARKER.unlink(missing_ok=True)
            self._state = "missing"
        else:
            self._state = "pending-remove" if REMOVE_MARKER.exists() else "installed"
        self._detail = ""
        self._loaded = False
        self._process: QProcess | None = None
        self._tail: list[str] = []

    @Property(str, notify=changed)
    def state(self) -> str:
        return self._state

    @Property(bool, notify=changed)
    def installed(self) -> bool:
        """文件在且可用（等待删除期间仍可用，切回增强挡位即取消删除）。"""
        return self._state in ("installed", "pending-remove")

    @Property(str, notify=changed)
    def detail(self) -> str:
        return self._detail

    @Property(str, constant=True)
    def packageText(self) -> str:
        return f"{PACKAGE} {_version()}"

    @Property(str, constant=True)
    def sizeText(self) -> str:
        return "下载约 161 MB，安装后约 420 MB"

    def _set(self, state: str, detail: str = "") -> None:
        self._state = state
        self._detail = detail
        self.changed.emit()

    @Slot()
    def markLoaded(self) -> None:
        """本次运行已加载 Qt Quick 3D（其 DLL 会被占用，删除需推迟到下次启动）。"""

        self._loaded = True

    @Slot()
    def install(self) -> None:
        if self._state in ("installing", "removing"):
            return
        REMOVE_MARKER.unlink(missing_ok=True)
        if (_pyside_dir() / "qml" / "QtQuick3D").is_dir():
            self._set("installed")
            return
        self._run(["install", "--disable-pip-version-check", "--no-deps", f"{PACKAGE}=={_version()}"], "installing", "正在下载")

    @Slot(str)
    def choose(self, motion: str) -> None:
        """用户切换动态效果挡位：记住选择；离开增强挡位只标记删除，回到增强挡位则取消标记。"""

        if motion not in MOTIONS:
            return
        save_motion(motion)
        if motion == "enhanced":
            if self._state == "pending-remove":
                REMOVE_MARKER.unlink(missing_ok=True)
                self._set("installed", "kept")
            return
        if self._state == "installed":
            REMOVE_MARKER.parent.mkdir(parents=True, exist_ok=True)
            REMOVE_MARKER.write_text("remove PySide6-Addons after next start\n", encoding="utf-8")
            self._set("pending-remove", "退出程序后，下次启动加载完毕、空闲时删除")

    @Slot()
    def cleanupPending(self) -> None:  # noqa: N802
        """启动加载完毕、程序空闲时调用：上次运行里离开了增强挡位，这里在后台删除组件文件。"""

        if self._state != "pending-remove" or self._loaded or not REMOVE_MARKER.exists():
            return
        REMOVE_MARKER.unlink(missing_ok=True)
        self._run(["uninstall", "-y", "--disable-pip-version-check", PACKAGE], "removing", "正在删除")

    def _run(self, args: list[str], state: str, detail: str) -> None:
        self._tail = []
        self._set(state, detail)
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(lambda: self._read(process))
        process.finished.connect(lambda code, _s: self._finished(state, code))
        self._process = process
        process.start(sys.executable, ["-m", "pip", *args])

    def _read(self, process: QProcess) -> None:
        text = bytes(process.readAllStandardOutput().data()).decode("utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            self._tail = (self._tail + [line])[-6:]
            if line.startswith("Downloading"):
                # 例："Downloading PySide6_Addons-6.9.3-...whl (171.2 MB)"
                size = line[line.rfind("(") + 1 : line.rfind(")")] if "(" in line else ""
                self._set(self._state, f"正在下载 {size}".strip())
            elif line.startswith("Installing"):
                self._set(self._state, "正在安装")

    def _finished(self, state: str, code: int) -> None:
        self._process = None
        if code != 0:
            self._set("error", "；".join(self._tail[-2:]) or f"pip 退出码 {code}")
            return
        if state == "installing":
            self._set("installed" if is_installed() else "error", "" if is_installed() else "安装完成但未找到 QtQuick3D 模块")
        else:
            self._set("missing")
