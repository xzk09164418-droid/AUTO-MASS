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
import re
import shlex
import time
import uuid
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core import Config
from app.core.general_ownership import general_ownership
from app.core.notify import should_send_result
from app.core.ws import Publisher, protocol
from app.log_box.hooks import make_line_hook
from app.log_box.markers import parse_marker
from app.models.config import GeneralConfig, GeneralUserConfig
from app.models.ConfigBase import MultipleConfig
from app.models.emulator import DeviceBase
from app.models.schema import GeneralConfig_Script, WSTaskNoticeData
from app.models.task import LogRecord, ScriptItem
from app.services import Notify, System
from app.task.base import ScriptAutoProxyBase
from app.utils import (
    LogMonitor,
    ProcessInfo,
    ProcessManager,
    apply_patterns,
    compile_log_signs,
    flush_patterns,
    get_logger,
    is_process_running,
    load_patterns,
    strptime,
)
from app.utils.constants import UTC4
from app.utils.LogPatternExtractor import LOG_TYPE_NORMAL

from .recovery import (
    EXIT_STABLE_SECONDS,
    RECOVERY_SECONDS,
    CleanupFailed,
    GeneralProcessManager,
    ProcessTracker,
    split_restart_arguments,
)
from .tools import push_notification
from .tools.launch import launch_commands

logger = get_logger("通用脚本自动代理")

_PREFIX_SENTINEL = "******"

# 进程启动宽限期（秒）
_PROCESS_START_GRACE_SECONDS = 90

_STRPTIME_DIRECTIVES: dict[str, str] = {
    "%Y": r"\d{4}",
    "%y": r"\d{2}",
    "%m": r"\d{1,2}",
    "%d": r"\d{1,2}",
    "%H": r"\d{1,2}",
    "%I": r"\d{1,2}",
    "%M": r"\d{1,2}",
    "%S": r"\d{1,2}",
    "%f": r"\d+",
    "%j": r"\d{1,3}",
    "%U": r"\d{1,2}",
    "%W": r"\d{1,2}",
    "%w": r"\d",
    "%A": r"\w+",
    "%a": r"\w+",
    "%B": r"\w+",
    "%b": r"\w+",
    "%p": r"[APap][Mm]",
    "%%": r"%",
}


def _format_to_prefix_regex(fmt: str) -> re.Pattern[str]:
    """strptime format（不含 ****** 哨兵）→ 前缀匹配正则。"""
    parts: list[str] = []
    i = 0
    while i < len(fmt):
        if fmt[i] == "%" and i + 1 < len(fmt):
            d = fmt[i : i + 2]
            if d in _STRPTIME_DIRECTIVES:
                parts.append(_STRPTIME_DIRECTIVES[d])
                i += 2
                continue
        parts.append(re.escape(fmt[i]))
        i += 1
    return re.compile("^" + "".join(parts))


