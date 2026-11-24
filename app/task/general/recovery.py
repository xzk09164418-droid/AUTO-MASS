"""通用脚本的进程身份追踪与自定义清理；不接管其他专项。"""

import asyncio
import ntpath
import os
from collections.abc import Awaitable, Callable

import psutil

from app.models.schema import GeneralTaskKillData
from app.utils import ProcessInfo, ProcessManager, get_logger
from app.utils.platform.common.process import _in_execution_session, match_process
from app.utils.platform.common.process_runner import ProcessRunner
from app.utils.platform.windows.session import get_process_session_id

logger = get_logger("通用脚本恢复")
CLEANUP_INTERVAL = 5
RECOVERY_SECONDS = 30 * 60
EXIT_STABLE_SECONDS = 30


class GeneralProcessManager(ProcessManager):
    """让调度器取消时也走同一清理入口，避免按原进程树绕过自定义清单。"""

    def __init__(self, cleanup: Callable[[], Awaitable[None]] | None = None):
        super().__init__()
        self.cleanup = cleanup

    async def kill(self) -> None:
        if self.cleanup is not None:
            await self.cleanup()
        else:
            await super().kill()


class CleanupFailed(RuntimeError):
    """目标进程未退出，禁止再启动恢复程序。"""


class ProcessTracker:
    def __init__(self) -> None:
        self.owned: dict[int, psutil.Process] = {}

    def remember(self, pid: int) -> None:
        try:
            proc = psutil.Process(pid)
            # 提前缓存创建时间，之后 is_running 才能识别 PID 复用。
            proc.create_time()
            self.owned[pid] = proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    async def cleanup_owned_tree(self) -> None:
        """手动暂停仅强清本次启动并确认归属的进程树，验证后才允许继续。"""
        for _ in range(3):
            await asyncio.to_thread(self.collect_children)
            for proc in tuple(self.owned.values()):
                if proc.pid == os.getpid() or not proc.is_running():
                    continue
                if not _in_execution_session(proc.pid):
                    raise CleanupFailed(f"PID {proc.pid} 不属于当前执行会话")
                if os.name == "nt":
                    result = await ProcessRunner.run_process(
                        "taskkill", "/F", "/T", "/PID", str(proc.pid), timeout=10
                    )
                    if result.returncode and proc.is_running():
                        logger.warning(
                            f"暂停清理 PID {proc.pid} 失败: {result.failure_detail()}"
                        )
                else:
                    proc.kill()
            await asyncio.sleep(CLEANUP_INTERVAL)
        alive = [str(proc.pid) for proc in self.owned.values() if proc.is_running()]
        if alive:
            raise CleanupFailed("暂停未完成，进程仍存活或无权清理: " + "、".join(alive))

    def find_owned(self, target: ProcessInfo) -> list[psutil.Process]:
        """仅在直接启动的进程及已确认的后代中查找主体，不按启动时间认领。"""
        self.collect_children()
        matched = []
        for proc in tuple(self.owned.values()):
            try:
                if not proc.is_running():
                    continue
                proc.info = proc.as_dict(attrs=["name", "exe", "cmdline"])
                if match_process(proc, target):
                    matched.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return matched

    def collect_children(self) -> None:
        for proc in tuple(self.owned.values()):
            try:
                if proc.is_running():
                    for child in proc.children(recursive=True):
                        child.create_time()
                        self.owned[child.pid] = child
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    @staticmethod
    def matches(proc: psutil.Process, targets: list[GeneralTaskKillData]) -> bool:
        name, path = proc.name(), proc.exe()
        return any(
            name.casefold() == target.Name.casefold()
            and ntpath.normcase(ntpath.normpath(path))
            == ntpath.normcase(ntpath.normpath(target.Path))
            for target in targets
        )

    def candidates(
        self, targets: list[GeneralTaskKillData], mode: str
    ) -> tuple[list[psutil.Process], list[str]]:
        processes = (
            tuple(self.owned.values()) if mode == "Tracked" else psutil.process_iter()
        )
        matched, inaccessible = [], []
        names = {target.Name.casefold() for target in targets}
        session = (
            get_process_session_id() if mode == "Session" and os.name == "nt" else None
        )
        for proc in processes:
            try:
                if not proc.is_running():
                    continue
                if mode != "Force" and not _in_execution_session(proc.pid):
                    continue
                if proc.name().casefold() not in names:
                    continue
                if session is not None:
                    try:
                        if get_process_session_id(proc.pid) != session:
                            continue
                    except OSError:
                        continue
                if self.matches(proc, targets):
                    proc.create_time()
                    matched.append(proc)
            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied:
                # 名称已匹配但路径读不到时不能冒险终止，也不能报告清理成功。
                try:
                    if proc.name().casefold() in names:
                        inaccessible.append(f"PID {proc.pid} 无法核验路径")
                except psutil.NoSuchProcess:
                    pass
                except psutil.AccessDenied:
                    if mode == "Tracked":
                        inaccessible.append(f"PID {proc.pid} 无法核验身份")
        return matched, inaccessible

    async def cleanup(self, targets: list[GeneralTaskKillData], mode: str) -> None:
        tree_members: dict[int, psutil.Process] = {}
        for attempt in range(3):
            if mode == "Tracked":
                await asyncio.to_thread(self.collect_children)
            matched, _ = await asyncio.to_thread(self.candidates, targets, mode)
            for proc in matched:
                try:
                    # 发送终止命令前重新核对身份，避免复用 PID 或路径快照。
                    if not proc.is_running() or not self.matches(proc, targets):
                        continue
                    if mode == "Force":
                        for child in proc.children(recursive=True):
                            child.create_time()
                            tree_members[child.pid] = child
                    args = ["taskkill", "/F"]
                    if mode == "Force":
                        args.append("/T")
                    args.extend(["/PID", str(proc.pid)])
                    if os.name == "nt":
                        result = await ProcessRunner.run_process(*args, timeout=10)
                        if result.returncode:
                            logger.warning(
                                f"第 {attempt + 1} 轮清理 PID {proc.pid}: {result.failure_detail()}"
                            )
                    else:
                        proc.kill()
                except psutil.NoSuchProcess:
                    continue
                except (psutil.AccessDenied, OSError, TimeoutError) as e:
                    logger.warning(f"第 {attempt + 1} 轮清理 PID {proc.pid} 失败: {e}")
            await asyncio.sleep(CLEANUP_INTERVAL)
        remaining, inaccessible = await asyncio.to_thread(
            self.candidates, targets, mode
        )
        alive = [f"PID {proc.pid}" for proc in remaining]
        for child in tree_members.values():
            if child.is_running():
                alive.append(f"子进程 PID {child.pid}")
        if alive or inaccessible:
            raise CleanupFailed("进程清理失败: " + "、".join(alive + inaccessible))
