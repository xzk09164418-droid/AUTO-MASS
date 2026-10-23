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
import time
import uuid
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Literal

import app.task as task
from app.core.child_session import ChildSessionManager
from app.core.desktop_guard import ensure_desktop_available
from app.models.config import CLASS_BOOK
from app.models.schema import (
    ReplayRecord,
    TaskRuntimeSnapshot,
    TaskRuntimeSnapshotItem,
    TaskStatusOut,
    WSPowerSignData,
    WSTaskCompletedData,
    WSTaskCreatedData,
    WSTaskCyclePreviewData,
    WSTaskInfoUpdatedData,
    WSTaskLogUpdatedData,
    WSTaskNoticeData,
    WSTaskScriptIdentityData,
)
from app.models.task import (
    ScriptItem,
    TaskExecuteBase,
    TaskItem,
    TaskTriggerSource,
    UserItem,
)
from app.runtime_tasks import RuntimeTasks
from app.task.general.tools import execute_script_task
from app.tools.push_log import build_task_result_text
from app.utils import LazyProxy, get_logger
from app.utils.constants import UTC4

from .config import (
    BAAHConfig,
    BetterGIConfig,
    Config,
    GeneralConfig,
    HSRConfig,
    M9AConfig,
    MaaConfig,
    MaaEndConfig,
    MaaFWConfig,
    MSSConfig,
    OkNteConfig,
    OkwwConfig,
    SrcConfig,
    WhimboxConfig,
    ZzzOdConfig,
)
from .queue_cycle import (
    SUCCESS_USER_STATUSES,
    CycleEntry,
    collect_cycle_entries,
    due_entries,
    format_cycle_time,
    format_next_run,
    is_empty_cycle_time,
    is_script_success,
    next_after_finish,
    next_after_start,
    parse_cycle_time,
    sort_for_preview,
)
from .ws import MainConnection, Publisher, protocol

System = LazyProxy("app.services", "System")

if TYPE_CHECKING:
    from .notify import TaskCommunitySignNotification

_SCRIPT_TYPE_BY_CLASS = {cls.__name__: key for key, cls in CLASS_BOOK.items()}

_RECENT_RESULTS_MAX = 200
_RECENT_RESULTS_TTL_SECONDS = 1800


@dataclass(frozen=True)
class _ManagerBuildContext:
    """构造脚本调度器所需的额外输入（占用归属与互斥资源）。"""

    script_uid: uuid.UUID
    reservation_owner: str
    root_paths: tuple[Path, ...]
    emulator_key: str | None
    reservations: "_ScriptTaskReservations"


def _build_src_manager(
    script_item: ScriptItem, ctx: _ManagerBuildContext
) -> TaskExecuteBase:
    if not ctx.root_paths:
        raise RuntimeError("SRC 路径占用未初始化")
    return task.SrcManager(
        script_item,
        reserved_src_root_path=ctx.root_paths[0],
        reserve_src_root=lambda root_path: ctx.reservations.try_acquire(
            ctx.script_uid,
            ctx.reservation_owner,
            root_paths=(root_path,),
            emulator_key=ctx.emulator_key,
        ),
    )


_MANAGER_BOOK: dict[
    type, Callable[[ScriptItem, _ManagerBuildContext], TaskExecuteBase]
] = {
    MaaConfig: lambda script_item, _ctx: task.MaaManager(script_item),
    GeneralConfig: lambda script_item, _ctx: task.GeneralManager(script_item),
    OkwwConfig: lambda script_item, _ctx: task.OkwwManager(script_item),
    OkNteConfig: lambda script_item, _ctx: task.OkNteManager(script_item),
    MaaEndConfig: lambda script_item, _ctx: task.MaaEndManager(script_item),
    M9AConfig: lambda script_item, _ctx: task.MaaFWEmbeddedManager(script_item),
    MSSConfig: lambda script_item, _ctx: task.MaaFWEmbeddedManager(script_item),
    HSRConfig: lambda script_item, _ctx: task.HSRManager(script_item),
    BetterGIConfig: lambda script_item, _ctx: task.BetterGIManager(script_item),
    ZzzOdConfig: lambda script_item, _ctx: task.ZzzOdManager(script_item),
    BAAHConfig: lambda script_item, _ctx: task.BAAHManager(script_item),
    MaaFWConfig: lambda script_item, _ctx: task.MaaFWEmbeddedManager(script_item),
    WhimboxConfig: lambda script_item, _ctx: task.WhimboxManager(script_item),
    SrcConfig: _build_src_manager,
}

logger = get_logger("业务调度")

CYCLE_IDLE_SLEEP_SECONDS = 60
CYCLE_MAX_SLEEP_SECONDS = 30
CYCLE_RETRY_SLEEP_SECONDS = 30
CYCLE_PREVIEW_REFRESH_SECONDS = 5
CYCLE_PREVIEW_SIZE = 4


class _ScriptTaskReservations:
    """为脚本任务提供原子、带所有者的进程内占用。"""

    def __init__(self) -> None:
        self._owners: dict[tuple[str, str], str] = {}
        self._owner_keys: dict[str, dict[uuid.UUID, set[tuple[str, str]]]] = {}
        self._reserved_root_paths: dict[tuple[str, str], Path] = {}

    @staticmethod
    def _resource_keys(
        script_uid: uuid.UUID,
        root_paths: tuple[Path, ...],
        emulator_key: str | None,
    ) -> set[tuple[str, str]]:
        keys = {("script", str(script_uid))}
        for root_path in root_paths:
            keys.add(("install-root", _normalize_src_root_path(root_path)))
        if emulator_key is not None:
            keys.add(("emulator", emulator_key))
        return keys

    def try_acquire(
        self,
        script_uid: uuid.UUID,
        owner: str,
        *,
        root_paths: Iterable[Path] = (),
        emulator_key: str | None = None,
    ) -> bool:
        resolved_root_paths = tuple(path.resolve() for path in root_paths)
        keys = self._resource_keys(script_uid, resolved_root_paths, emulator_key)
        if any(self._owners.get(key) not in (None, owner) for key in keys):
            return False

        for key, existing_owner in self._owners.items():
            if key[0] != "install-root" or existing_owner == owner:
                continue
            existing_src_root_path = self._reserved_root_paths.get(key)
            if existing_src_root_path is None:
                continue
            existing_root_path = _normalize_src_root_path(existing_src_root_path)
            for root_path in resolved_root_paths:
                root_path_key = _normalize_src_root_path(root_path)
                if (
                    root_path_key == existing_root_path
                    or _is_relative_src_root(root_path_key, existing_root_path)
                    or _is_relative_src_root(existing_root_path, root_path_key)
                ):
                    return False

        for key in keys:
            self._owners[key] = owner
        self._owner_keys.setdefault(owner, {}).setdefault(script_uid, set()).update(
            keys
        )
        for root_path in resolved_root_paths:
            root_key = ("install-root", _normalize_src_root_path(root_path))
            self._reserved_root_paths[root_key] = root_path
        return True

    def release(self, script_uid: uuid.UUID, owner: str) -> bool:
        script_key = ("script", str(script_uid))
        if self._owners.get(script_key) != owner:
            return False
        keys = self._owner_keys.get(owner, {}).pop(script_uid, set())
        for key in keys:
            key_still_reserved = any(
                key in other_keys
                for other_keys in self._owner_keys.get(owner, {}).values()
            )
            if not key_still_reserved and self._owners.get(key) == owner:
                self._owners.pop(key)
            if key[0] == "install-root" and not key_still_reserved:
                self._reserved_root_paths.pop(key, None)
        if not self._owner_keys.get(owner):
            self._owner_keys.pop(owner, None)
        return True


def _normalize_src_root_path(path: Path) -> str:
    return os.path.normcase(str(path)).casefold()


def _is_relative_src_root(path: Path | str, parent: Path | str) -> bool:
    path = str(path)
    parent = str(parent).rstrip(os.sep)
    return path.startswith(parent + os.sep)


def _exclusive_resources(
    script_config: object,
) -> tuple[tuple[Path, ...], str | None]:
    roots: tuple[Path, ...] = ()
    if isinstance(script_config, (MaaConfig, SrcConfig, MaaEndConfig)):
        raw = str(script_config.get("Info", "Path") or "").strip()
        roots = (Path(raw),) if raw else ()
    return roots, _emulator_key(script_config)


def _emulator_key(script_config: object) -> str | None:
    if isinstance(script_config, (MaaConfig, SrcConfig, MaaFWConfig, BAAHConfig)):
        emulator_id = script_config.get("Emulator", "Id")
        index = script_config.get("Emulator", "Index")
    elif isinstance(script_config, MaaEndConfig):
        emulator_id = script_config.get("Game", "EmulatorId")
        index = script_config.get("Game", "EmulatorIndex")
    elif isinstance(script_config, GeneralConfig):
        if not script_config.get("Game", "Enabled") or (
            script_config.get("Game", "Type") != "Emulator"
        ):
            return None
        emulator_id = script_config.get("Game", "EmulatorId")
        index = script_config.get("Game", "EmulatorIndex")
    else:
        return None
    if str(emulator_id or "") in ("", "-") or str(index or "") in ("", "-"):
        return None
    return f"{emulator_id}:{index}"