class AutoProxyTask(ScriptAutoProxyBase):
    """通用脚本自动代理，支持自定义清理、有序恢复和一次限时补跑。"""

    def __init__(
        self,
        script_info: ScriptItem,
        script_config: GeneralConfig,
        user_config: MultipleConfig[GeneralUserConfig],
        game_manager: ProcessManager | DeviceBase | None,
    ):
        super().__init__()

        if script_info.task_info is None:
            raise RuntimeError("ScriptItem 未绑定到 TaskItem")

        self.task_info = script_info.task_info
        self.script_info = script_info
        self.script_config = script_config
        self.user_config = user_config
        self.game_manager = game_manager
        self.cur_user_item = self.script_info.user_list[self.script_info.current_index]
        self.cur_user_uid = uuid.UUID(self.cur_user_item.user_id)
        self.cur_user_config = self.user_config[self.cur_user_uid]
        self.check_result = "-"
        self.has_log_path = False
        self.general_log_monitor: LogMonitor | None = None
        self._cleanup_task: asyncio.Task | None = None
        self._cleanup_error = ""
        self._prepared = False
        self._recovery_used = False
        self._first_failure = ""
        self._recovery_result = ""
        self._finished = False
        self._ownership_warning = ""

    async def check(self) -> str:
        # 单独运行脚本是用户主动指定的一次性运行，不受单日代理次数上限约束
        if (
            self.task_info.is_queue_task
            and self.script_info.script_id
            not in self.task_info.external_restart_script_ids
            and self.script_config.get("Run", "ProxyTimesLimit") != 0
            and self.cur_user_config.get("Data", "ProxyTimes")
            >= self.script_config.get("Run", "ProxyTimesLimit")
        ):
            self.cur_user_item.status = "跳过"
            return "今日代理次数已达上限, 跳过该用户"

        return "Pass"

    async def prepare(self):
        recovery_config = GeneralConfig_Script.model_validate(
            {
                "TaskKill": self.script_config.get("Script", "TaskKill"),
                "TaskKillMode": self.script_config.get("Script", "TaskKillMode"),
                "Restart": self.script_config.get("Script", "Restart"),
            }
        )
        self.cleanup_targets = recovery_config.TaskKill or []
        self.cleanup_mode = recovery_config.TaskKillMode or "Force"
        self.restart_entries = recovery_config.Restart or []
        self.process_tracker = ProcessTracker()
        self.general_process_manager = self._new_process_manager()
        self._launch_managers: list[ProcessManager] = []
        self.wait_event = asyncio.Event()
        self.user_start_time = datetime.now()
        self.log_start_time = datetime.now()
        self.log_start_at = time.monotonic()

        self.script_path = Path(self.script_config.get("Script", "ScriptPath"))

        commands = launch_commands(
            self.script_path, str(self.script_config.get("Script", "Arguments"))
        )
        path_list = [path for path, _ in commands]
        arguments_list = [arguments for _, arguments in commands]

        self.script_exe_path = path_list[0] if len(path_list) > 0 else self.script_path
        self.script_arguments = arguments_list[0] if len(arguments_list) > 0 else []

        self.script_target_process_info = (
            ProcessInfo(
                name=self.script_config.get("Script", "TrackProcessName") or None,
                exe=self.script_config.get("Script", "TrackProcessExe") or None,
                cmdline=shlex.split(
                    self.script_config.get("Script", "TrackProcessCmdline"), posix=False
                )
                or None,
            )
            if self.script_config.get("Script", "IfTrackProcess")
            else None
        )

        raw_log_path = str(self.script_config.get("Script", "LogPath") or "").strip()
        self.has_log_path = bool(raw_log_path)

        if self.has_log_path:
            self.script_log_path = Path(raw_log_path)
            self.log_format = self.script_config.get("Script", "LogPathFormat")
            self.log_use_prefix = bool(self.log_format) and self.log_format.endswith(
                _PREFIX_SENTINEL
            )
            if self.log_use_prefix:
                prefix_re = _format_to_prefix_regex(
                    self.log_format[: -len(_PREFIX_SENTINEL)]
                )
                if not prefix_re.match(self.script_log_path.stem):
                    logger.warning(
                        f"LogPathFormat 与 LogPath 不匹配: {self.log_format} vs {self.script_log_path}"
                    )
            elif self.log_format:
                with suppress(ValueError):
                    datetime.strptime(self.script_log_path.stem, self.log_format)
                    self.log_format = f"{self.log_format}{self.script_log_path.suffix}"
            else:
                self.log_format = self.script_log_path.name
        else:
            self.script_log_path = Path()
            self.log_format = ""
            self.log_use_prefix = False

        self.game_path = Path(self.script_config.get("Game", "Path"))
        self.game_url = self.script_config.get("Game", "URL")
        self.game_process_name = self.script_config.get("Game", "ProcessName")
        self.log_time_range = (
            self.script_config.get("Script", "LogTimeStart") - 1,
            self.script_config.get("Script", "LogTimeEnd"),
        )
        self.success_log = compile_log_signs(
            self.script_config.get("Script", "SuccessLog"),
            self.script_config.get("Script", "SuccessLogMode"),
        )
        self.error_log = compile_log_signs(
            self.script_config.get("Script", "ErrorLog"),
            self.script_config.get("Script", "ErrorLogMode"),
        )
        for name, matcher in (("成功", self.success_log), ("失败", self.error_log)):
            if matcher.invalid:
                logger.warning(f"通用脚本{name}日志正则语法错误，该标志将不会命中")

        self.log_line_hook = (
            make_line_hook(self.script_config.get("Script", "LogHookRules"))
            if self.script_config.get("Script", "LogHookEnabled")
            else None
        )
        self.push_log_enabled = bool(self.script_config.get("Script", "PushLogEnabled"))
        self.push_log_patterns_compiled = (
            load_patterns(self.script_config.get("Script", "PushLogPatterns"))
            if self.push_log_enabled
            else []
        )
        self.push_log_buffer: list[tuple[str, str]] = []
        self._push_log_processed = 0
        self._process_seen = False

        if self.has_log_path:
            self.general_log_monitor = LogMonitor(
                self.log_time_range,
                self.script_config.get("Script", "LogTimeFormat"),
                self.check_log,
                line_hook=self.log_line_hook,
            )
        else:
            self.general_log_monitor = None

        self.run_book = False
        if self.cleanup_targets and isinstance(self.game_manager, ProcessManager):
            self.game_manager = self._new_process_manager()
        self._prepared = True
        self._failure_kind = "error"
        self.cur_user_item.log_record[self.log_start_time] = self.cur_user_log = (
            LogRecord()
        )

    def _resolve_log_file_path(self) -> Path:
        return self.script_log_path

    def _note_launch_arguments_skipped(self) -> None:
        arguments = str(self.script_config.get("Game", "Arguments") or "").strip()
        if arguments:
            logger.info(f"检测到游戏已在运行，本轮不会应用启动参数（{arguments}）")

    async def _run_main_task(self) -> None:
        # General 自己管理首轮与补跑预算，其他专项仍使用基类总时限。
        self._task_started_monotonic = time.monotonic()
        await self.main_task()

    def _new_process_manager(self) -> ProcessManager:
        return GeneralProcessManager(
            self.kill_managed_process if self.cleanup_targets else None
        )

    async def main_task(self):
        self.curdate = datetime.now(tz=UTC4).strftime("%Y-%m-%d")
        if self.cur_user_config.get("Data", "LastProxyDate") != self.curdate:
            await self.cur_user_config.set("Data", "LastProxyDate", self.curdate)
            await self.cur_user_config.set("Data", "ProxyTimes", 0)
        self.check_result = await self.check()
        if self.check_result != "Pass":
            return
        await self.prepare()
        self.cur_user_item.status = "运行"
        self._phase_deadline = time.monotonic() + self.run_timeout_seconds
        try:
            async with asyncio.timeout_at(self._phase_deadline):
                await self.run_user_scripts_before()
            for attempt in range(self.script_config.get("Run", "RunTimesLimit")):
                if time.monotonic() >= self._phase_deadline:
                    self._set_result("任务总时限已耗尽", kind="timeout")
                    break
                try:
                    async with asyncio.timeout_at(self._phase_deadline):
                        await self._run_attempt(
                            use_restart=attempt > 0
                            or self.script_info.script_id
                            in self.task_info.desktop_restart_script_ids
                        )
                except TimeoutError:
                    self._set_result("任务总时限已耗尽", kind="timeout")
                finally:
                    await self._cleanup_before_recovery()
                if (
                    self.run_book
                    or self._cleanup_error
                    or self._failure_kind in {"configuration", "timeout"}
                ):
                    break
        except TimeoutError:
            self._set_result("任务总时限已耗尽", kind="timeout")
        finally:
            await self._cleanup_before_recovery()

        if (
            not self.run_book
            and not self._cleanup_error
            and self._failure_kind in {"stalled", "timeout"}
        ):
            self._recovery_used = True
            self._first_failure = self.cur_user_log.status
            logger.warning(
                f"首轮失败（{self._first_failure}），清理完成，开始唯一一次 30 分钟补跑"
            )
            self._phase_deadline = time.monotonic() + RECOVERY_SECONDS
            try:
                async with asyncio.timeout_at(self._phase_deadline):
                    await self._run_attempt(use_restart=True)
            except TimeoutError:
                self._set_result("补跑超过 30 分钟", kind="timeout")
            finally:
                await self._cleanup_before_recovery()
            self._recovery_result = "补跑成功" if self.run_book else "补跑失败"
        self._finished = True

    async def _cleanup_before_recovery(self) -> None:
        try:
            await self.kill_managed_process()
        except CleanupFailed as e:
            self._cleanup_error = str(e)
            logger.error(self._cleanup_error)

    def _set_result(self, message: str, *, kind: str = "error") -> None:
        self._failure_kind = kind
        self.cur_user_log.status = message
        self.script_info.log = message
        self.wait_event.set()
        self.run_book = message == "Success!"

    async def _run_attempt(self, *, use_restart: bool) -> None:
        self._cleanup_task = None
        self._cleanup_error = ""
        self.process_tracker = ProcessTracker()
        self._launch_managers = []
        self.general_process_manager = self._new_process_manager()
        self.log_start_time = datetime.now()
        self.log_start_at = time.monotonic()
        self._attempt_wall_time = time.time()
        self._failure_kind = "error"
        self._process_seen = False
        self._exit_since = None
        self._startup_deadline = None
        self._main_launched = False
        self._ownership_warning = ""
        self.wait_event.clear()
        self.cur_user_item.log_record[self.log_start_time] = self.cur_user_log = (
            LogRecord()
        )
        self.cur_user_log.status = "通用脚本正常运行中"
        self.push_log_buffer.clear()
        self._push_log_processed = 0
        for matcher in self.push_log_patterns_compiled:
            reset = getattr(matcher, "reset", None)
            if reset is not None:
                reset()
        self._body_path = (
            next(
                (Path(item.Path) for item in self.restart_entries if item.IsMain),
                self.script_exe_path,
            )
            if use_restart
            else self.script_exe_path
        )
        self._log_baseline = self._snapshot_log_files()
        self._latest_log_time = None
        self._latest_log_count = 0
        self._log_observed = False
        self._last_log_progress = time.monotonic()
        watcher = asyncio.create_task(self._monitor_run())
        log_watcher = (
            asyncio.create_task(self._watch_log_files()) if self.has_log_path else None
        )
        try:
            if use_restart and self.restart_entries:
                await self._launch_restart()
            else:
                await self._launch_original()
            await self.wait_event.wait()
            self.run_book = self.cur_user_log.status == "Success!"
        except (OSError, ValueError) as e:
            self._set_result(f"启动配置错误: {e}", kind="configuration")
        except Exception as e:
            self._set_result(f"启动失败: {e}")
        finally:
            watcher.cancel()
            if log_watcher is not None:
                log_watcher.cancel()
            await asyncio.gather(
                watcher, *([log_watcher] if log_watcher else []), return_exceptions=True
            )
            if self.general_log_monitor is not None:
                await self.general_log_monitor.stop()
            if self._main_launched or self._startup_deadline is not None:
                try:
                    await general_ownership.record(
                        self.script_info.script_id,
                        self.script_config,
                        confirmed=self._process_seen,
                    )
                    if not self._process_seen:
                        self._ownership_warning = (
                            "无法确认脚本主体归属，下次运行将提示检查设置"
                        )
                        self.cur_user_log.content.append(self._ownership_warning)
                        logger.warning(self._ownership_warning)
                except Exception as e:
                    logger.warning(f"保存主体归属提示失败: {e}")

    async def _launch_original(self) -> None:
        await self._launch_game()
        if isinstance(self.game_manager, ProcessManager) and self.game_manager.main_pid:
            self.process_tracker.remember(self.game_manager.main_pid)
        if self.wait_event.is_set():
            return
        await self.set_general()
        self._startup_deadline = time.monotonic() + _PROCESS_START_GRACE_SECONDS
        await self._launch_program(
            self.script_exe_path, self.script_arguments, main=True
        )

    async def _launch_program(
        self, path: Path, arguments: list[str], *, main: bool, cwd: Path | None = None
    ) -> None:
        manager = self.general_process_manager if main else self._new_process_manager()
        self._launch_managers.append(manager)
        # 主体追踪由并行观察负责，避免启动器阻塞 60 秒导致错过日志或短命进程。
        await manager.open_process(path, *arguments, cwd=cwd)
        if manager.process is not None:
            self.process_tracker.remember(manager.process.pid)
        if main:
            self._main_launched = True
            if self.script_target_process_info is None:
                self._process_seen = True

    async def _launch_restart(self) -> None:
        for entry in self.restart_entries:
            if self.wait_event.is_set():
                return
            if entry.IsMain:
                self._startup_deadline = time.monotonic() + entry.WaitSeconds - 5
            try:
                args = split_restart_arguments(entry.Arguments)
                await self._launch_program(
                    Path(entry.Path),
                    args,
                    main=entry.IsMain,
                    cwd=Path(entry.WorkingDirectory)
                    if entry.WorkingDirectory
                    else None,
                )
            except Exception as e:
                logger.warning(f"恢复启动失败，继续后续项目: {entry.Path}: {e}")
                self.cur_user_log.content.append(f"启动失败: {entry.Path}: {e}")
            try:
                await asyncio.wait_for(
                    self.wait_event.wait(), timeout=entry.WaitSeconds
                )
                return
            except TimeoutError:
                pass
        if (
            not self._main_launched
            and not self._process_seen
            and not self.wait_event.is_set()
        ):
            self._set_result("脚本主体未启动")

    def _find_body(self) -> bool:
        target = self.script_target_process_info or ProcessInfo(
            name=self._body_path.name, exe=str(self._body_path)
        )
        matched = self.process_tracker.find_owned(target)
        if matched:
            self.general_process_manager.target_process = matched[0]
        return bool(matched)

    async def _monitor_run(self) -> None:
        try:
            while not self.wait_event.is_set():
                await asyncio.to_thread(self.process_tracker.collect_children)
                running = await asyncio.to_thread(self._find_body)
                if self.script_target_process_info is None and self._main_launched:
                    running = running or await self.general_process_manager.is_running()
                if self.wait_event.is_set():
                    return
                now = time.monotonic()
                if running:
                    self._process_seen = True
                    self._exit_since = None
                elif self._process_seen:
                    if self._exit_since is None:
                        self._exit_since = now
                    elif now - self._exit_since >= EXIT_STABLE_SECONDS:
                        self._set_result("Success!", kind="success")
                elif (
                    self._startup_deadline is not None and now >= self._startup_deadline
                ):
                    self._set_result("未观测到脚本主体启动")
                if (
                    not self.wait_event.is_set()
                    and self.has_log_path
                    and now - self._last_log_progress
                    >= self.script_config.get("Run", "RunTimeLimit") * 60
                ):
                    self._set_result("脚本日志停滞超时", kind="stalled")
                await asyncio.sleep(0.2)
        except Exception as e:
            self._set_result(f"运行监控失败: {e}")

    def _snapshot_log_files(self) -> dict[Path, tuple[int, int]]:
        if not self.has_log_path:
            return {}
        return {
            p: (p.stat().st_size, p.stat().st_mtime_ns) for p in self._log_candidates()
        }

    def _log_candidates(self) -> list[Path]:
        if not self.script_log_path.parent.is_dir():
            return []
        if self.log_use_prefix:
            pattern = _format_to_prefix_regex(self.log_format[: -len(_PREFIX_SENTINEL)])
            return [
                p
                for p in self.script_log_path.parent.iterdir()
                if p.is_file() and pattern.match(p.name)
            ]
        if "%" not in self.log_format:
            return [self.script_log_path] if self.script_log_path.is_file() else []
        paths = []
        for path in self.script_log_path.parent.iterdir():
            if path.is_file():
                with suppress(ValueError):
                    strptime(path.name, self.log_format, self.log_start_time)
                    paths.append(path)
        return paths

    def _resolve_current_log(self) -> Path:
        changed = []
        for path in self._log_candidates():
            try:
                stat = path.stat()
                if (stat.st_size, stat.st_mtime_ns) != self._log_baseline.get(path):
                    changed.append((stat.st_mtime_ns, path))
            except FileNotFoundError:
                continue
        if changed:
            self._active_log_path = max(changed, key=lambda entry: entry[0])[1]
        return self._active_log_path

    async def _watch_log_files(self) -> None:
        self._active_log_path = self.script_log_path
        try:
            self.general_log_monitor = LogMonitor(
                self.log_time_range,
                self.script_config.get("Script", "LogTimeFormat"),
                self.check_log,
                line_hook=self.log_line_hook,
            )
            await self.general_log_monitor.start_monitor_file(
                self._resolve_current_log,
                self.log_start_time,
                initial_offsets={
                    path: stat[0] for path, stat in self._log_baseline.items()
                },
            )
            while not self.wait_event.is_set():
                monitor_task = self.general_log_monitor.task
                if monitor_task is not None and monitor_task.done():
                    monitor_task.result()
                    raise RuntimeError("日志监控意外结束")
                await asyncio.sleep(0.2)
        except Exception as e:
            self._set_result(f"日志监控失败: {e}")

    async def _launch_game(self) -> None:
        self.script_info.log = "正在启动游戏 / 模拟器"
        if self.game_manager is not None:
            try:
                if isinstance(self.game_manager, ProcessManager):
                    if self.script_config.get("Game", "Type") == "URL":
                        if self.game_process_name and is_process_running(
                            self.game_process_name
                        ):
                            logger.info(
                                f"检测到游戏进程已在运行，跳过由 MAS 重复启动游戏: {self.game_process_name}"
                            )
                            self._note_launch_arguments_skipped()
                            await asyncio.sleep(2)
                        else:
                            logger.info(
                                f"启动游戏: {self.game_process_name}, 参数{self.game_url}"
                            )
                            await self.game_manager.open_protocol(
                                self.game_url,
                                ProcessInfo(name=self.game_process_name),
                            )
                            await asyncio.sleep(2)
                    else:
                        game_process_name = self.game_path.name
                        if game_process_name and is_process_running(game_process_name):
                            logger.info(
                                f"检测到游戏进程已在运行，跳过由 MAS 重复启动游戏: {game_process_name}"
                            )
                            self._note_launch_arguments_skipped()
                            await asyncio.sleep(
                                self.script_config.get("Game", "WaitTime")
                            )
                        else:
                            logger.info(
                                f"启动游戏: {self.game_path}, 参数: {self.script_config.get('Game', 'Arguments')}"
                            )
                            await self.game_manager.open_process(
                                self.game_path,
                                *str(self.script_config.get("Game", "Arguments")).split(
                                    " "
                                ),
                                breakaway=True,
                            )
                            self.script_info.log = f"正在等待游戏完成启动\n请等待{self.script_config.get('Game', 'WaitTime')}s"
                            await asyncio.sleep(
                                self.script_config.get("Game", "WaitTime")
                            )
                elif isinstance(self.game_manager, DeviceBase):
                    logger.info(
                        f"启动模拟器: {self.script_config.get('Game', 'EmulatorIndex')}"
                    )
                    await self.game_manager.open(
                        self.script_config.get("Game", "EmulatorIndex")
                    )
            except Exception as e:
                raise RuntimeError(f"游戏/模拟器启动失败: {e}") from e

    async def update_config(self):
        """已精简移除配置回写功能：仅通过外部程序自身的启动参数控制启停。"""
        logger.debug("已精简移除配置回写功能，跳过 update_config")

    async def kill_managed_process(self) -> None:
        if not self._prepared:
            return
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_processes())
        # 取消不能截断三轮清理，重复收尾也不会再清理三遍。
        cancelled = False
        while not self._cleanup_task.done():
            try:
                await asyncio.shield(self._cleanup_task)
            except asyncio.CancelledError:
                cancelled = True
        try:
            self._cleanup_task.result()
        finally:
            if cancelled:
                raise asyncio.CancelledError

    async def _cleanup_processes(self) -> None:
        try:
            if getattr(self.task_info, "manual_pause_requested", False):
                await self.process_tracker.cleanup_owned_tree()
            elif self.cleanup_targets:
                await self.process_tracker.cleanup(
                    self.cleanup_targets, self.cleanup_mode
                )
            else:
                await asyncio.to_thread(self.process_tracker.collect_children)
                await self._legacy_cleanup()
                for manager in self._launch_managers:
                    if manager is not self.general_process_manager:
                        await manager.kill()
                remaining = [
                    str(proc.pid)
                    for proc in self.process_tracker.owned.values()
                    if proc.is_running()
                ]
                if remaining:
                    raise CleanupFailed(
                        "进程清理失败，仍在运行: " + "、".join(remaining)
                    )
        except CleanupFailed:
            raise
        except Exception as e:
            raise CleanupFailed(f"进程清理失败: {e}") from e

    async def _legacy_cleanup(self):
        """中止关联进程（底层通过 taskkill /F /T 连续强杀 3 遍）"""

        errors = []
        try:
            logger.info(
                f"强制清理通用脚本进程 (taskkill /F /T x3): {self.script_exe_path}"
            )
            if (
                hasattr(self, "general_process_manager")
                and self.general_process_manager is not None
            ):
                await self.general_process_manager.kill()
            if hasattr(self, "script_exe_path") and self.script_exe_path is not None:
                await System.kill_process(self.script_exe_path, kill_tree=True)
        except Exception as e:
            logger.opt(exception=True).warning(f"中止通用脚本进程失败: {e}")
            errors.append(str(e))

        if self.game_manager is not None:
            logger.info("中止游戏/模拟器进程")
            try:
                if isinstance(self.game_manager, ProcessManager):
                    await self.game_manager.kill()
                    if self.script_config.get(
                        "Game", "Type"
                    ) == "Client" and self.script_config.get("Game", "IfForceClose"):
                        await System.kill_process(self.game_path, kill_tree=True)
                elif isinstance(self.game_manager, DeviceBase):
                    await self.game_manager.close(
                        self.script_config.get("Game", "EmulatorIndex"),
                    )
            except Exception as e:
                logger.opt(exception=True).warning(f"关闭游戏/模拟器失败: {e}")
                errors.append(str(e))
        if errors:
            raise CleanupFailed("进程清理失败: " + "；".join(errors))

    async def set_general(self) -> None:
        """启动前清理可能残留的旧脚本进程（不再注入或覆盖外部配置文件，仅靠启动参数控制启停）。"""
        logger.info(
            "准备启动脚本: 清理可能未退出的残留进程（不下发/不回写外部配置文件）"
        )
        if not self.cleanup_targets:
            await System.kill_process(self.script_exe_path, kill_tree=True)

    def _format_push_log(
        self,
        line: str,
        latest_time: datetime,
        content_override: Optional[str] = None,
    ) -> str:
        time_text = ""
        try:
            parsed = strptime(
                line[self.log_time_range[0] : self.log_time_range[1]],
                self.script_config.get("Script", "LogTimeFormat"),
                latest_time,
            )
            time_text = parsed.strftime("%H:%M")
        except (IndexError, ValueError):
            pass

        if content_override is not None:
            content = content_override
        else:
            content = (
                line[: self.log_time_range[0]] + line[self.log_time_range[1] :]
            ).strip()
            content = content or line.strip()
            content = re.sub(r"^(?:\[\]\s*)?\[[^\]]+\]\s*\[\w+\]:\s*", "", content)

        return f"{time_text} - {content}" if time_text else content

    async def check_log(self, log_content: list[str], latest_time: datetime) -> None:
        """有日志路径模式下的日志回调（保持原 Auto-MAS 判定逻辑）"""

        log = "".join(log_content)
        self.cur_user_log.content = log_content
        self.script_info.log = log

        if len(log_content) < self._push_log_processed:
            self._push_log_processed = 0
        for line in log_content[self._push_log_processed :]:
            marker = parse_marker(line)
            if marker is not None:
                op = marker.get("op")
                if op == "push":
                    self.push_log_buffer.append(
                        (
                            marker.get("type") or LOG_TYPE_NORMAL,
                            str(marker.get("text") or ""),
                        )
                    )
                continue
            if self.push_log_enabled and self.push_log_patterns_compiled:
                extracted = apply_patterns(
                    line, matchers=self.push_log_patterns_compiled
                )
                if extracted is not None:
                    log_type, text = extracted
                    self.push_log_buffer.append(
                        (
                            log_type,
                            self._format_push_log(
                                line, latest_time, content_override=text
                            ),
                        )
                    )
        self._push_log_processed = len(log_content)

        if log_content:
            self._log_observed = True
        if log_content and (
            latest_time != self._latest_log_time
            or len(log_content) != self._latest_log_count
        ):
            self._last_log_progress = time.monotonic()
            self._latest_log_time = latest_time
            self._latest_log_count = len(log_content)
        if self.wait_event.is_set():
            return
        if self.success_log.search(log) is not None:
            self._set_result("Success!", kind="success")
        else:
            error_sign = self.error_log.search(log)
            if error_sign is not None:
                self._set_result(f"异常日志: {error_sign}")

    async def final_task(self):
        if self.check_result != "Pass" or not self._prepared:
            return

        await self._cleanup_before_recovery()
        if getattr(self.task_info, "manual_pause_requested", False):
            if self.general_log_monitor is not None:
                await self.general_log_monitor.stop()
            if self._cleanup_error:
                self.task_info.pause_cleanup_error = str(self._cleanup_error)
            return
        if not self._finished:
            self.run_book = False
            if self._recovery_used:
                self._recovery_result = "补跑已取消"
            if hasattr(self, "cur_user_log"):
                self.cur_user_log.status = "任务被用户手动中止"
        if self.general_log_monitor is not None:
            await self.general_log_monitor.stop()
        if hasattr(self, "general_process_manager"):
            del self.general_process_manager
        if hasattr(self, "general_log_monitor"):
            self.general_log_monitor = None

        user_logs_list = []
        for t, log_item in self.cur_user_item.log_record.items():
            dt = t.astimezone(UTC4)
            log_path = Config.build_history_log_path(
                script_name=self.script_info.name,
                user_name=self.cur_user_item.name,
                log_time=dt,
            )
            user_logs_list.append(log_path.with_suffix(".json"))

            if log_item.status == "通用脚本正常运行中":
                log_item.status = "任务被用户手动中止"

            if len(log_item.content) == 0:
                if self.has_log_path:
                    log_item.content = ["未捕获到任何日志内容"]
                    if log_item.status == "未开始监看日志":
                        log_item.status = "未捕获到日志"
                else:
                    log_item.content = [f"无日志模式执行结束，状态: {log_item.status}"]

            await Config.save_general_log(log_path, log_item.content, log_item.status)

        if self.push_log_enabled and self.push_log_patterns_compiled:
            for log_type, text in flush_patterns(
                matchers=self.push_log_patterns_compiled
            ):
                self.push_log_buffer.append(
                    (
                        log_type,
                        self._format_push_log(
                            "", datetime.now(), content_override=text
                        ),
                    )
                )

        self.cur_user_item.push_log = self.push_log_buffer

        statistics = await Config.merge_statistic_info(user_logs_list)
        statistics["user_info"] = self.cur_user_item.name
        statistics["start_time"] = self.user_start_time.strftime("%Y-%m-%d %H:%M:%S")
        statistics["end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        statistics["user_result"] = (
            "代理任务全部完成" if self.run_book else self.cur_user_item.result
        )

        if self._recovery_used:
            statistics["user_result"] = (
                f"首轮失败（{self._first_failure}），{self._recovery_result}"
            )
        if self._ownership_warning:
            statistics["user_result"] += f"；{self._ownership_warning}"
        if self._cleanup_error:
            self.script_info.log = self._cleanup_error
            statistics["user_result"] += f"；{self._cleanup_error}"
        statistics["notification_failed"] = not self.run_book or bool(
            self._cleanup_error
        )
        success_symbol = "√" if self.run_book else "X"

        try:
            await push_notification(
                "统计信息",
                f"{datetime.now().strftime('%m-%d')} |{success_symbol}|  {self.cur_user_item.name} 的自动代理统计报告",
                statistics,
                self.cur_user_config,
                task_info=self.task_info,
            )
        except Exception as e:
            logger.opt(exception=True).warning(f"推送通知时出现异常: {e}")
            await Publisher.send(
                id=self.task_info.task_id,
                type=protocol.TASK_NOTICE,
                data=WSTaskNoticeData(
                    level="error", message=f"推送通知时出现异常: {e}"
                ),
            )

        if self.run_book:
            if (
                self.cur_user_config.get("Data", "ProxyTimes") == 0
                and self.cur_user_config.get("Info", "RemainedDay") != -1
            ):
                await self.cur_user_config.set(
                    "Info",
                    "RemainedDay",
                    self.cur_user_config.get("Info", "RemainedDay") - 1,
                )
            await self.cur_user_config.set(
                "Data",
                "ProxyTimes",
                self.cur_user_config.get("Data", "ProxyTimes") + 1,
            )
            self.cur_user_item.status = "完成"
            logger.success(f"用户 {self.cur_user_uid} 的自动代理任务已完成")
            if should_send_result(
                {"uncompleted_count": int(statistics["notification_failed"])}
            ):
                await Notify.push_plyer(
                    "成功完成一个自动代理任务！",
                    statistics["user_result"],
                    f"已完成 {self.cur_user_item.name} 的自动代理任务",
                    3,
                )
        else:
            logger.warning(f"用户 {self.cur_user_uid} 的自动代理任务未完成")
            self.cur_user_item.status = "异常"
            if should_send_result(
                {"uncompleted_count": int(statistics["notification_failed"])}
            ):
                await Notify.push_plyer(
                    "自动代理任务已结束",
                    statistics["user_result"],
                    f"{self.cur_user_item.name} 的自动代理结果",
                    3,
                )

    async def on_crash(self, e: Exception):
        self._finished = True
        self.run_book = False
        if self._recovery_used:
            self._recovery_result = "补跑失败"
        if hasattr(self, "cur_user_log"):
            self.cur_user_log.status = f"运行异常: {e}"
        self.cur_user_item.status = "异常"
        logger.opt(exception=True).warning(f"自动代理任务出现异常: {e}")
        await Publisher.send(
            id=self.task_info.task_id,
            type=protocol.TASK_NOTICE,
            data=WSTaskNoticeData(level="error", message=f"自动代理任务出现异常: {e}"),
        )
