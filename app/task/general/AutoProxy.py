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
from app.core.ws import Publisher, protocol
from app.log_box.hooks import make_line_hook
from app.log_box.markers import parse_marker
from app.models.config import GeneralConfig, GeneralUserConfig
from app.models.ConfigBase import MultipleConfig
from app.models.emulator import DeviceBase
from app.models.schema import WSTaskNoticeData
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
    """自动代理模式（支持无日志路径退出码模式 + 有日志路径双模判定，移除配置回写，强杀 3 遍）"""

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

    async def check(self) -> str:
        # 单独运行脚本是用户主动指定的一次性运行，不受单日代理次数上限约束
        if (
            self.task_info.is_queue_task
            and self.script_info.script_id not in self.task_info.external_restart_script_ids
            and self.script_config.get("Run", "ProxyTimesLimit") != 0
            and self.cur_user_config.get("Data", "ProxyTimes")
            >= self.script_config.get("Run", "ProxyTimesLimit")
        ):
            self.cur_user_item.status = "跳过"
            return "今日代理次数已达上限, 跳过该用户"

        return "Pass"

    async def prepare(self):
        self.general_process_manager = ProcessManager()
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

    def _resolve_log_file_path(self) -> Path:
        return self.script_log_path

    def _note_launch_arguments_skipped(self) -> None:
        arguments = str(self.script_config.get("Game", "Arguments") or "").strip()
        if arguments:
            logger.info(f"检测到游戏已在运行，本轮不会应用启动参数（{arguments}）")

    async def _wait_without_log_until_exit(self) -> None:
        """无日志模式：当未填写日志路径时，日志超时（RunTimeLimit）自动失效，
        仅受总上限时间（HardTimeLimit）约束；只要进程在上限时间内自行退出（不限返回码）即视为成功。
        """
        logger.info("当前未填写日志路径：启用无日志退出判定模式（日志超时已自动失效，仅受总上限时间约束）")
        self.script_info.log = "无日志模式：正在等待外部脚本进程执行完成..."

        while True:
            if not await self.general_process_manager.is_running():
                exit_code = self.general_process_manager.returncode
                msg = f"外部脚本进程已在上限时间内自行退出 (退出码: {exit_code})"
                logger.success(msg)
                self.cur_user_log.content = [msg]
                self.cur_user_log.status = "Success!"
                self.script_info.log = msg
                self.wait_event.set()
                return
            await asyncio.sleep(0.5)

    async def main_task(self):
        """自动代理模式主逻辑"""

        self.curdate = datetime.now(tz=UTC4).strftime("%Y-%m-%d")
        if self.cur_user_config.get("Data", "LastProxyDate") != self.curdate:
            await self.cur_user_config.set("Data", "LastProxyDate", self.curdate)
            await self.cur_user_config.set("Data", "ProxyTimes", 0)

        self.check_result = await self.check()
        if self.check_result != "Pass":
            if self.cur_user_item.status == "异常":
                await Publisher.send(
                    id=self.task_info.task_id,
                    type=protocol.TASK_NOTICE,
                    data=WSTaskNoticeData(
                        level="error",
                        message=f"用户 {self.cur_user_item.name} 检查未通过: {self.check_result}",
                    ),
                )
            return

        await self.prepare()
        await self.run_user_scripts_before()

        logger.info(f"开始代理用户: {self.cur_user_uid}")
        self.cur_user_item.status = "运行"

        for i in range(self.script_config.get("Run", "RunTimesLimit")):
            if self.run_book:
                break
            if self.remaining_hard_timeout_seconds() <= 0:
                logger.warning("已达到任务总上限时间，不再进行后续重试")
                break

            logger.info(
                f"用户 {self.cur_user_item.name} - 尝试次数: {i + 1}/{self.script_config.get('Run', 'RunTimesLimit')} "
                f"(剩余总上限时间: {self.remaining_hard_timeout_seconds():.1f}s)"
            )
            self.log_start_time = datetime.now()
            self.log_start_at = time.monotonic()
            self.cur_user_item.log_record[self.log_start_time] = self.cur_user_log = (
                LogRecord()
            )
            self.push_log_buffer.clear()
            self._push_log_processed = 0
            self._process_seen = False
            for _matcher in self.push_log_patterns_compiled:
                _reset = getattr(_matcher, "reset", None)
                if _reset is not None:
                    _reset()

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
                            if game_process_name and is_process_running(
                                game_process_name
                            ):
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
                                    *str(
                                        self.script_config.get("Game", "Arguments")
                                    ).split(" "),
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
                    await self.handle_pre_script_error("游戏/模拟器启动失败", e)
                    continue

            await self.set_general()
            logger.info(
                f"通过启动参数运行外部脚本任务: {self.script_exe_path}, 参数: {self.script_arguments}"
            )

            self.wait_event.clear()
            t = datetime.now()
            await self.general_process_manager.open_process(
                self.script_exe_path,
                *self.script_arguments,
                target_process=self.script_target_process_info,
            )

            if not self.has_log_path:
                # 无日志路径模式：仅以在上限时间内自行退出作为成功条件
                await self._wait_without_log_until_exit()
            else:
                # 有日志路径模式：保留原 Auto-MAS 日志监控与日志停滞超时逻辑
                self.script_info.log = "正在等待脚本日志文件生成"
                if_get_file = False
                target_suffix: int | None = None
                deadline = time.monotonic() + 60
                if self.log_use_prefix:
                    prefix_fmt = self.log_format[: -len(_PREFIX_SENTINEL)]
                    pattern = _format_to_prefix_regex(prefix_fmt)
                while time.monotonic() < deadline:
                    if self.log_use_prefix:
                        today = t.date()

                        current_suffix = 0
                        current_file: Path | None = None
                        if self.script_log_path.parent.is_dir():
                            for log_file in self.script_log_path.parent.iterdir():
                                if not log_file.is_file():
                                    continue
                                m = pattern.match(log_file.name)
                                if not m:
                                    continue
                                with suppress(ValueError):
                                    file_time = strptime(m.group(0), prefix_fmt, t)
                                if file_time.date() != today:
                                    continue
                                tail = log_file.name[m.end() :]
                                num_match = re.search(
                                    r"(\d+)\s*$", tail.rsplit(".", 1)[0]
                                )
                                suffix = int(num_match.group(1)) if num_match else 0
                                if suffix > current_suffix:
                                    current_suffix = suffix
                                    current_file = log_file

                        if target_suffix is None:
                            target_suffix = current_suffix + 1

                        if current_suffix >= target_suffix and current_file is not None:
                            self.script_log_path = current_file
                            logger.success(
                                f"成功定位到日志文件（按日期前缀）: {self.script_log_path} "
                                f"(suffix={current_suffix})"
                            )
                            if_get_file = True
                            break

                        self.script_info.log = (
                            f"正在等待脚本日志文件生成（按日期前缀，"
                            f"目标后缀 -{target_suffix}）"
                        )
                        await asyncio.sleep(1)
                    else:
                        if self.script_log_path.parent.is_dir():
                            for log_file in self.script_log_path.parent.iterdir():
                                if log_file.is_file():
                                    with suppress(ValueError):
                                        if (
                                            strptime(log_file.name, self.log_format, t)
                                            >= t
                                        ):
                                            self.script_log_path = log_file
                                            logger.success(
                                                f"成功定位到日志文件: {self.script_log_path}"
                                            )
                                            if_get_file = True
                                            break
                        if if_get_file:
                            break
                        await asyncio.sleep(1)
                else:
                    await self.handle_pre_script_error("未找到日志文件")
                    break

                assert self.general_log_monitor is not None
                await self.general_log_monitor.start_monitor_file(
                    self._resolve_log_file_path, self.log_start_time
                )
                await self.wait_event.wait()
                await self.general_log_monitor.stop()

            if self.cur_user_log.status == "Success!":
                self.run_book = True
                logger.info(f"用户: {self.cur_user_uid} - 通用脚本进程完成代理任务")
                self.script_info.log = (
                    "检测到通用脚本进程完成代理任务\n正在等待相关程序结束并执行强制清理"
                )

                await self.kill_managed_process()
                await asyncio.sleep(10)
            else:
                logger.warning(
                    f"用户: {self.cur_user_uid} - 代理任务异常: {self.cur_user_log.status}"
                )
                self.script_info.log = f"{self.cur_user_log.status}\n正在中止相关程序"

                await self.kill_managed_process()

                await Notify.push_plyer(
                    "用户自动代理出现异常！",
                    f"用户 {self.cur_user_item.name} 的自动代理出现一次异常",
                    f"{self.cur_user_item.name}的自动代理出现异常",
                    3,
                )

                await asyncio.sleep(10)

            await asyncio.sleep(3)

    async def handle_pre_script_error(
        self, error_message: str, e: Exception | None = None
    ):
        if e is None:
            logger.warning(f"用户: {self.cur_user_uid} - {error_message}")
            await Publisher.send(
                id=self.task_info.task_id,
                type=protocol.TASK_NOTICE,
                data=WSTaskNoticeData(level="error", message=error_message),
            )
        else:
            logger.opt(exception=True).warning(
                f"用户: {self.cur_user_uid} - {error_message}: {e}"
            )
            await Publisher.send(
                id=self.task_info.task_id,
                type=protocol.TASK_NOTICE,
                data=WSTaskNoticeData(level="error", message=f"{error_message}: {e}"),
            )
        self.cur_user_log.content = [f"{error_message}, 无日志记录"]
        self.cur_user_log.status = error_message

        await self.kill_managed_process()

        await Notify.push_plyer(
            "用户自动代理出现异常！",
            f"用户 {self.cur_user_item.name} 自动代理时{error_message}",
            f"{self.cur_user_item.name}的自动代理出现异常",
            3,
        )

    async def update_config(self):
        """已精简移除配置回写功能：仅通过外部程序自身的启动参数控制启停。"""
        logger.debug("已精简移除配置回写功能，跳过 update_config")

    async def kill_managed_process(self):
        """中止关联进程（底层通过 taskkill /F /T 连续强杀 3 遍）"""

        try:
            logger.info(f"强制清理通用脚本进程 (taskkill /F /T x3): {self.script_exe_path}")
            if hasattr(self, "general_process_manager") and self.general_process_manager is not None:
                await self.general_process_manager.kill()
            if hasattr(self, "script_exe_path") and self.script_exe_path is not None:
                await System.kill_process(self.script_exe_path, kill_tree=True)
        except Exception as e:
            logger.opt(exception=True).warning(f"中止通用脚本进程失败: {e}")

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

    async def set_general(self) -> None:
        """启动前清理可能残留的旧脚本进程（不再注入或覆盖外部配置文件，仅靠启动参数控制启停）。"""
        logger.info("准备启动脚本: 清理可能未退出的残留进程（不下发/不回写外部配置文件）")
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

        # 保持原 Auto-MAS 逻辑：
        # 命中 SuccessLog 判成功；命中 ErrorLog 或日志停滞超时判失败；未配 SuccessLog 则进程正常退出判成功
        if self.success_log.search(log) is not None:
            self.cur_user_log.status = "Success!"
        elif self.is_log_stalled(
            latest_time, minutes=self.script_config.get("Run", "RunTimeLimit")
        ):
            self.cur_user_log.status = "脚本进程超时"
        else:
            error_sign = self.error_log.search(log)
            if error_sign is not None:
                self.cur_user_log.status = f"异常日志: {error_sign}"
            elif await self.general_process_manager.is_running():
                self._process_seen = True
                self.cur_user_log.status = "通用脚本正常运行中"
            elif (
                not self._process_seen
                and time.monotonic() - self.log_start_at < _PROCESS_START_GRACE_SECONDS
            ):
                self.cur_user_log.status = "通用脚本正常运行中"
            elif self.success_log.configured:
                self.cur_user_log.status = "脚本在完成任务前退出"
            else:
                self.cur_user_log.status = "Success!"

        logger.debug(f"通用脚本日志分析结果: {self.cur_user_log.status}")
        if self.cur_user_log.status != "通用脚本正常运行中":
            logger.info(f"通用脚本任务结果: {self.cur_user_log.status}, 日志锁已释放")
            self.wait_event.set()

    async def final_task(self):
        if self.check_result != "Pass":
            return

        await self.kill_managed_process()
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

        statistics["notification_failed"] = not self.run_book
        success_symbol = "√" if self.run_book else "X"

        try:
            await push_notification(
                "统计信息",
                f"{datetime.now().strftime('%m-%d')} |{success_symbol}|  {self.cur_user_item.name} 的自动代理统计报告",
                statistics,
                self.cur_user_config,
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
            await Notify.push_plyer(
                "成功完成一个自动代理任务！",
                f"已完成用户 {self.cur_user_item.name} 的自动代理任务",
                f"已完成 {self.cur_user_item.name} 的自动代理任务",
                3,
            )
        else:
            logger.warning(f"用户 {self.cur_user_uid} 的自动代理任务未完成")
            self.cur_user_item.status = "异常"

    async def on_crash(self, e: Exception):
        self.cur_user_item.status = "异常"
        logger.opt(exception=True).warning(f"自动代理任务出现异常: {e}")
        await Publisher.send(
            id=self.task_info.task_id,
            type=protocol.TASK_NOTICE,
            data=WSTaskNoticeData(level="error", message=f"自动代理任务出现异常: {e}"),
        )