@dataclass(eq=False)
class _ReplayRequest:
    script: ScriptItem
    user: UserItem | None
    explicit_reason: bool
    reason: str
    history_paths: list[str]


@dataclass
class TaskInfo(TaskItem):
    community_sign_notification: "TaskCommunitySignNotification | None" = field(
        default=None, init=False, repr=False
    )
    replay_cancelled: bool = field(default=False, init=False, repr=False)
    _replay_runs: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _replay_active: dict[str, int] = field(default_factory=dict, init=False, repr=False)
    _replay_candidates: dict[str, dict[str, UserItem]] = field(
        default_factory=dict, init=False, repr=False
    )
    _replay_seen: set[tuple[str, str | None]] = field(
        default_factory=set, init=False, repr=False
    )
    _replay_requests: dict[str, dict[str, _ReplayRequest]] = field(
        default_factory=dict, init=False, repr=False
    )

    def begin_script_run(self, script: ScriptItem) -> None:
        self.flush_replays(script)
        previous = self._replay_runs.get(script.script_id)
        self._replay_seen = {key for key in self._replay_seen if key[0] != previous}
        self._replay_runs[script.script_id] = str(uuid.uuid4())
        self._replay_candidates.pop(script.script_id, None)
        self._replay_active.pop(script.script_id, None)
        script.user_list = []
        script.current_index = -1
        script.status = "等待"

    def on_status_changed(
        self, item: UserItem | ScriptItem, previous: str | None, status: str
    ) -> None:
        if self.mode != "AutoProxy" or self.replay_cancelled:
            return
        script = (
            item
            if isinstance(item, ScriptItem)
            else next(
                (
                    script
                    for script in self.script_list
                    if any(user is item for user in script.user_list)
                ),
                None,
            )
        )
        if script is None:
            return
        if isinstance(item, UserItem):
            candidates = self._replay_candidates.setdefault(script.script_id, {})
            if status != "异常":
                candidates.pop(item.user_id, None)
            elif self._replay_active.get(script.script_id, 0):
                candidates[item.user_id] = item
            else:
                self._request_replay(script, item)
        elif status == "异常" and not self._replay_active.get(script.script_id, 0):
            self._request_replay(script)

    def on_user_execution_started(self, script: ScriptItem) -> None:
        self._replay_active[script.script_id] = (
            self._replay_active.get(script.script_id, 0) + 1
        )

    def on_user_execution_finished(self, script: ScriptItem) -> None:
        active = max(0, self._replay_active.get(script.script_id, 0) - 1)
        self._replay_active[script.script_id] = active
        if active:
            return
        candidates = self._replay_candidates.pop(script.script_id, {})
        for user in candidates.values():
            if user.status == "异常":
                self._request_replay(script, user)
        if script.status == "异常":
            self._request_replay(script)

    def _request_replay(
        self,
        script: ScriptItem | None,
        user: UserItem | None = None,
        *,
        reason: str = "",
    ) -> None:
        if self.mode != "AutoProxy" or self.replay_cancelled:
            return
        try:
            if not Config.get("Replay", "Enabled"):
                return
            script_id = script.script_id if script else "scheduler"
            run_id = self._replay_runs.setdefault(script_id, str(uuid.uuid4()))
            key = (run_id, user.user_id if user else None)
            if key in self._replay_seen or (
                user is None and any(seen[0] == run_id for seen in self._replay_seen)
            ):
                return
            self._replay_seen.add(key)
            options = Config.obs_replay_options()
            record = ReplayRecord(
                replayId=str(uuid.uuid4()),
                taskId=self.task_id,
                scriptId=script.script_id if script else None,
                userId=user.user_id if user else None,
                scriptName=script.name if script else "调度任务",
                userName=user.name if user else "",
                failedAt=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                reason=reason or self._replay_reason(user),
                historyPaths=self._replay_history_paths(script, user),
            )
            RuntimeTasks.spawn(
                self._save_replay(options, record), name=f"obs-replay:{record.replayId}"
            )
            if script is not None:
                self._replay_requests.setdefault(script_id, {})[record.replayId] = (
                    _ReplayRequest(
                        script=script,
                        user=user,
                        explicit_reason=bool(reason),
                        reason=record.reason,
                        history_paths=list(record.historyPaths),
                    )
                )
        except Exception as error:
            logger.warning(f"无法安排失败回放: {type(error).__name__}")

    @staticmethod
    def _replay_reason(user: UserItem | None) -> str:
        if user is None:
            return "脚本执行异常"
        return user.result if user.log_record else "账号执行异常"

    @staticmethod
    def _replay_history_paths(
        script: ScriptItem | None, user: UserItem | None
    ) -> list[str]:
        if script is None or user is None:
            return []
        try:
            script_config = Config.ScriptConfig[uuid.UUID(script.script_id)]
        except (KeyError, ValueError):
            script_config = None
        if isinstance(script_config, MaaFWConfig):
            from app.task.MaaFW.tools.embedded.history_paths import (
                maafw_history_log_path,
            )

            return [
                str(
                    maafw_history_log_path(user.name, start, script.name).with_suffix(
                        ".json"
                    )
                )
                for start in user.log_record
            ]
        return [
            str(
                Config.build_history_log_path(
                    script_name=script.name,
                    user_name=user.name,
                    log_time=start.astimezone(UTC4),
                ).with_suffix(".json")
            )
            for start in user.log_record
        ]

    def flush_replays(self, script: ScriptItem | None = None) -> None:
        try:
            if script is None:
                pending = list(self._replay_requests.values())
                self._replay_requests.clear()
            else:
                pending = [self._replay_requests.pop(script.script_id, {})]
            for requests in pending:
                for replay_id, request in requests.items():
                    reason = (
                        request.reason
                        if request.explicit_reason
                        else self._replay_reason(request.user)
                    )
                    history_paths = self._replay_history_paths(
                        request.script, request.user
                    )
                    if (
                        reason == request.reason
                        and history_paths == request.history_paths
                    ):
                        continue
                    RuntimeTasks.spawn(
                        self._update_replay(replay_id, reason, history_paths),
                        name=f"obs-replay-update:{replay_id}",
                    )
        except Exception as error:
            logger.warning(f"无法补齐失败回放信息: {type(error).__name__}")

    async def _save_replay(self, options, record: ReplayRecord) -> None:
        from app.services.obs_replay import ObsReplay

        try:
            await ObsReplay.save(options, record)
        except Exception as error:
            logger.warning(f"失败回放未保存: {error}")
            await Publisher.send(
                id=self.task_id,
                type=protocol.TASK_NOTICE,
                data=WSTaskNoticeData(
                    level="warning", message=f"失败回放未保存：{error}"
                ),
            )

    async def _update_replay(
        self, replay_id: str, reason: str, history_paths: list[str]
    ) -> None:
        from app.services.obs_replay import ObsReplay

        await ObsReplay.update_record(
            replay_id, reason=reason, history_paths=history_paths
        )

    async def on_change(self):
        await Publisher.send(
            id=self.task_id,
            type=protocol.TASK_INFO_UPDATED,
            data=WSTaskInfoUpdatedData(
                task_info=self.asdict,
                cycleNextList=[
                    WSTaskCyclePreviewData(**item) for item in self.cycle_next_list
                ],
            ),
        )
        if self.current_index != -1:
            script = self.script_list[self.current_index]
            log = script.log
            if (
                log == self._last_pushed_log
                and script.log_first_line == self._last_pushed_log_first_line
            ):
                return
            if (
                self._last_pushed_log
                and log.startswith(self._last_pushed_log)
                and script.log_first_line == self._last_pushed_log_first_line
            ):
                payload = log[len(self._last_pushed_log) :]
                append = True
                first_line = WSTaskLogUpdatedData.model_fields["firstLine"].default
            else:
                payload = log[-200_000:]
                append = False
                dropped_hint = log[: len(log) - len(payload)]
                first_line = script.log_first_line + dropped_hint.count("\n")
            self._log_seq += 1
            await Publisher.send(
                id=self.task_id,
                type=protocol.TASK_LOG_UPDATED,
                data=WSTaskLogUpdatedData(
                    log=payload,
                    seq=self._log_seq,
                    append=append,
                    firstLine=first_line,
                ),
            )
            self._last_pushed_log = log
            if not append:
                self._last_pushed_log_first_line = script.log_first_line


