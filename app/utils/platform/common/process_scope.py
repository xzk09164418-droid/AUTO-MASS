"""任务范围内的进程清理，不扫描或终止其他任务的进程。"""

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Protocol
from weakref import WeakKeyDictionary, WeakSet

from app.utils.logger import get_logger

logger = get_logger("任务进程清理")


class ManagedProcess(Protocol):
    async def kill(self) -> None: ...


class ProcessScope:
    def __init__(self) -> None:
        self.processes: WeakSet = WeakSet()
        self.children: set[ProcessScope] = set()
        self.requests: set[asyncio.Task] = set()

    def request_stop(self) -> None:
        for child in tuple(self.children):
            child.request_stop()
        for process in tuple(self.processes):
            self.requests.add(asyncio.create_task(process.kill()))

    async def wait_stops(self) -> None:
        if not self.requests:
            return
        pending = asyncio.gather(*self.requests, return_exceptions=True)
        cancelled = False
        while not pending.done():
            try:
                await asyncio.shield(pending)
            except asyncio.CancelledError:
                cancelled = True
        for result in pending.result():
            if isinstance(result, BaseException):
                logger.error(f"任务进程清理失败: {result}")
        if cancelled:
            raise asyncio.CancelledError


_current: ContextVar[ProcessScope | None] = ContextVar(
    "managed_process_scope", default=None
)
_tasks: WeakKeyDictionary = WeakKeyDictionary()


def register_process(process: ManagedProcess) -> None:
    scope = _current.get()
    if scope is not None:
        scope.processes.add(process)


def request_task_process_stop(task: asyncio.Task | None) -> None:
    scope = _tasks.get(task) if task is not None else None
    if scope is not None:
        scope.request_stop()


@asynccontextmanager
async def managed_process_scope():
    parent = _current.get()
    scope = ProcessScope()
    task = asyncio.current_task()
    token = _current.set(scope)
    _tasks[task] = scope
    if parent is not None:
        parent.children.add(scope)
    try:
        yield scope
    finally:
        try:
            await scope.wait_stops()
        finally:
            if parent is not None:
                parent.children.discard(scope)
            _tasks.pop(task, None)
            _current.reset(token)
