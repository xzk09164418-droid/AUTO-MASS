#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2024-2025 DLmaster361
#   Copyright © 2025-2026 AUTO-MAS Team

#   This file is part of AUTO-MAS.

#   AUTO-MAS is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of
#   the License, or (at your option) any later version.

#   AUTO-MAS is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
#   the GNU Affero General Public License for more details.

#   You should have received a copy of the GNU Affero General Public License
#   along with AUTO-MAS. If not, see <https://www.gnu.org/licenses/>.

#   Contact: DLmaster_361@163.com


import asyncio
import os
import subprocess
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

from app.utils import get_logger
from app.utils.platform import window
from app.utils.platform.common.errors import UnsupportedPlatformError
from app.utils.platform.process import platform_process
from app.utils.platform.windows.session import (
    EXECUTION_SESSION_ENV,
    in_execution_session,
)

from .process_runner import (  # noqa: F401  # 兼容 re-export：ProcessManager.py 经本模块再导出
    ProcessResult,
    ProcessRunner,
    create_subprocess,
)

logger = get_logger("进程管理")


def _in_execution_session(pid: int) -> bool:
    if os.name != "nt":
        return True
    return in_execution_session(pid)


# 后继进程改绑的搜索窗口（秒）: 覆盖引导式启动器自更新/接力换进程的间隙
_RESEEK_TIMEOUT_SECONDS = 5.0

# 接力后继的最长「年龄」（秒）: 合法后继在原进程退出前后数秒内创建, 而检测到
# 原进程退出最多晚一个日志空闲回调周期（60s）, 留足余量后仍能把运行期间早已
# 存在的同 exe 无关实例（如用户手动打开的启动器 GUI）挡在改绑之外
_RESEEK_MAX_SUCCESSOR_AGE_SECONDS = 180.0

# 强制清理连续调用 taskkill /F /T 的次数
FORCE_KILL_PASSES = 3


@dataclass
class ProcessInfo:
    pid: int | None = None
    name: str | None = None
    exe: str | None = None
    cmdline: list[str] | None = None


def match_process(proc: psutil.Process, target: ProcessInfo) -> bool:
    """检查进程是否与目标进程信息匹配

    ``proc`` 须来自预取了 name/exe/cmdline 的 ``psutil.process_iter``, 直接用
    ``proc.info`` 里的字段比对, 不再逐个进程重新查询; 无权限读到的字段为 None,
    按不匹配处理。
    """

    info = proc.info
    if not _in_execution_session(proc.pid):
        return False
    if target.pid is not None and proc.pid != target.pid:
        return False
    if target.name is not None and info["name"] != target.name:
        return False
    if target.exe is not None and (
        not info["exe"] or Path(info["exe"]) != Path(target.exe)
    ):
        return False
    if target.cmdline is not None and info["cmdline"] != target.cmdline:
        return False

    return True


def is_process_running(process_name: str) -> bool:
    """检查指定进程名是否正在运行且存在可见窗口"""

    for proc in psutil.process_iter(["name"]):
        with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            if proc.info.get("name") == process_name and _in_execution_session(
                proc.pid
            ):
                # 平台不支持窗口能力时 get_window_handles 返回空列表, 循环不进入
                for hwnd in get_window_handles(proc.pid):
                    if window.is_visible(hwnd):
                        return True
    return False


def is_process_alive(process_name: str) -> bool:
    """检查指定进程名是否有存活实例（不依赖窗口）。

    is_process_running 要求存在可见窗口，窗口销毁后进程仍可能存活；
    需要「等待进程完全退出」的调用方（如多用户切换等待旧游戏退出）应
    用本函数按进程名判断存活。
    """

    for proc in psutil.process_iter(["name"]):
        with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            if proc.info.get("name") == process_name and _in_execution_session(
                proc.pid
            ):
                return True
    return False


def get_window_handles(pid: int) -> list[int]:
    """获取指定进程的所有窗口句柄"""

    try:
        return window.get_window_handles(pid)
    except UnsupportedPlatformError:
        return []


def get_main_window_handle(
    pid: int,
    window_title: str | None = None,
    window_class_name: str | None = None,
) -> int | None:
    """获取指定进程的主窗口句柄

    优先按标题或类名定位, 若未命中则回退到 PID 下最合适的顶层窗口。
    平台不支持窗口能力时返回 None。
    """

    try:
        return window.get_main_window_handle(pid, window_title, window_class_name)
    except UnsupportedPlatformError:
        return None