class Task(TaskExecuteBase):
    wait_for_finalizer_on_cancel = True

    def __init__(
        self,
        task_info: TaskInfo,
        script_identities: list[WSTaskScriptIdentityData],
        script_reservations: _ScriptTaskReservations | None = None,
        script_run_days: list[list[str]] | None = None,
        on_finished: Callable[[TaskStatusOut], None] | None = None,
    ):
        super().__init__()
        self.task_info = task_info
        self.script_identities = script_identities
        self._on_finished = on_finished
        self.script_run_days = script_run_days
        self.run_weekday = datetime.now().strftime("%A")
        self.script_reservations = script_reservations or _ScriptTaskReservations()
        self.is_closing = False
        self._exit_result = "success"
        self._exit_error: str | None = None
        self._queue_run_started = False
        self._queue_before_script_ran = False
        self._queue_after_script_ran = False
        self._queue_script_task: asyncio.Task | None = None
        # 支持全局热键上/下一个任务跳转
        self._active_child_task: asyncio.Task | None = None
        self._pending_nav_offset: int | None = None

    def request_navigate(self, offset: int) -> bool:
        """请求跳转到上一个（offset=-1）或下一个（offset=+1）子任务。"""
        if self.is_closing:
            return False
        self._pending_nav_offset = offset
        if self._active_child_task is not None and not self._active_child_task.done():
            from app.utils.platform.common.process_scope import (
                request_task_process_stop,
            )

            request_task_process_stop(self._active_child_task)
            self._active_child_task.cancel()
            return True
        return False

    def _record_error(self, error: str) -> None:
        if self._exit_result == "success":
            self._exit_result = "error"
            self._exit_error = error

    def cancel(self) -> bool:
        self.task_info.replay_cancelled = True
        self.stopped_manually = True
        if (
            self._queue_after_script_ran
            and self._queue_script_task is not None
            and not self._queue_script_task.done()
        ):
            self._queue_script_task.cancel()
        cancelled = super().cancel()
        if cancelled and self._exit_result == "success":
            self._exit_result = "cancelled"
            self._exit_error = "任务执行被取消"
        return cancelled

    async def prepare(self):
        script_ids = [identity.scriptId for identity in self.script_identities]

        self.task_info.script_list = [
            ScriptItem(
                script_id=script_id,
                status="等待",
                name=Config.ScriptConfig[uuid.UUID(script_id)].get("Info", "Name"),
                user_list=(
                    []
                    if self.task_info.mode == "AutoProxy"
                    else [
                        UserItem(
                            user_id=str(uuid.uuid4()), name="暂未加载", status="等待"
                        )
                    ]
                ),
            )
            for script_id in script_ids
        ]
        self.task_info.schedule_on_change()

        logger.success(
            f"任务 {self.task_info.task_id} 检索完成，包含 {len(self.task_info.script_list)} 个脚本项"
        )

    async def main_task(self):
        from app.services.telemetry import (
            observe_span,
            record_count,
            record_distribution,
        )

        attributes = {
            "mode": self.task_info.mode,
            "trigger": self.task_info.trigger_source,
        }
        started_at = time.perf_counter()
        outcome = "success"

        try:
            with observe_span(
                name="AUTO-MAS task",
                op="auto_mas.task.run",
                attributes=attributes,
                force_transaction=True,
            ):
                await self._run_main_task()
                outcome = self._exit_result
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        except Exception:
            outcome = "error"
            raise
        finally:
            metric_attributes = {**attributes, "outcome": outcome}
            record_count("auto_mas.task.runs", attributes=metric_attributes)
            record_distribution(
                "auto_mas.task.duration",
                (time.perf_counter() - started_at) * 1000,
                unit="millisecond",
                attributes=metric_attributes,
            )

    @contextmanager
    def _observe_script_run(
        self, script_item: ScriptItem, script_config
    ) -> Iterator[None]:
        from app.services.telemetry import record_count

        outcome = "error"
        try:
            yield
            user_statuses = [
                user.status
                for user in script_item.user_list
                if not user.maintenance_skipped
            ]
            if script_item.status == "异常":
                outcome = "failed"
            elif script_item.user_list and not user_statuses:
                outcome = "skipped"
            elif not user_statuses:
                outcome = "failed" if script_item.status == "异常" else "no_user"
            elif all(status in SUCCESS_USER_STATUSES for status in user_statuses):
                outcome = "success"
            elif "异常" in user_statuses:
                outcome = "failed"
            else:
                outcome = "incomplete"
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        finally:
            record_count(
                "auto_mas.script.runs",
                attributes={
                    "script_type": _SCRIPT_TYPE_BY_CLASS.get(
                        type(script_config).__name__, "unknown"
                    ),
                    "mode": self.task_info.mode,
                    "outcome": outcome,
                },
            )

    def _build_task_item(
        self,
        script_item: ScriptItem,
        script_config,
        *,
        script_uid: uuid.UUID,
        reservation_owner: str,
        root_paths: tuple[Path, ...],
        emulator_key: str | None,
    ):
        build = _MANAGER_BOOK.get(type(script_config))
        if build is None:
            return None
        return build(
            script_item,
            _ManagerBuildContext(
                script_uid=script_uid,
                reservation_owner=reservation_owner,
                root_paths=root_paths,
                emulator_key=emulator_key,
                reservations=self.script_reservations,
            ),
        )

    async def _run_cycle_task(self) -> None:
        if self.task_info.queue_id is None:
            raise RuntimeError("循环运行必须指定队列")

        queue_uid = uuid.UUID(self.task_info.queue_id)
        logger.info(f"循环队列开始运行: {queue_uid}")
        try:
            await self.prepare()
            await self._notice_scope_skipped_scripts()
            self._queue_run_started = True
            await self._run_queue_extra_script(
                queue_uid,
                "IfScriptBeforeTask",
                "ScriptBeforeTask",
                "队列运行前脚本",
            )
            while True:
                await self._run_cycle_round(queue_uid)
        finally:
            Config.running_cycle_queue_ids.discard(queue_uid)
            self.task_info.cycle_next_list = []
            logger.info(f"循环队列停止运行: {queue_uid}")

    async def _run_cycle_round(self, queue_uid: uuid.UUID) -> None:
        queue = Config.QueueConfig[queue_uid]
        now = datetime.now()
        entries = self._collect_entries(queue_uid)

        for entry in entries:
            queue_item = queue.QueueItem[uuid.UUID(entry.queue_item_id)]
            stored = parse_cycle_time(queue_item.get("Schedule", "NextRunAt"))
            if is_empty_cycle_time(stored) and entry.next_run_at > now:
                await queue_item.set(
                    "Schedule", "NextRunAt", format_cycle_time(entry.next_run_at)
                )

        await self._publish_cycle_preview(entries)

        if not entries:
            await asyncio.sleep(CYCLE_IDLE_SLEEP_SECONDS)
            return

        pending = due_entries(entries)
        if not pending:
            await self._sleep_until(min(entry.next_run_at for entry in entries))
            return

        await self._run_due_entries(queue_uid, pending)

    async def _sleep_until(self, target: datetime) -> None:
        delay = (target - datetime.now()).total_seconds()
        await asyncio.sleep(max(1.0, min(delay, CYCLE_MAX_SLEEP_SECONDS)))

    async def _run_due_entries(
        self, queue_uid: uuid.UUID, pending: list[CycleEntry]
    ) -> None:
        results: list[str] = []
        for stale in pending:
            # 循环队列相邻两个子任务间隔检查是否有其他程序需要连接本地远程桌面
            await ChildSessionManager.wait_if_external_requested(
                boundary_label=f"循环队列[{queue_uid}]子任务间隔"
            )
            entries = self._collect_entries(queue_uid)
            entry = next(
                (e for e in entries if e.queue_item_id == stale.queue_item_id), None
            )
            if entry is None or not entry.is_due:
                continue
            results.append(await self._run_cycle_entry(queue_uid, entry, entries))

        if results and not any(result in ("success", "skipped") for result in results):
            await asyncio.sleep(CYCLE_RETRY_SLEEP_SECONDS)

    def _scope_skipped_script_ids(self) -> set[str]:
        scope = self.task_info.user_ids_by_script
        if not scope:
            return set()
        return {script_id for script_id, user_ids in scope.items() if not user_ids}

    async def _notice_scope_skipped_scripts(self) -> None:
        skipped = self._scope_skipped_script_ids()
        if not skipped:
            return
        for script_item in self.task_info.script_list:
            if script_item.script_id not in skipped:
                continue
            script_item.status = "跳过"
            logger.info(f"跳过任务: {script_item.script_id}, 本次未选择任何用户")
            await Publisher.send(
                id=self.task_info.task_id,
                type=protocol.TASK_NOTICE,
                data=WSTaskNoticeData(
                    level="warning",
                    message=f"任务 {script_item.name} 本次未选择任何用户, 已跳过",
                ),
            )

    def _collect_entries(self, queue_uid: uuid.UUID) -> list[CycleEntry]:
        entries = collect_cycle_entries(
            Config.QueueConfig[queue_uid], Config.ScriptConfig, datetime.now()
        )
        skipped = self._scope_skipped_script_ids()
        if not skipped:
            return entries
        return [entry for entry in entries if entry.script_id not in skipped]

    async def _run_cycle_entry(
        self,
        queue_uid: uuid.UUID,
        entry: CycleEntry,
        entries: list[CycleEntry],
    ) -> Literal["success", "failed", "blocked", "skipped"]:
        try:
            queue_item = Config.QueueConfig[queue_uid].QueueItem[
                uuid.UUID(entry.queue_item_id)
            ]
        except KeyError:
            raise RuntimeError(
                "循环队列的结构在运行中被改动，已停止循环，请重新启动"
            ) from None
        script_list = self.task_info.script_list
        if (
            entry.index >= len(script_list)
            or script_list[entry.index].script_id != entry.script_id
        ):
            raise RuntimeError("循环队列的结构在运行中被改动，已停止循环，请重新启动")
        script_uid = uuid.UUID(entry.script_id)
        script_item = script_list[entry.index]

        if script_uid not in Config.ScriptConfig:
            self.task_info.begin_script_run(script_item)
            script_item.status = "异常"
            logger.warning(f"循环跳过: {script_uid} 对应脚本已被删除")
            return "failed"

        script_config = Config.ScriptConfig[script_uid]
        self.task_info.current_index = entry.index
        root_paths, emulator_key = _exclusive_resources(script_config)
        reservation_owner = self.task_info.task_id

        if script_config.is_locked or not self.script_reservations.try_acquire(
            script_uid,
            reservation_owner,
            root_paths=root_paths,
            emulator_key=emulator_key,
        ):
            script_item.status = "等待"
            logger.info(f"循环等待: {entry.script_name} 已被其他任务占用")
            return "blocked"

        self.task_info.begin_script_run(script_item)
        started_at = datetime.now()
        previous_started_at = queue_item.get("Data", "LastCycleStartedAt")
        success = False
        ChildSessionManager.enter_subtask()
        try:
            await queue_item.set(
                "Data", "LastCycleStartedAt", format_cycle_time(started_at)
            )
            if queue_item.get("Schedule", "IntervalAnchor") == "start":
                await queue_item.set(
                    "Schedule",
                    "NextRunAt",
                    format_next_run(next_after_start(queue_item, started_at)),
                )

            task_item = self._build_task_item(
                script_item,
                script_config,
                script_uid=script_uid,
                reservation_owner=reservation_owner,
                root_paths=root_paths,
                emulator_key=emulator_key,
            )
            if task_item is None:
                script_item.status = "异常"
                logger.error(f"不支持的脚本类型: {type(script_config).__name__}")
            else:
                self.task_info.current_index = entry.index
                script_item.status = "运行"
                logger.info(f"循环任务开始: {script_uid}")
                await self._publish_cycle_preview(entries, running=entry)

                with self._observe_script_run(script_item, script_config):
                    await self._spawn_with_preview(task_item, entry, queue_uid)

                success = is_script_success(
                    script_item.status,
                    (user.status for user in script_item.user_list),
                )
        except Exception as e:
            script_item.status = "异常"
            logger.exception(f"循环任务出现异常: {entry.script_name}: {e}")
        finally:
            ChildSessionManager.exit_subtask()
            self.script_reservations.release(script_uid, reservation_owner)
            self.task_info.flush_replays(script_item)

        if (
            script_item.status == "跳过"
            and script_item.user_list
            and all(user.maintenance_skipped for user in script_item.user_list)
        ):
            await queue_item.set("Data", "LastCycleStartedAt", previous_started_at)
            await self._advance_cycle_after_maintenance(queue_item)
            return "skipped"

        finished_at = datetime.now()
        await queue_item.set(
            "Data", "LastCycleFinishedAt", format_cycle_time(finished_at)
        )
        if queue_item.get("Schedule", "IntervalAnchor") == "start":
            next_run_at = next_after_start(queue_item, started_at, after=finished_at)
        else:
            next_run_at = next_after_finish(queue_item, finished_at)
        await queue_item.set("Schedule", "NextRunAt", format_next_run(next_run_at))

        if not success:
            logger.warning(f"循环任务未成功: {entry.script_name}")
        return "success" if success else "failed"

    async def _advance_cycle_after_maintenance(self, queue_item) -> None:
        skipped_at = datetime.now()
        if queue_item.get("Schedule", "IntervalAnchor") == "start":
            next_run_at = next_after_start(queue_item, skipped_at)
        else:
            next_run_at = next_after_finish(queue_item, skipped_at)
        await queue_item.set("Schedule", "NextRunAt", format_next_run(next_run_at))

    async def _spawn_with_preview(
        self,
        task_item: TaskExecuteBase,
        entry: CycleEntry,
        queue_uid: uuid.UUID,
    ) -> None:
        child = self.spawn(task_item)
        self._active_child_task = child
        refresher = RuntimeTasks.spawn(
            self._refresh_preview_while_running(queue_uid, entry),
            name=f"cycle-preview:{self.task_info.task_id}",
        )
        try:
            await child
        except asyncio.CancelledError:
            if self._pending_nav_offset is not None and not self.is_closing:
                self._pending_nav_offset = None
                current_task = asyncio.current_task()
                if current_task is not None:
                    while current_task.cancelling():
                        current_task.uncancel()
                logger.info(f"循环队列子任务已响应热键跳过: {entry.script_name}")
                return
            raise
        finally:
            self._active_child_task = None
            if refresher is not None:
                refresher.cancel()

    async def _refresh_preview_while_running(
        self, queue_uid: uuid.UUID, running: CycleEntry
    ) -> None:
        while True:
            await asyncio.sleep(CYCLE_PREVIEW_REFRESH_SECONDS)
            await self._publish_cycle_preview(
                self._collect_entries(queue_uid), running=running
            )

    async def _publish_cycle_preview(
        self, entries: list[CycleEntry], running: CycleEntry | None = None
    ) -> None:
        preview: list[dict] = []
        for entry in sort_for_preview(entries):
            preview.append(
                {
                    "queueItemId": entry.queue_item_id,
                    "scriptId": entry.script_id,
                    "scriptName": entry.script_name,
                    "nextRunAt": format_cycle_time(entry.next_run_at),
                    "isDue": entry.is_due,
                    "isRunning": running is not None
                    and entry.queue_item_id == running.queue_item_id,
                }
            )

        preview.sort(key=lambda item: not item["isRunning"])
        self.task_info.cycle_next_list = preview[:CYCLE_PREVIEW_SIZE]
        self.task_info.schedule_on_change()

    async def _run_main_task(self):
        if self.task_info.is_cycle:
            await self._run_cycle_task()
            return

        if self.task_info.mode == "AutoProxy":
            from app.core.notify import TaskCommunitySignNotification
            from app.core.timer import MainTimer

            sign_source = {
                "scheduled_task": "task_scheduled",
                "manual_task": "task_manual",
                "startup_task": "task_startup",
            }.get(self.task_info.trigger_source, "task_manual")
            community_sign = TaskCommunitySignNotification(self.task_info)
            self.task_info.community_sign_notification = community_sign
            MainTimer.schedule_community_for_task(
                source=sign_source, on_completed=community_sign.receive
            )

        await self.prepare()

        if self.task_info.queue_id is not None:
            self._queue_run_started = True
            await self._run_queue_extra_script(
                self.task_info.queue_id,
                "IfScriptBeforeTask",
                "ScriptBeforeTask",
                "队列运行前脚本",
            )

        logger.info(
            f"开始运行任务: {self.task_info.task_id}, 模式: {self.task_info.mode}"
        )

        start_index = 0
        if (
            getattr(self.task_info, "resume_from_script_id", None)
            and self.task_info.queue_id is not None
        ):
            resume_id = str(self.task_info.resume_from_script_id)
            for idx, item in enumerate(self.task_info.script_list):
                if item.script_id == resume_id:
                    start_index = idx
                    break
            else:
                logger.warning(
                    f"未找到 resume_from_script_id={resume_id}，将从队列首项开始执行"
                )

        for i in range(start_index):
            self.task_info.script_list[i].status = "跳过"

        await ensure_desktop_available()
        await self._run_script_list(start_index)

    async def _run_queue_extra_script(
        self, queue_id: str | uuid.UUID, if_key: str, path_key: str, label: str
    ) -> bool:
        if self.stopped_manually or self.is_closing:
            return False

        queue_uid = uuid.UUID(str(queue_id))
        if queue_uid not in Config.QueueConfig:
            return False
        queue_config = Config.QueueConfig[queue_uid]
        if not queue_config.get("Info", if_key):
            return False

        script_path = str(queue_config.get("Info", path_key) or "").strip()
        if not script_path:
            return False

        if if_key == "IfScriptBeforeTask":
            if self._queue_before_script_ran:
                return False
            self._queue_before_script_ran = True
        elif if_key == "IfScriptAfterTask":
            if self._queue_after_script_ran:
                return False
            self._queue_after_script_ran = True

        await Publisher.send(
            id=self.task_info.task_id,
            type=protocol.TASK_NOTICE,
            data=WSTaskNoticeData(level="info", message=f"开始执行{label}"),
        )
        if self.stopped_manually or self.is_closing:
            return False
        script_task = asyncio.create_task(execute_script_task(Path(script_path), label))
        self._queue_script_task = script_task
        try:
            succeeded = await script_task
            await Publisher.send(
                id=self.task_info.task_id,
                type=protocol.TASK_NOTICE,
                data=WSTaskNoticeData(
                    level="info" if succeeded else "warning",
                    message=f"{label}执行{'成功' if succeeded else '失败'}",
                ),
            )
            return succeeded
        except asyncio.CancelledError:
            if self.stopped_manually and if_key == "IfScriptAfterTask":
                return False
            raise
        finally:
            if self._queue_script_task is script_task:
                self._queue_script_task = None

    def _is_script_scheduled_today(self, index: int) -> bool:
        if self.script_run_days is None or index >= len(self.script_run_days):
            return True
        return self.run_weekday in self.script_run_days[index]

    async def _run_script_list(self, start_index: int) -> None:
        idx = start_index
        has_started_any = False

        while 0 <= idx < len(self.task_info.script_list):
            # 队列中相邻两个子任务间隔检查是否有其他程序需要连接本地远程桌面，并在其停止使用时机接受回传
            if has_started_any or ChildSessionManager.has_external_lease_requests():
                await ChildSessionManager.wait_if_external_requested(
                    boundary_label=f"队列任务[{self.task_info.task_id}]子任务间隔"
                )

            self.task_info.current_index = idx
            script_item = self.task_info.script_list[idx]
            self.task_info.begin_script_run(script_item)
            current_script_uid = uuid.UUID(script_item.script_id)

            if current_script_uid not in Config.ScriptConfig:
                script_item.status = "异常"
                self._record_error(f"脚本 {current_script_uid} 已被删除")
                logger.info(f"跳过任务: {current_script_uid}, 该任务对应脚本已被删除")
                await Publisher.send(
                    id=self.task_info.task_id,
                    type=protocol.TASK_NOTICE,
                    data=WSTaskNoticeData(
                        level="error",
                        message=f"任务 {script_item.name} 对应脚本已被删除",
                    ),
                )
                idx += 1
                continue

            script_scope = self.task_info.script_user_scope(script_item.script_id)
            if script_scope is not None and not script_scope:
                script_item.status = "跳过"
                logger.info(f"跳过任务: {current_script_uid}, 本次未选择任何用户")
                await Publisher.send(
                    id=self.task_info.task_id,
                    type=protocol.TASK_NOTICE,
                    data=WSTaskNoticeData(
                        level="warning",
                        message=f"任务 {script_item.name} 本次未选择任何用户, 已跳过",
                    ),
                )
                idx += 1
                continue

            if not self._is_script_scheduled_today(idx):
                script_item.status = "跳过"
                logger.info(
                    f"跳过任务: {current_script_uid}, 队列项未安排在 {self.run_weekday} 运行"
                )
                idx += 1
                continue

            reservation_owner = self.task_info.task_id
            script_config = Config.ScriptConfig[current_script_uid]
            root_paths, emulator_key = _exclusive_resources(script_config)
            if not self.script_reservations.try_acquire(
                current_script_uid,
                reservation_owner,
                root_paths=root_paths,
                emulator_key=emulator_key,
            ):
                script_item.status = "跳过"
                logger.info(
                    f"跳过任务: {current_script_uid}, 该任务已被其他任务调度器锁定"
                )
                await Publisher.send(
                    id=self.task_info.task_id,
                    type=protocol.TASK_NOTICE,
                    data=WSTaskNoticeData(
                        level="warning",
                        message=f"任务 {script_item.name} 已被其他任务调度器锁定",
                    ),
                )
                idx += 1
                continue

            nav_offset: int | None = None
            has_started_any = True
            ChildSessionManager.enter_subtask()
            try:
                if script_config.is_locked:
                    script_item.status = "跳过"
                    logger.info(f"跳过任务: {current_script_uid}, 该任务配置已被锁定")
                    await Publisher.send(
                        id=self.task_info.task_id,
                        type=protocol.TASK_NOTICE,
                        data=WSTaskNoticeData(
                            level="warning",
                            message=f"任务 {script_item.name} 已被锁定",
                        ),
                    )
                    idx += 1
                    continue

                script_item.status = "运行"
                logger.info(f"任务开始: {current_script_uid}")

                task_item = self._build_task_item(
                    script_item,
                    script_config,
                    script_uid=current_script_uid,
                    reservation_owner=reservation_owner,
                    root_paths=root_paths,
                    emulator_key=emulator_key,
                )
                if task_item is None:
                    script_item.status = "异常"
                    self._record_error(
                        f"不支持的脚本类型: {type(script_config).__name__}"
                    )
                    logger.error(f"不支持的脚本类型: {type(script_config).__name__}")
                    await Publisher.send(
                        id=self.task_info.task_id,
                        type=protocol.TASK_NOTICE,
                        data=WSTaskNoticeData(level="error", message="脚本类型不支持"),
                    )
                    idx += 1
                    continue

                with self._observe_script_run(script_item, script_config):
                    child = self.spawn(task_item)
                    self._active_child_task = child
                    try:
                        await child
                    except asyncio.CancelledError:
                        if self._pending_nav_offset is not None and not self.is_closing:
                            nav_offset = self._pending_nav_offset
                            self._pending_nav_offset = None
                            current_task = asyncio.current_task()
                            if current_task is not None:
                                while current_task.cancelling():
                                    current_task.uncancel()
                            script_item.status = "跳过"
                            logger.info(
                                f"已响应全局热键切换任务 (offset={nav_offset:+d}): 中止当前脚本 {script_item.name}"
                            )
                        else:
                            raise
                    finally:
                        self._active_child_task = None
            finally:
                ChildSessionManager.exit_subtask()
                self.script_reservations.release(current_script_uid, reservation_owner)
                self.task_info.flush_replays(script_item)

            if nav_offset is not None:
                idx = max(0, idx + nav_offset)
            else:
                idx += 1

    async def final_task(self) -> None:
        self.task_info.flush_replays()

        if self._queue_run_started and self.task_info.queue_id is not None:
            await self._run_queue_extra_script(
                self.task_info.queue_id,
                "IfScriptAfterTask",
                "ScriptAfterTask",
                "队列运行后脚本",
            )

        logger.info(f"任务结束: {self.task_info.task_id}")

        if self.task_info.community_sign_notification is not None:
            self.task_info.community_sign_notification.finish()

        result_text = build_task_result_text(self.task_info.script_list)
        await Publisher.send(
            id=str(self.task_info.task_id),
            type=protocol.TASK_COMPLETED,
            data=WSTaskCompletedData(
                result=result_text,
                outcome=self._exit_result,
                error=self._exit_error,
                task_info=self.task_info.asdict,
            ),
        )
        if self._on_finished is not None:
            self._on_finished(
                TaskStatusOut(
                    taskId=str(self.task_info.task_id),
                    status=self._exit_result,
                    detail=result_text,
                    error=self._exit_error,
                    mode=self.task_info.mode,
                    isCycle=self.task_info.is_cycle,
                    queueId=self.task_info.queue_id,
                    scriptId=self.task_info.script_id,
                    userId=self.task_info.user_id,
                    finishedAt=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                )
            )

        if (
            not self.is_closing
            and not self.stopped_manually
            and not self.task_info.is_cycle
            and self.task_info.mode == "AutoProxy"
            and self.task_info.queue_id is not None
        ):
            if Config.power_sign == "NoAction":
                queue_uid = uuid.UUID(self.task_info.queue_id)
                if queue_uid not in Config.QueueConfig:
                    logger.info(f"队列 {queue_uid} 已删除，跳过完成后操作")
                    return
                queue_config = Config.QueueConfig[queue_uid]
                Config.power_sign = queue_config.get("Info", "AfterAccomplish")
                Config.power_delay = (
                    queue_config.get("Info", "AfterAccomplishDelay") * 60
                )
                await Publisher.send(
                    id=protocol.ID_MAIN,
                    type=protocol.POWER_SIGN_UPDATED,
                    data=WSPowerSignData(signal=Config.power_sign),
                )

    async def on_crash(self, e: Exception) -> None:
        current = self.task_info.current_index
        script = (
            self.task_info.script_list[current]
            if 0 <= current < len(self.task_info.script_list)
            else None
        )
        self.task_info._request_replay(
            script, reason=f"任务执行异常：{type(e).__name__}: {e}"
        )
        if self._exit_result == "success":
            self._exit_result = "error"
            self._exit_error = f"{type(e).__name__}: {e}"

        logger.exception(f"任务 {self.task_info.task_id} 出现异常: {e}")
        await Publisher.send(
            id=self.task_info.task_id,
            type=protocol.TASK_NOTICE,
            data=WSTaskNoticeData(
                level="error",
                message=f"任务出现异常: {type(e).__name__}: {str(e)}",
            ),
        )


