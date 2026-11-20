"""3D 增强组件（可选安装）。

增强动态效果挡位需要 Qt Quick 3D，它在 PySide6-Addons 包里（约 180 MB），默认不安装：
- 用户在设置里选「增强」且组件缺失时，二次确认后用当前解释器的 pip 下载安装，版本与 PySide6 保持一致；
- 切回减少 / 标准挡位时直接删除这些文件。本次运行已加载过 3D 模块时 Windows 会锁住 DLL，
  先写入删除标记，下次启动、在加载任何 Qt 模块之前完成删除（见 cleanup_pending_removal）。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, QProcess, Signal, Slot

ROOT_DIR = Path(__file__).resolve().parents[2]
PACKAGE = "PySide6-Addons"
REMOVE_MARKER = ROOT_DIR / "config" / "QtEnhancedRemove.flag"


def _pyside_dir() -> Path:
    import PySide6

    return Path(PySide6.__file__).resolve().parent


def _version() -> str:
    import PySide6

    return PySide6.__version__


def is_installed() -> bool:
    return (_pyside_dir() / "qml" / "QtQuick3D").is_dir() and not REMOVE_MARKER.exists()


def cleanup_pending_removal() -> None:
    """启动早期调用：上次运行里已选择删除、但当时文件被占用，这里补删。"""

    if not REMOVE_MARKER.exists():
        return
    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", "--disable-pip-version-check", PACKAGE],
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    REMOVE_MARKER.unlink(missing_ok=True)


class EnhancedComponent(QObject):
    """暴露给 QML：state = installed / missing / installing / removing / pending-remove / error。"""

    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = "installed" if is_installed() else "missing"
        self._detail = ""
        self._loaded = False
        self._process: QProcess | None = None
        self._tail: list[str] = []

    @Property(str, notify=changed)
    def state(self) -> str:
        return self._state

    @Property(bool, notify=changed)
    def installed(self) -> bool:
        return self._state == "installed"

    @Property(str, notify=changed)
    def detail(self) -> str:
        return self._detail

    @Property(str, constant=True)
    def packageText(self) -> str:
        return f"{PACKAGE} {_version()}"

    @Property(str, constant=True)
    def sizeText(self) -> str:
        return "约 180 MB"

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

    @Slot()
    def remove(self) -> None:
        if self._state in ("installing", "removing", "missing"):
            return
        if self._loaded:
            REMOVE_MARKER.parent.mkdir(parents=True, exist_ok=True)
            REMOVE_MARKER.write_text("remove PySide6-Addons on next start\n", encoding="utf-8")
            self._set("pending-remove", "3D 模块正在使用中，下次启动时完成删除")
            return
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
