"""借用桌面的已登记进程身份与回收，不按进程名猜测外部程序归属。"""

import asyncio
import ctypes
import os

import psutil

from app.utils.platform.windows.session import get_process_session_id


class BorrowedDesktopProcess:
    def __init__(self, pid: int, created_at: float, session_id: int) -> None:
        process = psutil.Process(pid)
        if abs(process.create_time() - created_at) > 0.001:
            raise ValueError("借用进程身份已改变")
        if session_id == 0 or get_process_session_id(pid) != session_id:
            raise ValueError("借用进程不在声明的交互会话")
        if pid in {os.getpid(), *(p.pid for p in psutil.Process().parents())}:
            raise ValueError("不能将 MAS 或其主桌面监督进程登记为外部借用程序")
        self.session_id = session_id
        self.processes = {pid: process}
        self._validate(process)

    def _validate(self, process: psutil.Process) -> None:
        if get_process_session_id(process.pid) != self.session_id:
            raise ValueError("外部进程已改变会话")
        if process.name().lower().startswith(("mumuremote", "uuconsolegate")):
            raise ValueError("UU 远程组件不能纳入借用回收")

    def collect(self) -> None:
        for process in tuple(self.processes.values()):
            if process.is_running():
                for child in process.children(recursive=True):
                    self._validate(child)
                    child.create_time()
                    self.processes[child.pid] = child

    def _close_windows(self) -> None:
        targets = {p.pid for p in self.processes.values() if p.is_running()}
        callback_type = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p
        )

        def close(hwnd: int, _: int) -> bool:
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in targets:
                ctypes.windll.user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0010, 0, 0)
            return True

        ctypes.windll.user32.EnumWindows(callback_type(close), 0)

    async def close(self) -> None:
        self.collect()
        await asyncio.to_thread(self._close_windows)
        await asyncio.to_thread(
            psutil.wait_procs, list(self.processes.values()), timeout=5
        )
        self.collect()
        for process in reversed(list(self.processes.values())):
            if process.is_running():
                self._validate(process)
                process.kill()
        _, alive = await asyncio.to_thread(
            psutil.wait_procs, list(self.processes.values()), timeout=5
        )
        if alive:
            raise RuntimeError("外部进程未完全退出，保持暂停")
