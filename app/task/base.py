"""脚本单账号自动运行的总时限保护（从任务开始到结束的上限时间，含全部重试）。"""

import asyncio
import time
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from app.core.ws import Publisher, protocol
from app.models.ConfigBase import ConfigBase
from app.models.schema import WSTaskNoticeData
from app.models.task import LogRecord, ScriptItem, TaskExecuteBase, UserItem
from app.task.proxy_helpers import push_dispatch_log
from app.utils.logger import get_logger

logger = get_logger("脚本运行")

_INFLIGHT_DETECTIONS: dict[str, asyncio.Task] = {}


def _running_inflight_detection(script_id: str) -> asyncio.Task | None:
    """回收已结束的在途检测句柄；返回仍在执行的句柄（无则 None）。"""

    task = _INFLIGHT_DETECTIONS.get(script_id)
    if task is None:
        return None
    if task.get_loop() is not asyncio.get_running_loop():
        _INFLIGHT_DETECTIONS.pop(script_id, None)
        return None
    if not task.done():
        return task
    _INFLIGHT_DETECTIONS.pop(script_id, None)
    with suppress(Exception):
        task.exception()
    return None


class ScriptAutoProxyBase(TaskExecuteBase):
    # 总时限涵盖从任务开始到结束的全部时间（含等待和全部重试），不随日志推进重置；
    # 超过上限时间视为失败并强制清理进程，收尾必须完成后再切换下一个任务，避免打扰下一个任务。
    wait_for_finalizer_on_cancel = True

    script_info: ScriptItem
    script_config: ConfigBase
    cur_user_item: UserItem
    cur_user_config: ConfigBase
    cur_user_log: LogRecord
    _user_scripts_started: bool = False
    _maintenance_reason: str | None = None
    _task_started_monotonic: float | None = None
    _MAINTENANCE_WATCH_INTERVAL_SECONDS = 30.0
    _MAINTENANCE_WATCH_CONFIRMATIONS = 2
    _MAINTENANCE_DETECT_TIMEOUT_SECONDS = 15.0

    @property
    def run_timeout_seconds(self) -> float:
        return self.script_config.get("Run", "HardTimeLimit") * 60

    def remaining_hard_timeout_seconds(self) -> float:
        """返回距离整个任务上限时间（从任务开始到结束的总时间）的剩余秒数。"""
        total = float(self.run_timeout_seconds)
        if self._task_started_monotonic is None:
            return total
        elapsed = time.monotonic() - self._task_started_monotonic
        return max(0.0, total - elapsed)

    async def run_user_scripts_before(self) -> None:
        """执行用户级任务前脚本；每用户一次，先于全部重试。"""

        from app.task.general.tools import execute_script_task

        self._user_scripts_started = True
        if self.cur_user_config.get("Info", "IfScriptBeforeTask"):
            await execute_script_task(
                Path(self.cur_user_config.get("Info", "ScriptBeforeTask")),
                "脚本前任务",
            )

    async def run_user_scripts_after(self) -> None:
        """执行用户级任务后脚本；前置未执行过时跳过，保证成对且只一次。"""

        from app.task.general.tools import execute_script_task

        if not self._user_scripts_started:
            return
        self._user_scripts_started = False
        if self.cur_user_config.get("Info", "IfScriptAfterTask"):
            await execute_script_task(
                Path(self.cur_user_config.get("Info", "ScriptAfterTask")),
                "脚本后任务",
            )

    async def skip_on_game_maintenance(self, detect: Callable[[], str | None]) -> bool:
        """游戏画面维护检测：命中维护弹窗文本则把当前用户记为维护跳过。"""

        maintenance_text = await self._detect_game_maintenance(detect)
        if maintenance_text is None:
            return False

        reason = f"游戏维护中，本次跳过（画面检测到：{maintenance_text}）"
        self.cur_user_item.status = "跳过"
        self.cur_user_item.maintenance_skipped = True
        self.cur_user_log.status = reason
        self.cur_user_log.content = [reason]
        logger.info(f"用户 {self.cur_user_item.name} - {reason}")
        await self.notify_maintenance_skip(reason)
        return True

    async def _detect_game_maintenance(
        self, detect: Callable[[], str | None]
    ) -> str | None:
        script_id = self.script_info.script_id
        if _running_inflight_detection(script_id) is not None:
            return None
        task = asyncio.ensure_future(asyncio.to_thread(detect))
        _INFLIGHT_DETECTIONS[script_id] = task
        try:
            text = await asyncio.wait_for(
                asyncio.shield(task),
                timeout=self._MAINTENANCE_DETECT_TIMEOUT_SECONDS,
            )
        except Exception as e:
            logger.warning(f"游戏画面维护检测失败（忽略，继续正常流程）: {e}")
            return None
        _running_inflight_detection(script_id)
        return text

    async def notify_maintenance_skip(self, reason: str) -> None:
        try:
            await push_dispatch_log(self.script_info, reason)
            await Publisher.send(
                id=self.task_info.task_id,
                type=protocol.TASK_NOTICE,
                data=WSTaskNoticeData(level="info", message=reason),
            )
        except Exception:
            logger.opt(exception=True).warning("维护跳过通知推送失败（忽略）")

    async def watch_game_maintenance(
        self, detect: Callable[[], str | None], stop: asyncio.Event
    ) -> None:
        hits = 0
        while not stop.is_set():
            await asyncio.sleep(self._MAINTENANCE_WATCH_INTERVAL_SECONDS)
            if stop.is_set():
                return
            maintenance_text = await self._detect_game_maintenance(detect)
            if maintenance_text is None:
                hits = 0
                continue
            hits += 1
            if hits < self._MAINTENANCE_WATCH_CONFIRMATIONS:
                continue
            if self.cur_user_log.status == "Success!":
                return
            try:
                self._maintenance_reason = (
                    f"游戏维护中，本次跳过（运行期间画面检测到：{maintenance_text}）"
                )
                self.cur_user_item.status = "跳过"
                self.cur_user_item.maintenance_skipped = True
                logger.info(
                    f"用户 {self.cur_user_item.name} - {self._maintenance_reason}"
                )
            finally:
                stop.set()
            return

    def clear_maintenance_hit(self) -> None:
        """成功结论优先：清除运行期晚到的维护命中标记，避免被误报成维护跳过。"""
        self.cur_user_item.maintenance_skipped = False
        self._maintenance_reason = None

    async def _finalize_task(self) -> None:
        """收尾时成对执行后置脚本；收尾被取消或异常中断也仍会尝试执行。"""

        try:
            await super()._finalize_task()
        finally:
            await self.run_user_scripts_after()
            if _running_inflight_detection(self.script_info.script_id) is not None:
                logger.warning("上一轮游戏画面维护检测仍未结束，本轮不再投递新检测")

    async def _run_main_task(self) -> None:
        self._task_started_monotonic = time.monotonic()
        timeout = asyncio.timeout(self.run_timeout_seconds)
        try:
            async with timeout:
                await self.main_task()
        except TimeoutError:
            # 脚本内部的 TimeoutError 仍交给原异常流程处理。
            if not timeout.expired():
                raise

            message = f"运行超过 {self.run_timeout_seconds / 60:g} 分钟，已终止"
            user = self.cur_user_item
            user.status = "异常"
            if user.log_record:
                record = user.log_record[max(user.log_record)]
            else:
                record = LogRecord()
                user.log_record[datetime.now()] = record
            record.status = message
            record.content.append(message)
            self.script_info.log = f"{message}\n正在强制清理相关程序 (taskkill /F /T x3)"
            logger.warning(f"{self.script_info.name} - {user.name}: {message}")
            # 超过总上限时间时立即执行强制清理，确保绝不打扰下一个任务
            kill_fn = getattr(self, "kill_managed_process", None)
            if callable(kill_fn):
                with suppress(Exception):
                    await kill_fn()
