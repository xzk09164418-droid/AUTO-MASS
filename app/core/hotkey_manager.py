"""全局热键管理器（支持启停切换、上一任务、下一任务）。

在 Windows 平台通过 `user32.RegisterHotKey` 与独立消息泵线程监听系统全局热键，
触发后投递到主事件循环调用 `TaskManager` 的启停与上/下任务跳转接口。
"""

from __future__ import annotations

import asyncio
import ctypes
import os
import threading
from ctypes import wintypes
from typing import Any, Callable, Coroutine

from app.task.MaaFW.tools.core.runner.hotkey import _canonical_key, _win32_keycode
from app.utils.logger import get_logger

logger = get_logger("全局热键")

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

HOTKEY_ID_TOGGLE = 1001
HOTKEY_ID_PREV = 1002
HOTKEY_ID_NEXT = 1003

_MODIFIER_MAP = {
    "CTRL": MOD_CONTROL,
    "ALT": MOD_ALT,
    "SHIFT": MOD_SHIFT,
    "META": MOD_WIN,
}


def parse_win32_hotkey(hotkey_str: str) -> tuple[int, int]:
    """将形如 'Ctrl+Alt+S'、'Ctrl+Alt+Left'、'F9' 的快捷键字符串解析为 (modifiers, vk_code)。"""
    raw = (hotkey_str or "").strip()
    if not raw:
        raise ValueError("快捷键字符串为空")

    parts = [_canonical_key(p) for p in raw.split("+")]
    if not parts or any(not part for part in parts) or parts[-1] in _MODIFIER_MAP:
        raise ValueError(f"无效的快捷键格式: {hotkey_str!r}")

    modifiers = MOD_NOREPEAT
    for mod in parts[:-1]:
        if mod not in _MODIFIER_MAP:
            raise ValueError(f"未知修饰键: {mod!r} (快捷键: {hotkey_str!r})")
        modifiers |= _MODIFIER_MAP[mod]

    vk = _win32_keycode(parts[-1])
    return modifiers, vk


