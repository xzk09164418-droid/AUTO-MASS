"""队列内的手动暂停与导航；不拥有脚本进程，也不释放外部租约。"""

import asyncio
import time
import uuid
from contextlib import suppress


class QueueControlChanged(Exception):
    """准入期间用户改变了选择，返回队列门禁重新判定。"""


class QueueControl:
    def __init__(self) -> None:
        self.paused = False
        self.cleaning = False
        self.error = ""
        self.index = 0
        self.revision = 0
        self.changed = asyncio.Event()
        self.explicit_resume = False
        self.all_blocked = False
        self.all_blocked_notified = False
        self.prompt: dict | None = None
        self.boundary: str | None = None
        self.interrupted = False

    def touch(self) -> None:
        self.revision += 1
        self.changed.set()

    def pause(self) -> None:
        self.paused = True
        self.explicit_resume = False
        self.prompt = None
        self.boundary = None
        self.touch()

    def resume(self) -> None:
        if self.error or self.cleaning:
            raise RuntimeError(self.error or "当前脚本仍在清理，请等待暂停完成")
        self.paused = False
        self.explicit_resume = True
        self.prompt = None
        self.touch()

    def warn(self, message: str, *, action: str, buttons: bool = True) -> None:
        self.paused = True
        self.explicit_resume = False
        self.prompt = {
            "token": uuid.uuid4().hex,
            "message": message,
            "deadline": time.time() + 30 if buttons else None,
            "buttons": buttons,
        }
        self.boundary = action
        self.touch()

    def navigate(self, offset: int, *, count: int) -> None:
        if self.all_blocked:
            raise RuntimeError("所有项目均不可用，仅可使用启停键切换等待状态")
        target = self.index + offset
        self.pause()
        if target < 0:
            self.warn("已到首项；继续将从队列开头重新运行", action="restart")
        elif target >= count:
            self.warn("已到尾项；继续将跳过尾项并结束队列", action="finish")
        else:
            self.index = target
            self.touch()

    def act_on_prompt(self, token: str, action: str) -> None:
        if not self.prompt or self.prompt["token"] != token:
            raise ValueError("这条通知已失效")
        if not self.prompt["buttons"]:
            raise ValueError("暂无可运行项目，请使用启停键")
        if action == "pause":
            # 保持边界选择；取消倒计时不等于撤销所选操作。
            self.prompt = None
            self.paused = True
            self.touch()
        elif action == "continue":
            self.resume()
        else:
            raise ValueError("未知控制操作")

    async def wait_paused(self) -> None:
        while self.paused or self.cleaning or self.error:
            self.changed.clear()
            await self.changed.wait()

    async def wait_resource(self, awaitable) -> bool:
        """资源等待可被控制操作唤醒；不长时间占用热键处理锁。"""
        self.changed.clear()
        resource = asyncio.ensure_future(awaitable)
        control = asyncio.create_task(self.changed.wait())
        try:
            done, _ = await asyncio.wait(
                (resource, control), return_when=asyncio.FIRST_COMPLETED
            )
            if resource in done:
                await resource
                return not self.paused
            return False
        finally:
            for pending in (resource, control):
                if not pending.done():
                    pending.cancel()
                with suppress(asyncio.CancelledError):
                    await pending

    def snapshot(self, *, task_id: str, queue_id: str | None, name: str) -> dict:
        return {
            "taskId": task_id,
            "queueId": queue_id,
            "selectedTask": name,
            "index": self.index,
            "revision": self.revision,
            "paused": self.paused,
            "cleaning": self.cleaning,
            "error": self.error,
            "allBlocked": self.all_blocked,
            "prompt": self.prompt,
            "state": "清理失败"
            if self.error
            else "正在暂停"
            if self.cleaning
            else "已暂停"
            if self.paused
            else "运行／等待资源",
        }
