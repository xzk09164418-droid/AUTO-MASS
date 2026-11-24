"""Qt 托盘与窗口生命周期，复用浏览器托盘的后端控制接口。"""

from __future__ import annotations

import ctypes
import json
import mmap
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from .backend import ROOT_DIR, BackendSupervisor


def logoff_child_session() -> None:
    """与 Web 托盘相同：清理完成后注销已启用的本地子会话。"""
    if sys.platform != "win32":
        return
    api = ctypes.WinDLL("wtsapi32", use_last_error=True)
    session = ctypes.c_uint32()
    if not api.WTSGetChildSessionId(ctypes.byref(session)):
        error = ctypes.get_last_error()
        if error == 1168:
            return
        raise OSError(error, "无法取得远程桌面子会话，完全退出未完成")
    if session.value != 0xFFFFFFFF and not api.WTSLogoffSession(None, session, True):
        raise OSError(ctypes.get_last_error(), "无法注销远程桌面子会话，完全退出未完成")


class ClientController(QObject):
    showRequested = Signal()
    releaseRequested = Signal()
    quitRequested = Signal()
    errorOccurred = Signal(str)

    def __init__(
        self, backend: BackendSupervisor, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self.backend = backend
        self.window = None
        self._tray_theme = None
        try:
            settings = json.loads(
                (ROOT_DIR / "config/Config.json").read_text(encoding="utf-8")
            )
            self.start_hidden = (
                settings.get("Start", {}).get("IfMinimizeDirectly") is True
            )
        except (OSError, ValueError):
            self.start_hidden = False
        self.busy = False
        self._restart = False
        self._close_deadline = 0.0
        self._misses = 0
        self._display_prompt = None
        self._workers = ThreadPoolExecutor(max_workers=1)
        self._logout = None
        self._close_timer = QTimer(self)
        self._close_timer.setInterval(500)
        self._close_timer.timeout.connect(self._wait_for_close)
        self.tray = QSystemTrayIcon(
            QIcon(str(ROOT_DIR / "res/icons/AUTO-MAS.ico")), self
        )
        self.tray.setToolTip("AUTO-MAS")
        self.menu = QMenu()
        self._menu_dark = None
        self.actions = {}
        self._add("show", "打开 AUTO-MAS Qt 控制台", self.show_window)
        self.menu.addSeparator()
        self._add(
            "rdp_show",
            "显示 BetterGI 本地远程桌面窗口",
            lambda: self.control("/api/child-session/window", {"visible": True}),
        )
        self._add(
            "rdp_hide",
            "隐藏远程桌面窗口到托盘",
            lambda: self.control("/api/child-session/window", {"visible": False}),
        )
        self.menu.addSeparator()
        self._add(
            "toggle",
            "启停任务队列",
            lambda: self.control("/api/dispatch/navigation/toggle", {}),
        )
        self._add(
            "previous",
            "上一个任务",
            lambda: self.control("/api/dispatch/navigation/previous", {}),
        )
        self._add(
            "next",
            "下一个任务",
            lambda: self.control("/api/dispatch/navigation/next", {}),
        )
        self.menu.addSeparator()
        self._add("frontend", "仅退出前端", self.release_frontend)
        self._add(
            "pause",
            "暂停后端服务（停止队列）",
            lambda: self.control("/api/dispatch/stop", {"taskId": "ALL"}),
        )
        self._add("restart", "强制重启 MAS（清空运行状态）", self.force_restart)
        self._add("exit", "完全退出", self.shutdown_all)
        # Windows 的原生 HMENU 不绘制 Qt 样式，右键时弹出实际的 QMenu。
        if sys.platform != "win32":
            self.tray.setContextMenu(self.menu)
        self.menu.aboutToShow.connect(self._style_menu)
        self.menu.aboutToShow.connect(self._refresh_hotkeys)
        self.tray.activated.connect(self._activated)
        self.tray.show()
        self.errorOccurred.connect(self._show_error)
        backend.eventReceived.connect(self._event)

    def set_window(self, window) -> None:
        self.window = window
        self.tray.setToolTip(
            "AUTO-MAS（前端已打开）" if window is not None else "AUTO-MAS（前端已退出，后端仍在运行）"
        )
        if sys.platform != "win32":
            return
        if window is None:
            self._tray_theme = None
            return
        # The RDP host can read the live theme even before either tray opens.
        self._tray_theme = mmap.mmap(-1, 1, tagname=r"Local\AutoMas.QtTrayDark")
        window.trayDarkChanged.connect(self._sync_tray_theme)
        self._sync_tray_theme()

    def _sync_tray_theme(self) -> None:
        if self._tray_theme is not None:
            self._tray_theme[0] = int(self.window.property("trayDark"))

    def _style_menu(self) -> None:
        dark = (
            self.window.property("trayDark")
            if self.window is not None
            else QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        )
        if dark == self._menu_dark:
            return
        self._menu_dark = dark
        paper, ink, hair, accent = (
            ("#1c272c", "#e0e3dc", "#536166", "#e07a2c")
            if dark
            else ("#f6f4f1", "#0b0c0b", "#aaa59a", "#e8701f")
        )
        self.menu.setStyleSheet(f"""
            QMenu {{ background: {paper}; color: {ink}; border: 1px solid {hair};
                    border-top: 3px solid {accent}; padding: 5px 0;
                    font-family: "Microsoft YaHei UI"; font-size: 10pt; }}
            QMenu::item {{ padding: 6px 22px 6px 16px; border-left: 3px solid transparent; }}
            QMenu::item:selected {{ background: {ink}; color: {paper}; border-left-color: {accent}; }}
            QMenu::item:disabled {{ color: {hair}; }}
            QMenu::separator {{ height: 1px; background: {hair}; margin: 4px 12px; }}
        """)

    def _refresh_hotkeys(self) -> None:
        def loaded(result):
            if not self._ok(result):
                return
            keys = result.get("data", {}).get("Hotkey", {})
            for action, label, key in (
                ("toggle", "启停任务队列", "ToggleStartStop"),
                ("previous", "上一个任务", "PreviousTask"),
                ("next", "下一个任务", "NextTask"),
            ):
                shortcut = keys.get(key) if keys.get("Enabled", True) else None
                self.actions[action].setText(
                    label + (f" ({shortcut})" if shortcut else "")
                )

        self.backend.call("/api/setting/get", {}, loaded)

    def _add(self, key, label, action) -> None:
        item = self.menu.addAction(label)
        item.triggered.connect(action)
        self.actions[key] = item

    def _activated(self, reason) -> None:
        if (
            sys.platform == "win32"
            and reason == QSystemTrayIcon.ActivationReason.Context
        ):
            if not self.busy:
                self.menu.popup(QCursor.pos())
            return
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_window()

    @Slot()
    def show_window(self) -> None:
        if self.busy:
            return
        if self.backend._replaced:
            self.backend.start()
        self.showRequested.emit()
        if self.window:
            self.window.showNormal()
            self.window.raise_()
            self.window.requestActivate()

    @Slot(result=bool)
    def close_window(self) -> bool:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            if (
                QMessageBox.question(
                    None,
                    "退出 AUTO-MAS",
                    "系统托盘不可用，是否等待后端清理后完整退出？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.Yes
            ):
                self.shutdown_all()
            return True
        if self.window:
            self.window.hide()
        return True

    def release_frontend(self) -> None:
        if self.busy:
            return
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.errorOccurred.emit("系统托盘不可用，已保留界面。")
            return
        self.releaseRequested.emit()

    def _set_busy(self, value: bool) -> None:
        self.busy = value
        self.menu.setEnabled(not value)

    def _show_error(self, text: str) -> None:
        box = QMessageBox(QMessageBox.Icon.Warning, "AUTO-MAS 操作未完成", text)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box.open()
        self._error_box = box

    def _fail(self, text: str) -> None:
        self._close_timer.stop()
        self._set_busy(False)
        self.errorOccurred.emit(text)

    @staticmethod
    def _ok(result: dict) -> bool:
        return (
            result.get("code", 200) == 200
            and result.get("success", True) is not False
            and result.get("status") != "error"
        )

    def control(self, path: str, body: dict) -> None:
        if self.busy:
            return
        self._set_busy(True)

        def health(result):
            if result.get("instanceId") != self.backend._expected_id or not result.get(
                "ready"
            ):
                self._fail("后端尚未就绪或不属于本安装实例，已拒绝操作。")
                return
            self.backend.call(path, body, done, timeout=120000)

        def done(result):
            self._set_busy(False)
            if not self._ok(result):
                self.errorOccurred.emit(str(result.get("message") or "后端操作失败"))
            elif path == "/api/dispatch/stop":
                self.tray.setToolTip("AUTO-MAS（队列已停止，后端仍在运行）")

        self.backend.call("/api/core/health", None, health)

    def shutdown_all(self, *, restart: bool = False) -> None:
        if self.busy:
            return
        self._set_busy(True)
        self._restart = restart
        self._misses = 0
        self._close_deadline = time.monotonic() + 120
        try:
            config = json.loads(
                (ROOT_DIR / "config/Config.json").read_text(encoding="utf-8")
            )
            self._close_child = config.get("ChildSession", {}).get("Enabled") is True
        except FileNotFoundError:
            self._close_child = False
        except (OSError, ValueError) as error:
            self._fail(str(error))
            return

        def health(result):
            if result.get("instanceId") not in (None, self.backend._expected_id):
                self._fail("后端不属于本安装实例，已取消退出。")
                return
            if result.get("instanceId") is None:
                if (
                    result.get("transportError")
                    == QNetworkReply.NetworkError.ConnectionRefusedError.value
                ):
                    self._close_timer.start()
                else:
                    self._fail(
                        "无法确认后端状态，请恢复连接后重试；仅退出前端仍可使用。"
                    )
                return
            self.backend.call("/api/core/close", {}, accepted, timeout=120000)

        def accepted(result):
            if not self._ok(result):
                self._fail(str(result.get("message") or "后端拒绝退出"))
                return
            self._close_timer.start()

        self.backend.call("/api/core/health", None, health)

    def _wait_for_close(self) -> None:
        self._close_timer.stop()
        if time.monotonic() >= self._close_deadline:
            self._fail("后端尚未完成清理，已保留托盘，请查看日志后重试。")
            return

        def checked(result):
            if result.get("instanceId") == self.backend._expected_id:
                self._misses = 0
            elif result.get("instanceId") is not None:
                self._fail("端口已被其他实例占用，已停止退出流程。")
                return
            elif (
                result.get("transportError")
                == QNetworkReply.NetworkError.ConnectionRefusedError.value
            ):
                self._misses += 1
            else:
                self._misses = 0
            # 仅连续拒绝连接算退出；超时/坏响应不等于后端已完成清理。
            if self._misses >= 2:
                self.backend.shutdown()
                self._logout = (
                    self._workers.submit(logoff_child_session)
                    if self._close_child
                    else None
                )
                self._finish_close()
            else:
                self._close_timer.start()

        self.backend.call("/api/core/health", None, checked, timeout=2000)

    def _finish_close(self) -> None:
        if self._logout is not None:
            if not self._logout.done():
                QTimer.singleShot(100, self._finish_close)
                return
            try:
                self._logout.result()
            except Exception as error:
                self._fail(str(error))
                return
        if self._restart:
            self._set_busy(False)
            self.backend.start()
            self.show_window()
        else:
            self.tray.hide()
            self.quitRequested.emit()

    def force_restart(self) -> None:
        if self.busy:
            return
        answer = QMessageBox.warning(
            None,
            "强制重启 MAS",
            "将强制终止当前任务及身份已核实的外部占用进程树，清除占用和临时运行状态，并注销已启用的远程桌面子会话。保留配置，不续跑旧队列。是否继续？",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Ok:
            return
        try:
            script = ROOT_DIR / "scripts/force-restart.ps1"
            if not script.exists():
                raise FileNotFoundError("缺少强制重启助手，请使用完整发行包。")
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                    "-Root",
                    str(ROOT_DIR),
                    "-Frontend",
                    "Qt",
                ],
                cwd=ROOT_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._set_busy(True)
            # 助手失败时允许重试，错误报告由现有助手负责。
            QTimer.singleShot(15000, lambda: self._set_busy(False))
        except OSError as error:
            self.errorOccurred.emit(str(error))

    def _event(self, kind: str, data: dict) -> None:
        if kind == "frontend.close.requested":
            self.shutdown_all()
        elif kind == "frontend.restart.requested":
            self.shutdown_all(restart=True)
        elif kind == "display.detach.prompt":
            self._display_question(data)
        elif kind == "display.detach.prompt.closed" and self._display_prompt:
            self._display_prompt.close()
        elif kind in (
            "system.notice",
            "task.notice",
            "emulator.notice",
            "task.config.discarded",
        ):
            self.tray.showMessage(
                str(data.get("title") or "AUTO-MAS"),
                str(
                    data.get("message")
                    or data.get("content")
                    or "\n".join(data.get("lines", []))
                    or "任务状态已更新"
                ),
            )

    def _display_question(self, data: dict) -> None:
        if self._display_prompt:
            self._display_prompt.close()
        box = QMessageBox(
            QMessageBox.Icon.Question,
            "虚拟显示器",
            "真实显示器已接回，任务仍在运行。立即拆除可能使游戏窗口移动，是否拆除？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        box.finished.connect(
            lambda result: (
                self.control("/api/setting/virtual-display/detach", {})
                if result == QMessageBox.StandardButton.Yes
                else None
            )
        )
        box.show()
        # 使用后端指定的真实显示器位置，避免提示落在不可见的虚拟屏上。
        rect = data.get("monitor") or {}
        if all(
            isinstance(rect.get(k), int) for k in ("left", "top", "right", "bottom")
        ):
            # 后端给物理像素，Qt 在高 DPI 下使用逻辑坐标。
            for screen in QApplication.screens():
                ratio = screen.devicePixelRatio()
                area = screen.geometry()
                if (
                    abs(area.x() * ratio - rect["left"]) < 10
                    and abs(area.y() * ratio - rect["top"]) < 10
                ):
                    area = screen.availableGeometry()
                    box.move(
                        area.right() - box.width() - 24,
                        area.bottom() - box.height() - 24,
                    )
                    break
        self._display_prompt = box