class _HotkeyManager:
    """系统级全局热键服务。"""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._running = False
        self._registered_bindings: dict[str, str] = {}
        self._registration_errors: list[str] = []
        self._reload_lock = asyncio.Lock()
        self._action_lock = asyncio.Lock()

    @property
    def registered_bindings(self) -> dict[str, str]:
        return dict(self._registered_bindings)

    def _read_config_bindings(self) -> tuple[bool, str, str, str]:
        try:
            from app.core import Config

            enabled = bool(Config.get("Hotkey", "Enabled"))
            toggle_key = str(Config.get("Hotkey", "ToggleStartStop") or "Ctrl+Alt+S")
            prev_key = str(Config.get("Hotkey", "PreviousTask") or "Ctrl+Alt+Left")
            next_key = str(Config.get("Hotkey", "NextTask") or "Ctrl+Alt+Right")
            return enabled, toggle_key, prev_key, next_key
        except Exception:
            return True, "Ctrl+Alt+S", "Ctrl+Alt+Left", "Ctrl+Alt+Right"

    async def start(self) -> None:
        if self._running:
            return
        self._loop = asyncio.get_running_loop()
        enabled, toggle_key, prev_key, next_key = self._read_config_bindings()
        self._registered_bindings = {}
        self._registration_errors = []
        if not enabled:
            logger.info("全局热键开关未启用，跳过注册")
            return

        if os.name != "nt":
            logger.info("当前非 Windows 平台，全局热键仅保留 HTTP API 触发模式")
            return

        ready_event = threading.Event()
        self._running = True
        self._thread = threading.Thread(
            target=self._win32_message_loop,
            args=(toggle_key, prev_key, next_key, ready_event),
            name="auto-mas-global-hotkey",
            daemon=True,
        )
        self._thread.start()
        if not await asyncio.to_thread(ready_event.wait, 3.0):
            await self.stop()
            raise RuntimeError("等待全局热键注册超时")
        if self._registration_errors:
            errors = "；".join(self._registration_errors)
            await self.stop()
            raise RuntimeError(errors)

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if os.name == "nt" and self._thread_id is not None:
            try:
                ctypes.windll.user32.PostThreadMessageW(
                    wintypes.DWORD(self._thread_id),
                    wintypes.UINT(WM_QUIT),
                    wintypes.WPARAM(0),
                    wintypes.LPARAM(0),
                )
            except Exception:
                pass
        if self._thread is not None and self._thread.is_alive():
            await asyncio.to_thread(self._thread.join, 2.0)
        self._thread = None
        self._thread_id = None
        self._registered_bindings = {}
        logger.info("全局热键服务已停止")

    async def reload(self) -> None:
        async with self._reload_lock:
            await self.stop()
            await self.start()

    def _win32_message_loop(
        self,
        toggle_key: str,
        prev_key: str,
        next_key: str,
        ready_event: threading.Event,
    ) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.windll.kernel32
        self._thread_id = int(kernel32.GetCurrentThreadId())

        specs = [
            (
                HOTKEY_ID_TOGGLE,
                "toggleStartStop",
                "启停切换",
                toggle_key,
                self.trigger_toggle_start_stop,
            ),
            (
                HOTKEY_ID_PREV,
                "previousTask",
                "上一个任务",
                prev_key,
                self.trigger_previous_task,
            ),
            (
                HOTKEY_ID_NEXT,
                "nextTask",
                "下一个任务",
                next_key,
                self.trigger_next_task,
            ),
        ]
        actions: dict[int, Callable[[], Coroutine[Any, Any, Any]]] = {}

        for hk_id, name, label, key_str, coro_fn in specs:
            if not key_str.strip():
                continue
            try:
                mods, vk = parse_win32_hotkey(key_str)
                if user32.RegisterHotKey(None, hk_id, mods, vk):
                    actions[hk_id] = coro_fn
                    self._registered_bindings[name] = key_str
                    logger.info(f"已注册全局热键 [{label}]: {key_str}")
                else:
                    err = ctypes.get_last_error()
                    raise OSError(err, ctypes.FormatError(err))
            except Exception as exc:
                error = f"注册全局热键 [{label}] ({key_str}) 失败: {exc}"
                self._registration_errors.append(error)
                logger.warning(error)

        # 先创建消息队列，再通知主线程就绪，保证紧接着的 stop/reload 能投递 WM_QUIT。
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
        ready_event.set()
        try:
            while self._running:
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret <= 0 or msg.message == WM_QUIT:
                    break
                if msg.message == WM_HOTKEY:
                    hk_id = int(msg.wParam)
                    coro_fn = actions.get(hk_id)
                    if coro_fn is not None and self._loop is not None:
                        asyncio.run_coroutine_threadsafe(
                            self._run_action(coro_fn), self._loop
                        )
        finally:
            for hk_id in actions:
                try:
                    user32.UnregisterHotKey(None, hk_id)
                except Exception:
                    pass

    async def _run_action(self, action: Callable[[], Coroutine[Any, Any, Any]]) -> None:
        if self._action_lock.locked():
            return
        async with self._action_lock:
            try:
                result = await action()
                logger.info(f"全局热键操作完成: {result}")
            except Exception:
                logger.exception("全局热键操作失败")

    async def trigger_toggle_start_stop(self) -> dict[str, Any]:
        from app.core import TaskManager

        logger.info("全局热键触发：控制程序启停 (toggle_start_stop)")
        return await TaskManager.toggle_start_stop()

    async def trigger_previous_task(self) -> dict[str, Any]:
        from app.core import TaskManager

        logger.info("全局热键触发：切换到上一个任务 (previous_task)")
        return await TaskManager.navigate_task(-1)

    async def trigger_next_task(self) -> dict[str, Any]:
        from app.core import TaskManager

        logger.info("全局热键触发：切换到下一个任务 (next_task)")
        return await TaskManager.navigate_task(1)


HotkeyManager = _HotkeyManager()