class ProcessManager:
    """进程监视器类, 用于跟踪主进程及其所有子进程的状态（支持本地远程桌面 Child Session 包装器模式）"""

    def __init__(
        self,
        window_title: str | None = None,
        window_class_name: str | None = None,
        reseek_target: bool = False,
    ):
        super().__init__()

        self.process: asyncio.subprocess.Process | Any | None = None
        self.target_process: psutil.Process | None = None
        self.window_title = window_title
        self.window_class_name = window_class_name
        # 引导式启动器（自更新/接力时会更换进程实例）场景: 跟踪进程退出后按
        # 目标信息重新搜索后继实例改绑, 而不是直接判定运行结束
        self.reseek_target = reseek_target
        self._target_info: ProcessInfo | None = None
        self._target_create_time: float | None = None
        self._drain_tasks: list[asyncio.Task[None]] = []
        self.last_returncode: int | None = None
        self._launched_program: Path | None = None

    @property
    def main_pid(self) -> int | None:
        """主进程的 PID"""

        if self.target_process is not None:
            return self.target_process.pid
        if self.process is not None:
            return self.process.pid
        return None

    @property
    def returncode(self) -> int | None:
        """获取被管理进程的退出码（兼容本地进程与远程桌面 Wrapper 进程）。"""
        if self.process is not None and self.process.returncode is not None:
            self.last_returncode = int(self.process.returncode)
            return self.last_returncode
        if self.target_process is not None and not self.target_process.is_running():
            with suppress(Exception):
                rc = self.target_process.wait(timeout=0)
                if rc is not None:
                    self.last_returncode = int(rc)
                    return self.last_returncode
        return self.last_returncode

    @property
    def main_process(self) -> psutil.Process | asyncio.subprocess.Process | Any | None:
        """主进程对象"""

        if self.target_process is not None:
            return self.target_process
        if self.process is not None:
            return self.process
        return None

    @property
    def main_hwnd(self) -> int | None:
        """主进程的主窗口句柄"""

        if self.main_pid is None:
            return None
        return get_main_window_handle(
            self.main_pid, self.window_title, self.window_class_name
        )

    async def open_process(
        self,
        program: Path | str,
        *args: str,
        cwd: Path | None = None,
        target_process: ProcessInfo | None = None,
        stdin: int = asyncio.subprocess.DEVNULL,
        stdout: int = asyncio.subprocess.DEVNULL,
        stderr: int = asyncio.subprocess.DEVNULL,
        null_stream_to_pipe: bool = False,
        elevated: bool = False,
        breakaway: bool = False,
        env: dict[str, str] | None = None,
        use_child_session: bool | None = None,
    ) -> None:
        """
        启动子进程并跟踪目标进程。
        当启用本地远程桌面（Child Session）时，自动通过包装器（Wrapper）在本地远程桌面中启动进程并跟踪状态与退出码。
        """

        if await self.is_running():
            raise RuntimeError("无法同时管理多个进程")

        if (
            target_process is not None
            and target_process.pid is None
            and target_process.name is None
            and target_process.cmdline is None
            and target_process.exe is None
        ):
            raise ValueError("目标进程信息不完整")

        await self.clear()
        self.last_returncode = None
        self._launched_program = Path(program) if program else None

        if os.name == "nt" and not _in_execution_session(os.getpid()):
            raise RuntimeError("当前进程不在指定的 RDP 执行会话")

        # 判断是否需要在本地远程桌面（Child Session）中执行任务
        if use_child_session is None and os.name == "nt":
            try:
                from app.core.child_session import ChildSessionManager

                use_child_session = ChildSessionManager.enabled
                # 后端本身已迁入子桌面时直接创建进程，继承同一会话并保留管道语义。
                if os.environ.get(EXECUTION_SESSION_ENV) is not None:
                    use_child_session = False
            except RuntimeError:
                raise
            except Exception:
                use_child_session = False

        if use_child_session and os.name == "nt":
            from app.core.child_session import ChildSessionManager

            self.process = await ChildSessionManager.launch_in_child_session(
                program,
                *args,
                cwd=cwd,
                env=env,
            )
            if target_process is not None:
                await self.search_process(
                    target_process,
                    60.0,
                    min_create_time=time.time(),
                )
            return

        if elevated and os.name == "nt":
            # 以管理员权限启动进程（触发 UAC），ShellExecute 不返回子进程句柄，
            # 因此无法直接持有 process，仅支持通过 target_process 追踪。
            await asyncio.get_running_loop().run_in_executor(
                None, self._open_process_elevated, program, args, cwd
            )
            if target_process is not None:
                await self.search_process(
                    target_process,
                    60.0,
                    min_create_time=time.time(),
                )
            return

        # 若指定了 null_stream_to_pipe, 将 stdout/stderr 为 DEVNULL 的流替换为管道, 并在后台消费以防止阻塞
        drain_streams = []
        if null_stream_to_pipe:
            if stdout == asyncio.subprocess.DEVNULL:
                stdout = asyncio.subprocess.PIPE
                drain_streams.append("stdout")
            if stderr == asyncio.subprocess.DEVNULL:
                stderr = asyncio.subprocess.PIPE
                drain_streams.append("stderr")

        self.process = await create_subprocess(
            program,
            *args,
            breakaway=breakaway,
            cwd=cwd or (Path(program).parent if Path(program).is_file() else None),
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            env=env,
        )

        # 启动协程消费管道流以防止阻塞
        if drain_streams:
            for name in drain_streams:
                stream = getattr(self.process, name)
                if stream is not None:
                    self._drain_tasks.append(asyncio.create_task(self._drain(stream)))

        if target_process is not None:
            await self.search_process(
                target_process,
                60.0,
                min_create_time=time.time(),
            )

    @staticmethod
    def _open_process_elevated(
        program: Path | str, args: tuple[str, ...], cwd: Path | None
    ) -> None:
        """以管理员权限启动进程（触发 UAC），ShellExecute 成功时返回码大于 32。"""
        import win32api
        import win32con

        parameters = subprocess.list2cmdline(list(args)) if args else None
        working_directory = str(cwd) if cwd is not None else None

        ret = win32api.ShellExecute(
            None,
            "runas",
            str(program),
            parameters,
            working_directory,
            win32con.SW_SHOWNORMAL,
        )
        if ret <= 32:
            raise RuntimeError(
                f"以管理员权限启动进程失败: {program} (ShellExecute 返回 {ret})"
            )

    async def _drain(self, stream: asyncio.StreamReader) -> None:
        """消费子进程标准流, 丢弃写入, 防止管道背压阻塞子进程。"""

        try:
            while _ := await stream.readline():
                pass
        except (ValueError, OSError):
            pass

    async def open_protocol(
        self, protocol_url: str, target_process: ProcessInfo
    ) -> None:
        """使用自定义协议启动子进程, 需要目标进程信息进行跟踪"""

        try:
            await platform_process.open_protocol(protocol_url)
        except UnsupportedPlatformError:
            raise
        except Exception as e:
            raise RuntimeError(f"无法启动协议 {protocol_url}: {e}") from e

        await self.search_process(
            target_process,
            60.0,
            min_create_time=time.time(),
        )

    async def search_process(
        self,
        target_process: ProcessInfo,
        timeout_seconds: float = 60.0,
        min_create_time: float | None = None,
    ) -> None:
        """查找目标进程"""

        def _scan() -> tuple[psutil.Process, float | None] | None:
            for proc in psutil.process_iter(
                ["pid", "name", "exe", "cmdline", "create_time"]
            ):
                if not match_process(proc, target_process):
                    continue
                create_time = proc.info["create_time"]
                if min_create_time is not None and (
                    create_time is None or create_time < min_create_time - 2
                ):
                    continue
                return proc, create_time
            return None

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            found = await asyncio.to_thread(_scan)
            if found is not None:
                proc, create_time = found
                self.target_process = proc
                self._target_info = target_process
                self._target_create_time = create_time
                return
            await asyncio.sleep(0.1)
        else:
            raise RuntimeError("未能在限定时间内找到目标进程")

    async def is_running(self) -> bool:
        """检查当前管理的进程是否仍在运行"""

        if self.target_process is not None:
            if self.target_process.is_running():
                return True
            if self.reseek_target and await self._reseek_target():
                return True
            return False
        if self.process is not None:
            rc = self.process.returncode
            if rc is not None:
                self.last_returncode = int(rc)
                return False
            return True
        return False

    async def _reseek_target(self) -> bool:
        """搜索跟踪目标的后继进程（同目标信息、创建更晚且足够新）, 命中则改绑。"""

        if self._target_info is None or self._target_create_time is None:
            return False
        successor = ProcessInfo(
            name=self._target_info.name,
            exe=self._target_info.exe,
            cmdline=self._target_info.cmdline,
        )
        min_successor_create_time = max(
            self._target_create_time,
            time.time() - _RESEEK_MAX_SUCCESSOR_AGE_SECONDS,
        )
        try:
            await self.search_process(
                successor,
                _RESEEK_TIMEOUT_SECONDS,
                min_create_time=min_successor_create_time,
            )
        except RuntimeError:
            return False
        logger.info(f"原跟踪进程已退出, 改绑后继进程 PID: {self.target_process.pid}")
        return True

    async def _force_taskkill_three_times(self, pid: int | None) -> None:
        """在 Windows 下对指定 PID 调用 taskkill /F /T 强杀 3 遍。"""
        if pid is None or pid <= 0:
            return
        if os.name == "nt":
            with suppress(Exception):
                await platform_process.kill_process(pid, kill_tree=True)
                return
        # 非 Windows 或平台降级兜底
        for _ in range(FORCE_KILL_PASSES):
            with suppress(Exception):
                proc = psutil.Process(pid)
                for child in proc.children(recursive=True):
                    with suppress(Exception):
                        child.kill()
                proc.kill()
            await asyncio.sleep(0.05)

    async def kill(self) -> None:
        """停止监视器并中止所有跟踪的进程（按需求执行 taskkill /F /T 强杀 3 遍）"""

        if self.target_process is not None:
            target_pid = self.target_process.pid
            await self._force_taskkill_three_times(target_pid)
            if self.target_process.is_running():
                with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                    try:
                        self.target_process.terminate()
                        await asyncio.get_running_loop().run_in_executor(
                            None, self.target_process.wait, 3
                        )
                    except psutil.TimeoutExpired:
                        self.target_process.kill()
                        with suppress(psutil.TimeoutExpired):
                            await asyncio.get_running_loop().run_in_executor(
                                None, self.target_process.wait, 3
                            )

        if self.process is not None:
            proc_pid = self.process.pid
            if self.process.returncode is None:
                with suppress(ProcessLookupError, Exception):
                    self.process.terminate()
                await self._force_taskkill_three_times(proc_pid)
                with suppress(ProcessLookupError, asyncio.TimeoutError, Exception):
                    await asyncio.wait_for(self.process.wait(), timeout=3)
            if self.process.returncode is not None:
                self.last_returncode = int(self.process.returncode)

        await self.clear()

    async def clear(self) -> None:
        """清空跟踪的进程信息"""

        if self._drain_tasks:
            for task in self._drain_tasks:
                if not task.done():
                    task.cancel()
            with suppress(asyncio.CancelledError):
                await asyncio.gather(*self._drain_tasks, return_exceptions=True)
            self._drain_tasks = []

        self.process = None
        self.target_process = None
        self._target_info = None
        self._target_create_time = None

    async def is_visible(self) -> bool:
        """检查主进程窗口是否可见"""

        hwnd = self.main_hwnd
        if hwnd is None:
            return False

        try:
            return window.is_visible(hwnd)
        except Exception:
            return False

    async def show_window(self) -> bool:
        """显示主进程窗口"""

        hwnd = self.main_hwnd
        if hwnd is None:
            return False

        try:
            return window.show_window(hwnd)
        except Exception:
            return False

    async def hide_window(self) -> bool:
        """隐藏主进程窗口"""
        hwnd = self.main_hwnd
        if hwnd is None:
            return False

        try:
            return window.hide_window(hwnd)
        except Exception:
            return False

    async def minimize_window(self) -> bool:
        """最小化主进程窗口"""

        hwnd = self.main_hwnd
        if hwnd is None:
            return False

        try:
            return window.minimize_window(hwnd)
        except Exception:
            return False

    async def activate_window(self) -> bool:
        """激活主进程窗口并将其置于前台"""

        hwnd = self.main_hwnd
        if hwnd is None:
            return False

        try:
            return window.activate_window(hwnd)
        except Exception:
            return False

    async def close(self) -> None:
        """请被管理进程自行退出，等它走完退出时的配置保存"""

        while await self.is_running():
            hwnd = self.main_hwnd
            if hwnd is None or not window.close_window(hwnd):
                return
            await asyncio.sleep(0.2)