class _TaskManager:
    """业务调度器"""

    def __init__(self):
        super().__init__()

        self.task_info: Dict[uuid.UUID, TaskInfo] = {}
        self.task_handler: Dict[uuid.UUID, Task] = {}
        self._recent_results: OrderedDict[str, tuple[float, TaskStatusOut]] = (
            OrderedDict()
        )
        self._script_reservations = _ScriptTaskReservations()
        self._cleanup_tasks: set[asyncio.Task[None]] = set()
        self._stop_all_lock = asyncio.Lock()
        self._stopping_all = False
        self._creating_tasks = 0
        self._creating_tasks_idle = asyncio.Event()
        self._creating_tasks_idle.set()
        self._startup_queue_started = False
        self._startup_queue_task: asyncio.Task | None = None
        self._last_standalone_script_idx: int = -1
        self._pending_timed_queue_runs: dict[uuid.UUID, int] = {}
        self._timed_queue_workers: dict[uuid.UUID, asyncio.Task[None]] = {}
        self._queue_finished_at: dict[uuid.UUID, float] = {}

    def is_queue_running(self, queue_id: str | uuid.UUID) -> bool:
        """包含正在停止和收尾的任务，避免上一轮释放资源前再次启动。"""
        return any(info.queue_id == str(queue_id) for info in self.task_info.values())

    def has_pending_timed_queue_run(self, queue_id: str | uuid.UUID) -> bool:
        return uuid.UUID(str(queue_id)) in self._timed_queue_workers

    def defer_timed_queue_run(self, queue_id: uuid.UUID, *, count: int = 1) -> None:
        """保留撞上当前轮的定时请求，整轮收尾后间隔 10 秒依次运行。"""
        if self._stopping_all or any(
            info.queue_id == str(queue_id)
            and getattr(self.task_handler.get(task_id), "is_closing", False)
            for task_id, info in self.task_info.items()
        ):
            return
        self._pending_timed_queue_runs[queue_id] = (
            self._pending_timed_queue_runs.get(queue_id, 0) + count
        )
        if queue_id not in self._timed_queue_workers:
            self._timed_queue_workers[queue_id] = asyncio.create_task(
                self._run_deferred_timed_queue(queue_id)
            )
        logger.info(
            f"队列 {queue_id} 定时已顺延，待运行 {self._pending_timed_queue_runs[queue_id]} 轮"
        )

    async def _run_deferred_timed_queue(self, queue_id: uuid.UUID) -> None:
        try:
            while self._pending_timed_queue_runs.get(queue_id, 0):
                while self.is_queue_running(queue_id):
                    await asyncio.sleep(0.2)
                if queue_id not in Config.QueueConfig:
                    return
                finished_at = self._queue_finished_at.get(queue_id, time.perf_counter())
                logger.info(f"队列 {queue_id} 将于收尾 10 秒后启动顺延定时")
                remaining = finished_at + 10 - time.perf_counter()
                while remaining > 0:
                    await asyncio.sleep(remaining)
                    remaining = finished_at + 10 - time.perf_counter()
                # 等待期间手动开了一轮时，等该轮完整结束后再重新计时。
                if self.is_queue_running(queue_id) or self._queue_finished_at.get(
                    queue_id, finished_at
                ) != finished_at:
                    continue
                if queue_id not in Config.QueueConfig:
                    return
                queue = Config.QueueConfig[queue_id]
                if queue.get("Info", "CycleEnabled") or not queue.get(
                    "Info", "TimeEnabled"
                ):
                    return
                try:
                    await self.add_task(
                        "AutoProxy",
                        str(queue_id),
                        new_task_info={
                            "queueId": str(queue_id),
                            "taskName": f"队列 - {queue.get('Info', 'Name')}",
                            "taskType": "顺延定时代理",
                        },
                        trigger_source="scheduled_task",
                    )
                except RuntimeError:
                    if self.is_queue_running(queue_id):
                        continue
                    raise
                self._pending_timed_queue_runs[queue_id] -= 1
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(f"队列 {queue_id} 顺延定时启动失败")
        finally:
            if self._timed_queue_workers.get(queue_id) is asyncio.current_task():
                self._timed_queue_workers.pop(queue_id, None)
                self._pending_timed_queue_runs.pop(queue_id, None)

    async def cancel_pending_timed_queue_runs(
        self, queue_id: str | uuid.UUID | None = None
    ) -> None:
        queue_ids = (
            list(self._timed_queue_workers)
            if queue_id is None
            else [uuid.UUID(str(queue_id))]
        )
        workers = []
        for uid in queue_ids:
            self._pending_timed_queue_runs.pop(uid, None)
            worker = self._timed_queue_workers.pop(uid, None)
            if worker is not None:
                worker.cancel()
                workers.append(worker)
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)

    @staticmethod
    def _queue_script_entries(
        queue_id: uuid.UUID,
    ) -> list[tuple[uuid.UUID, list[str]]]:
        return [
            (uuid.UUID(script_id), list(queue_item.get("Schedule", "Days")))
            for queue_item in Config.QueueConfig[queue_id].QueueItem.values()
            if (script_id := str(queue_item.get("Info", "ScriptId") or "").strip())
            and script_id != "-"
        ]

    @classmethod
    def _queue_script_ids(cls, queue_id: uuid.UUID) -> list[uuid.UUID]:
        return [script_id for script_id, _ in cls._queue_script_entries(queue_id)]

    @staticmethod
    def _script_identity(script_id: uuid.UUID) -> WSTaskScriptIdentityData:
        class_name = type(Config.ScriptConfig[script_id]).__name__
        return WSTaskScriptIdentityData(
            scriptId=str(script_id),
            scriptType=_SCRIPT_TYPE_BY_CLASS.get(class_name, class_name),
        )

    def _scheduled_script_identities(self) -> list[WSTaskScriptIdentityData]:
        identities: dict[uuid.UUID, WSTaskScriptIdentityData] = {}
        for queue_id, queue in Config.QueueConfig.items():
            if queue.get("Info", "CycleEnabled"):
                continue
            if not queue.get("Info", "TimeEnabled"):
                continue
            if not any(
                time_set.get("Info", "Enabled") and time_set.get("Info", "Days")
                for time_set in queue.TimeSet.values()
            ):
                continue

            for script_id in self._queue_script_ids(queue_id):
                if script_id not in Config.ScriptConfig:
                    continue
                identities.setdefault(script_id, self._script_identity(script_id))

        return list(identities.values())

    def _remember_result(self, status: TaskStatusOut) -> None:
        self._recent_results.pop(status.taskId, None)
        self._recent_results[status.taskId] = (time.monotonic(), status)
        while len(self._recent_results) > _RECENT_RESULTS_MAX:
            self._recent_results.popitem(last=False)

    def _prune_recent_results(self) -> None:
        deadline = time.monotonic() - _RECENT_RESULTS_TTL_SECONDS
        while self._recent_results:
            finished_at, _ = next(iter(self._recent_results.values()))
            if finished_at > deadline:
                break
            self._recent_results.popitem(last=False)

    def get_task_status(self, task_id: str) -> TaskStatusOut | None:
        try:
            task_uid = uuid.UUID(task_id)
        except ValueError:
            return None

        task_info = self.task_info.get(task_uid)
        if task_info is not None:
            handler = self.task_handler.get(task_uid)
            return TaskStatusOut(
                taskId=task_id,
                status="running",
                mode=task_info.mode,
                isCycle=task_info.is_cycle,
                queueId=task_info.queue_id,
                scriptId=task_info.script_id,
                userId=task_info.user_id,
                stopping=bool(handler and handler.is_closing),
            )

        self._prune_recent_results()
        remembered = self._recent_results.get(task_id)
        return remembered[1] if remembered is not None else None

    def get_runtime_snapshot(self) -> TaskRuntimeSnapshot:
        tasks: list[TaskRuntimeSnapshotItem] = []
        for task_uid, task_info in list(self.task_info.items()):
            handler = self.task_handler.get(task_uid)
            tasks.append(
                TaskRuntimeSnapshotItem(
                    taskId=str(task_uid),
                    mode=task_info.mode,
                    isCycle=task_info.is_cycle,
                    queueId=task_info.queue_id,
                    scriptId=task_info.script_id,
                    userId=task_info.user_id,
                    stopping=bool(handler and handler.is_closing),
                    scripts=handler.script_identities if handler else [],
                    task_info=task_info.asdict,
                    cycleNextList=[
                        WSTaskCyclePreviewData(**item)
                        for item in task_info.cycle_next_list
                    ],
                    log=task_info._last_pushed_log[-200_000:],
                    logSeq=task_info._log_seq,
                    logFirstLine=task_info._last_pushed_log_first_line
                    + task_info._last_pushed_log.count(
                        "\n", 0, max(0, len(task_info._last_pushed_log) - 200_000)
                    ),
                )
            )
        return TaskRuntimeSnapshot(
            tasks=tasks,
            scheduledScripts=self._scheduled_script_identities(),
        )

    def _schedule_clean_task(self, task_uid: uuid.UUID) -> None:
        clean_task = asyncio.create_task(self.clean_task(task_uid))
        self._cleanup_tasks.add(clean_task)

        def _on_done(done_task: asyncio.Task[None]) -> None:
            self._cleanup_tasks.discard(done_task)
            if done_task.cancelled():
                return
            exc = done_task.exception()
            if exc is not None:
                logger.error(f"任务收尾异常({task_uid}): {type(exc).__name__}: {exc}")

        clean_task.add_done_callback(_on_done)

    @staticmethod
    def _resolve_target_user(
        script_uid: uuid.UUID, user_id: str | None
    ) -> uuid.UUID | None:
        if user_id is None:
            return None

        script_config = Config.ScriptConfig[script_uid]
        script_name = script_config.get("Info", "Name")
        try:
            user_uid = uuid.UUID(user_id)
        except ValueError as e:
            raise ValueError(f"用户 {user_id} 不属于脚本 {script_name}") from e
        if user_uid not in script_config.UserData:
            raise ValueError(f"用户 {user_id} 不属于脚本 {script_name}")

        user_config = script_config.UserData[user_uid]
        if (
            not user_config.get("Info", "Status")
            or user_config.get("Info", "RemainedDay") == 0
        ):
            raise ValueError(
                f"用户 {user_config.get('Info', 'Name')} 未启用或代理天数已耗尽"
            )
        return user_uid

    def _resolve_target_users(
        self, script_uid: uuid.UUID, user_ids: list[str] | None
    ) -> frozenset[str] | None:
        if user_ids is None:
            return None
        if not user_ids:
            raise ValueError("至少选择一个用户")

        selected: set[str] = set()
        for user_id in user_ids:
            user_uid = self._resolve_target_user(script_uid, user_id)
            if user_uid is not None:
                selected.add(str(user_uid))

        return frozenset(selected)

    def _resolve_queue_user_scope(
        self, queue_id: uuid.UUID, queue_user_ids: dict[str, list[str]]
    ) -> dict[str, frozenset[str]]:
        queue_script_ids = {
            str(script_id) for script_id in self._queue_script_ids(queue_id)
        }
        scope: dict[str, frozenset[str]] = {}
        for script_id, user_ids in queue_user_ids.items():
            if script_id not in queue_script_ids:
                queue_name = Config.QueueConfig[queue_id].get("Info", "Name")
                raise ValueError(f"脚本 {script_id} 不属于队列 {queue_name}")
            if not user_ids:
                scope[script_id] = frozenset()
                continue
            scope[script_id] = (
                self._resolve_target_users(uuid.UUID(script_id), list(user_ids))
                or frozenset()
            )
        return scope

    async def add_task(
        self,
        mode: Literal["AutoProxy", "ScriptConfig", "Update", "CycleRun"],
        id: str,
        new_task_info: dict | None = None,
        resume_from_script_id: str | None = None,
        user_id: str | None = None,
        user_ids: list[str] | None = None,
        queue_user_ids: dict[str, list[str]] | None = None,
        trigger_source: TaskTriggerSource = "manual_task",
        view_only: bool = False,
        instance_idx: int | None = None,
    ) -> uuid.UUID:
        from app.core.desktop_runtime import ensure_execution_session

        await ensure_execution_session()
        uid = uuid.UUID(id)

        if self._stopping_all:
            raise RuntimeError("正在停止全部任务，暂不接受新任务")

        if uid in Config.QueueConfig and self.is_queue_running(uid):
            raise RuntimeError(
                f"队列 {Config.QueueConfig[uid].get('Info', 'Name')} 已在运行，请等待本轮结束"
            )

        if user_id is not None and user_ids is not None:
            raise ValueError("多选用户不能与单独运行用户同时使用")

        if (user_id is not None or user_ids is not None) and (
            mode != "AutoProxy" or uid not in Config.ScriptConfig
        ):
            raise ValueError("指定运行用户仅支持脚本的自动代理任务")

        if queue_user_ids is not None and (
            mode not in ("AutoProxy", "CycleRun") or uid not in Config.QueueConfig
        ):
            raise ValueError("按脚本指定运行用户仅支持队列任务")

        is_cycle = mode == "CycleRun"
        exec_mode: Literal["AutoProxy", "ScriptConfig", "Update"] = (
            "AutoProxy" if is_cycle else mode
        )

        if is_cycle:
            if uid not in Config.QueueConfig:
                raise ValueError(f"循环运行的任务 {uid} 必须是调度队列")
            if not Config.QueueConfig[uid].get("Info", "CycleEnabled"):
                raise ValueError(
                    f"队列 {Config.QueueConfig[uid].get('Info', 'Name')} 不是循环队列"
                )
            if uid in Config.running_cycle_queue_ids:
                raise RuntimeError(
                    f"循环队列 {Config.QueueConfig[uid].get('Info', 'Name')} 已在运行"
                )
            Config.running_cycle_queue_ids.add(uid)

        selected_user_ids: frozenset[str] | None = None
        selected_user_scope: dict[str, frozenset[str]] | None = None

        if mode in ("ScriptConfig", "Update"):
            if uid in Config.ScriptConfig:
                task_uid = uuid.uuid4()
                queue_id = None
                script_uid = uid
                user_uid = "Default"
            else:
                for script_id, script in Config.ScriptConfig.items():
                    if uid in script.UserData:
                        task_uid = uuid.uuid4()
                        queue_id = None
                        script_uid = script_id
                        user_uid = uid
                        break
                else:
                    raise ValueError(f"任务 {uid} 无法找到对应脚本配置")
        elif uid in Config.QueueConfig:
            task_uid = uuid.uuid4()
            queue_id = uid
            script_uid = None
            user_uid = None
        elif uid in Config.ScriptConfig:
            task_uid = uuid.uuid4()
            queue_id = None
            script_uid = uid
            user_uid = self._resolve_target_user(uid, user_id)
            selected_user_ids = self._resolve_target_users(uid, user_ids)
        else:
            raise ValueError(f"任务 {uid} 无法找到对应脚本配置")

        script_run_days: list[list[str]] | None = None
        if queue_id is not None:
            queue_entries = [
                entry
                for entry in self._queue_script_entries(queue_id)
                if entry[0] in Config.ScriptConfig
            ]
            target_script_ids = [script_id for script_id, _ in queue_entries]
            script_run_days = [days for _, days in queue_entries]
            if queue_user_ids is not None:
                selected_user_scope = self._resolve_queue_user_scope(
                    queue_id, queue_user_ids
                )
        elif script_uid is not None and script_uid in Config.ScriptConfig:
            target_script_ids = [script_uid]
        else:
            target_script_ids = []
        script_identities = [
            self._script_identity(script_id) for script_id in target_script_ids
        ]

        reservation_owner = str(task_uid)
        reservation_acquired = False
        if script_uid is not None:
            script_config = Config.ScriptConfig[script_uid]
            root_paths, emulator_key = _exclusive_resources(script_config)
            if script_config.is_locked or not self._script_reservations.try_acquire(
                script_uid,
                reservation_owner,
                root_paths=root_paths,
                emulator_key=emulator_key,
            ):
                raise RuntimeError(f"任务 {script_config.get('Info', 'Name')} 已在运行")
            reservation_acquired = True

        self._creating_tasks += 1
        self._creating_tasks_idle.clear()
        try:
            logger.info(
                f"创建任务: {task_uid}, 模式: {mode}, 触发来源: {trigger_source}"
            )
            self.task_info[task_uid] = TaskInfo(
                mode=exec_mode,
                task_id=str(task_uid),
                queue_id=str(queue_id) if queue_id else None,
                script_id=str(script_uid) if script_uid else None,
                user_id=str(user_uid) if user_uid else None,
                user_ids=selected_user_ids,
                user_ids_by_script=selected_user_scope,
                resume_from_script_id=resume_from_script_id,
                trigger_source=trigger_source,
                is_cycle=is_cycle,
                view_only=view_only and exec_mode == "ScriptConfig",
                instance_idx=instance_idx if exec_mode == "ScriptConfig" else None,
            )
            self.task_handler[task_uid] = Task(
                self.task_info[task_uid],
                script_identities,
                self._script_reservations,
                script_run_days=script_run_days,
                on_finished=self._remember_result,
            )
            await Publisher.send(
                id=protocol.ID_TASK_MANAGER,
                type=protocol.TASK_CREATED,
                data=WSTaskCreatedData(
                    taskId=str(task_uid),
                    mode=mode,
                    scripts=script_identities,
                    queueId=str(queue_id) if queue_id else None,
                    taskName=new_task_info.get("taskName") if new_task_info else None,
                    taskType=new_task_info.get("taskType") if new_task_info else None,
                ),
            )
            self.task_handler[task_uid].execute()
            self._schedule_clean_task(task_uid)
        except BaseException:
            if reservation_acquired and script_uid is not None:
                self._script_reservations.release(script_uid, reservation_owner)
            if is_cycle:
                Config.running_cycle_queue_ids.discard(uid)
            self.task_handler.pop(task_uid, None)
            self.task_info.pop(task_uid, None)
            raise
        finally:
            self._creating_tasks -= 1
            if self._creating_tasks == 0:
                self._creating_tasks_idle.set()

        return task_uid

    async def clean_task(self, task_uid: uuid.UUID) -> None:
        task_info = self.task_info[task_uid]
        try:
            await self.task_handler[task_uid].accomplish.wait()
        finally:
            if task_info.script_id is not None:
                self._script_reservations.release(
                    uuid.UUID(task_info.script_id), task_info.task_id
                )

        power_enabled = bool(task_info.mode != "ScriptConfig")
        self.task_info.pop(task_uid, None)
        self.task_handler.pop(task_uid, None)
        if task_info.queue_id is not None:
            self._queue_finished_at[uuid.UUID(task_info.queue_id)] = time.perf_counter()

        if (
            power_enabled
            and not self._stopping_all
            and not self._timed_queue_workers
            and len(self.task_handler) == 0
            and Config.power_sign != "NoAction"
        ):
            logger.info(f"所有任务已结束，准备执行电源操作: {Config.power_sign}")
            from app.core.timer import MainTimer

            await System.start_power_task(before_power=MainTimer.drain_community_tasks)

    async def stop_task(self, task_id: str) -> None:
        logger.info(f"中止任务: {task_id}")

        if task_id == "ALL":
            async with self._stop_all_lock:
                self._stopping_all = True
                Config.power_sign = "NoAction"
                Config.power_delay = 0
                try:
                    # 先取消当前任务并发出受管进程强制清理，再等待其他调度收尾。
                    for task_item in list(self.task_handler.values()):
                        if not task_item.is_closing and task_item.cancel():
                            task_item.is_closing = True
                    await self.cancel_pending_timed_queue_runs()
                    if System.power_task is not None and not System.power_task.done():
                        await System.cancel_power_task()

                    await self._creating_tasks_idle.wait()

                    task_item_list = list(self.task_handler.values())
                    if task_item_list:
                        logger.info("等待全部任务中的子任务结束...")
                    for task_item in task_item_list:
                        if not task_item.is_closing:
                            task_item.cancel()
                            task_item.is_closing = True
                    await asyncio.gather(
                        *(task_item.accomplish.wait() for task_item in task_item_list)
                    )
                    for task_item in task_item_list:
                        logger.info(f"子任务已结束: {task_item.task_info.task_id}")
                    cleanup_tasks = [
                        cleanup for cleanup in self._cleanup_tasks if not cleanup.done()
                    ]
                    if cleanup_tasks:
                        await asyncio.gather(*cleanup_tasks)
                finally:
                    Config.power_sign = "NoAction"
                    Config.power_delay = 0
                    self._stopping_all = False
            await Publisher.send(
                id=protocol.ID_MAIN,
                type=protocol.POWER_SIGN_UPDATED,
                data=WSPowerSignData(signal=Config.power_sign),
            )
        else:
            uid = uuid.UUID(task_id)
            if uid not in self.task_handler:
                logger.info(f"任务 {task_id} 已结束，无需中止")
                return
            if self.task_handler[uid].is_closing:
                raise RuntimeError("任务已在中止中")
            handler = self.task_handler[uid]
            handler.cancel()
            handler.is_closing = True
            queue_id = self.task_info[uid].queue_id
            if queue_id is not None:
                await self.cancel_pending_timed_queue_runs(queue_id)
            logger.info(f"等待任务 {task_id} 结束...")
            await handler.accomplish.wait()
            logger.info(f"任务 {task_id} 已结束")

    # ==================== 全局热键与快捷任务控制 ====================

    async def toggle_start_stop(self) -> dict[str, Any]:
        """控制程序启停：若有任务正在运行则停止全部任务；若无任务则启动首个可用队列或脚本。"""
        if self.task_handler or self._timed_queue_workers:
            await self.stop_task("ALL")
            return {"action": "stopped", "message": "已停止全部正在运行的任务"}

        return await self.start_default_task()

    async def start_default_task(self) -> dict[str, Any]:
        """启动默认队列（优先首个配置了脚本的队列，否则启动首个脚本）。"""
        for q_uid, queue in Config.QueueConfig.items():
            if self._queue_script_ids(q_uid):
                is_cycle = bool(queue.get("Info", "CycleEnabled"))
                mode: Literal["CycleRun", "AutoProxy"] = "CycleRun" if is_cycle else "AutoProxy"
                task_uid = await self.add_task(mode, str(q_uid), trigger_source="manual_task")
                return {
                    "action": "started",
                    "targetType": "queue",
                    "targetId": str(q_uid),
                    "taskId": str(task_uid),
                }

        script_uids = list(Config.ScriptConfig.keys())
        if script_uids:
            self._last_standalone_script_idx = 0
            s_uid = script_uids[0]
            task_uid = await self.add_task("AutoProxy", str(s_uid), trigger_source="manual_task")
            return {
                "action": "started",
                "targetType": "script",
                "targetId": str(s_uid),
                "taskId": str(task_uid),
            }

        return {"action": "none", "message": "当前没有可启动的队列或脚本配置"}

    async def navigate_task(self, direction: Literal[-1, 1]) -> dict[str, Any]:
        """切换到上一个任务（direction=-1）或下一个任务（direction=+1）。

        - 若当前存在运行中的队列任务，向该任务发送跳转偏移，立即中止当前子任务并切到目标子任务；
        - 若当前运行的是独立单脚本（或处于空闲态），则按 `Config.ScriptConfig` 顺序停止当前脚本并启动上/下一个脚本。
        """
        for task_uid, handler in list(self.task_handler.items()):
            if handler.is_closing:
                continue
            if len(handler.task_info.script_list) > 1 or handler.task_info.queue_id is not None:
                if handler.request_navigate(direction):
                    return {
                        "action": "navigated_in_queue",
                        "direction": direction,
                        "taskId": str(task_uid),
                    }

        script_uids = list(Config.ScriptConfig.keys())
        if not script_uids:
            return {"action": "none", "message": "当前没有已配置的脚本"}

        # 若当前正在跑单个脚本，先记住它的位置并停止它
        for task_uid, info in list(self.task_info.items()):
            if info.script_id:
                with suppress(ValueError):
                    cur_uid = uuid.UUID(info.script_id)
                    if cur_uid in script_uids:
                        self._last_standalone_script_idx = script_uids.index(cur_uid)
        if self.task_handler:
            await self.stop_task("ALL")

        if self._last_standalone_script_idx < 0:
            next_idx = 0 if direction > 0 else len(script_uids) - 1
        else:
            next_idx = (self._last_standalone_script_idx + direction) % len(script_uids)

        self._last_standalone_script_idx = next_idx
        target_uid = script_uids[next_idx]
        new_task_uid = await self.add_task("AutoProxy", str(target_uid), trigger_source="manual_task")
        return {
            "action": "started_script",
            "direction": direction,
            "scriptId": str(target_uid),
            "taskId": str(new_task_uid),
        }

    async def start_startup_queue(self):
        """开始运行启动时运行的调度队列"""

        while (running_task := self._startup_queue_task) is not None:
            logger.info("启动时任务正在等待运行，等待其结束后再判断")
            await asyncio.wait({running_task})

        if self._startup_queue_started:
            logger.info("启动时任务已触发，跳过重复运行")
            return

        self._startup_queue_task = asyncio.current_task()

        try:
            await asyncio.sleep(10)

            if not MainConnection.is_connected:
                logger.info("主 WebSocket 已断开，启动时任务等待下次连接后运行")
                return

            curday = datetime.now().strftime("%Y-%m-%d")

            self._startup_queue_started = True
            logger.info("开始运行启动时任务")
            for uid, queue in Config.QueueConfig.items():
                is_cycle = bool(queue.get("Info", "CycleEnabled"))
                start_mode = "CycleRun" if is_cycle else "AutoProxy"
                task_type = "启动时循环" if is_cycle else "启动时代理"

                StartUpMode = queue.get("Info", "StartUpMode")
                if StartUpMode == "Always":
                    logger.info(f"启动时需要运行的队列：{uid}")
                    try:
                        await TaskManager.add_task(
                            start_mode,
                            str(uid),
                            new_task_info={
                                "queueId": str(uid),
                                "taskName": f"队列 - {queue.get('Info', 'Name')}",
                                "taskType": task_type,
                            },
                            trigger_source="startup_task",
                        )
                    except (RuntimeError, ValueError) as error:
                        logger.error(f"启动时队列 {uid} 无法创建任务：{error}")
                        continue
                    await queue.set("Data", "LastStartupTime", curday)

                elif StartUpMode == "DailyFirst":
                    if queue.get("Data", "LastStartupTime") == curday:
                        logger.info(f"队列 {uid} 已在今日运行过，跳过该次运行")
                        continue

                    logger.info(f"启动时需要运行的队列：{uid}")
                    try:
                        await TaskManager.add_task(
                            start_mode,
                            str(uid),
                            new_task_info={
                                "queueId": str(uid),
                                "taskName": f"队列 - {queue.get('Info', 'Name')}",
                                "taskType": task_type,
                            },
                            trigger_source="startup_task",
                        )
                    except (RuntimeError, ValueError) as error:
                        logger.error(f"启动时队列 {uid} 无法创建任务：{error}")
                        continue
                    await queue.set("Data", "LastStartupTime", curday)

        finally:
            self._startup_queue_task = None

        logger.success("启动时任务开始运行")


TaskManager = _TaskManager()
