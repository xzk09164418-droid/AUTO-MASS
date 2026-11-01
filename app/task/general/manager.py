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


import uuid
from datetime import datetime
from pathlib import Path

from app.core import Config, EmulatorManager
from app.core.child_session import ChildSessionManager
from app.core.general_ownership import general_ownership
from app.core.ws import Publisher, protocol
from app.models.config import GeneralConfig, GeneralUserConfig
from app.models.ConfigBase import MultipleConfig
from app.models.emulator import DeviceProvider
from app.models.schema import WSTaskNoticeData
from app.models.task import ScriptItem, UserItem
from app.task.manager_base import ScriptManagerBase
from app.tools.push_log import build_user_result_text
from app.utils import ProcessManager, get_logger
from app.utils.constants import TASK_MODE_ZH

from .AutoProxy import AutoProxyTask
from .ScriptConfig import ScriptConfigTask
from .tools import push_notification

logger = get_logger("通用调度器")

METHOD_BOOK: dict[str, type[AutoProxyTask | ScriptConfigTask]] = {
    "AutoProxy": AutoProxyTask,
    "ScriptConfig": ScriptConfigTask,
}


class GeneralManager(ScriptManagerBase):
    """通用脚本控制器（已精简：不再强制要求日志路径与配置路径，不再进行配置注入与回写）"""

    def __init__(
        self,
        script_info: ScriptItem,
        *,
        device_provider: DeviceProvider | None = None,
    ):
        super().__init__()

        if script_info.task_info is None:
            raise RuntimeError("ScriptItem 未绑定到 TaskItem")

        self.task_info = script_info.task_info
        self.script_info = script_info
        self.check_result = "-"
        self._ownership_skipped = False
        self._prepared = False
        self._config_locked = False
        self._device_provider = device_provider

    def is_user_selected(self, user_id: uuid.UUID | str, user) -> bool:
        # 外部中断后从头重跑本轮最初选中的用户。已完成用户的剩余天数/次数可能
        # 已变化，不能因此悄悄把“从头重跑”降为只执行未完成用户；历史计数不回滚。
        script_id = self.script_info.script_id
        original = self.task_info.external_restart_user_ids.get(script_id)
        if (
            script_id in self.task_info.external_restart_script_ids
            and original is not None
        ):
            return str(user_id) in original
        return super().is_user_selected(user_id, user)

    async def check(self) -> str:
        """校验通用脚本配置是否可用（不再强制要求填写 ConfigPath 和 LogPath）"""
        if self.task_info.mode not in METHOD_BOOK:
            return "不支持的任务模式, 请检查任务配置！"
        if not isinstance(
            Config.ScriptConfig[uuid.UUID(self.script_info.script_id)], GeneralConfig
        ):
            return "脚本配置类型错误, 不是通用脚本类型"
        if (
            Config.ScriptConfig[uuid.UUID(self.script_info.script_id)].get(
                "Script", "IfTrackProcess"
            )
            and not Config.ScriptConfig[uuid.UUID(self.script_info.script_id)].get(
                "Script", "TrackProcessName"
            )
            and not Config.ScriptConfig[uuid.UUID(self.script_info.script_id)].get(
                "Script", "TrackProcessExe"
            )
            and not Config.ScriptConfig[uuid.UUID(self.script_info.script_id)].get(
                "Script", "TrackProcessCmdline"
            )
        ):
            return "开启追踪子进程后, 需至少填写一项追踪进程信息！"

        if Config.ScriptConfig[uuid.UUID(self.script_info.script_id)].get(
            "Game", "Enabled"
        ):
            if (
                Config.ScriptConfig[uuid.UUID(self.script_info.script_id)].get(
                    "Game", "Type"
                )
                == "Emulator"
            ) and (
                Config.ScriptConfig[uuid.UUID(self.script_info.script_id)].get(
                    "Game", "EmulatorId"
                )
                == "-"
                or Config.ScriptConfig[uuid.UUID(self.script_info.script_id)].get(
                    "Game", "EmulatorIndex"
                )
                in ["", "-"]
            ):
                return "未完成模拟器配置, 请检查脚本配置中的模拟器设置！"
            elif (
                Config.ScriptConfig[uuid.UUID(self.script_info.script_id)].get(
                    "Game", "Type"
                )
                == "Client"
            ) and not Path(
                Config.ScriptConfig[uuid.UUID(self.script_info.script_id)].get(
                    "Game", "Path"
                )
            ).exists():
                return "未完成游戏配置, 请检查脚本配置中的游戏设置！"
            elif (
                Config.ScriptConfig[uuid.UUID(self.script_info.script_id)].get(
                    "Game", "Type"
                )
                == "URL"
            ) and (
                not Config.ScriptConfig[uuid.UUID(self.script_info.script_id)].get(
                    "Game", "URL"
                )
                or not Config.ScriptConfig[uuid.UUID(self.script_info.script_id)].get(
                    "Game", "ProcessName"
                )
            ):
                return "未完成URL配置, 请检查脚本配置中的URL和进程名称设置！"

        return "Pass"

    async def prepare(self):
        """运行前准备"""

        await Config.ScriptConfig[uuid.UUID(self.script_info.script_id)].lock()
        self._config_locked = True
        self.script_config = Config.ScriptConfig[uuid.UUID(self.script_info.script_id)]
        self.user_config = MultipleConfig([GeneralUserConfig])
        await self.user_config.load(await self.script_config.UserData.toDict())
        logger.success(f"{self.script_info.script_id}已锁定, 通用脚本配置提取完成")

        if Config.ScriptConfig[uuid.UUID(self.script_info.script_id)].get(
            "Game", "Enabled"
        ):
            if (
                Config.ScriptConfig[uuid.UUID(self.script_info.script_id)].get(
                    "Game", "Type"
                )
                == "Emulator"
            ):
                device_provider = (
                    self._device_provider or EmulatorManager.get_emulator_instance
                )
                self.emulator_manager = await device_provider(
                    self.script_config.get("Game", "EmulatorId")
                )

            elif Config.ScriptConfig[uuid.UUID(self.script_info.script_id)].get(
                "Game", "Type"
            ) in ["Client", "URL"]:
                self.game_process_manager = ProcessManager()

        if self.task_info.mode == "ScriptConfig":
            self.script_info.user_list = [
                UserItem(
                    user_id=self.task_info.user_id or "Default", name="", status="等待"
                )
            ]
        else:
            self.script_info.user_list = self.build_proxy_user_list(
                self.user_config.items()
            )
            if (
                self.script_info.script_id
                not in self.task_info.external_restart_script_ids
            ):
                self.task_info.external_restart_user_ids[self.script_info.script_id] = (
                    frozenset(user.user_id for user in self.script_info.user_list)
                )
        logger.info(
            f"用户列表加载完成, 已筛选用户数: {len(self.script_info.user_list)}"
        )

    async def main_task(self):

        self.check_result = await self.check()
        if self.check_result != "Pass":
            logger.warning(f"未通过配置检查: {self.check_result}")
            await Publisher.send(
                id=self.task_info.task_id,
                type=protocol.TASK_NOTICE,
                data=WSTaskNoticeData(level="error", message=self.check_result),
            )
            return

        if self.task_info.mode == "AutoProxy":
            config = Config.ScriptConfig[uuid.UUID(self.script_info.script_id)]
            allowed = await general_ownership.before_run(
                self.script_info.script_id,
                self.script_info.name,
                config,
                automated=self.task_info.trigger_source != "manual_task",
            )
            if not allowed:
                self._ownership_skipped = True
                self.script_info.status = "跳过"
                self.script_info.log = "主体归属待确认，已跳过本次运行"
                return
        self.begin_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await self.prepare()
        self._prepared = True

        if not isinstance(self.script_config, GeneralConfig):
            raise RuntimeError("脚本配置类型错误, 不是通用脚本类型")

        for self.script_info.current_index in range(len(self.script_info.user_list)):
            # 相邻两个子任务之间检查是否有外部程序申请使用本地远程桌面
            if self.script_info.current_index > 0:
                await ChildSessionManager.wait_if_external_requested(
                    boundary_label=f"通用脚本[{self.script_info.name}]子任务间隔"
                )

            current_user = self.script_info.user_list[self.script_info.current_index]
            if (
                self.task_info.mode == "AutoProxy"
                and not await self.check_user_before_run(
                    current_user, self.user_config[uuid.UUID(current_user.user_id)]
                )
            ):
                continue

            task = METHOD_BOOK[self.task_info.mode](
                self.script_info,
                self.script_config,
                self.user_config,
                (
                    (
                        self.emulator_manager
                        if (self.script_config.get("Game", "Type") == "Emulator")
                        else self.game_process_manager
                    )
                    if self.script_config.get("Game", "Enabled")
                    else None
                ),
            )

            await self.run_user_task(current_user, task)

    async def final_task(self):
        """运行结束后的收尾工作（不进行任何外部配置文件恢复或回写）"""

        if self._ownership_skipped:
            return
        if self.check_result != "Pass":
            self.script_info.status = "异常"
            return self.check_result

        if not self._prepared:
            if self._config_locked:
                await Config.ScriptConfig[
                    uuid.UUID(self.script_info.script_id)
                ].unlock()
            self.script_info.status = "跳过"
            return

        logger.info("通用脚本任务已结束, 开始执行后续操作")

        await Config.ScriptConfig[uuid.UUID(self.script_info.script_id)].unlock()
        logger.success(f"已解锁脚本配置 {self.script_info.script_id}")

        if getattr(self.task_info, "manual_pause_requested", False):
            self.script_info.status = "已暂停"
            return

        if self.task_info.mode == "AutoProxy":
            await Config.ScriptConfig[
                uuid.UUID(self.script_info.script_id)
            ].UserData.load(await self.user_config.toDict())
            await Config.ScriptConfig.save()

            summary = self.collect_user_results()

            title = f"{datetime.now().strftime('%m-%d')} | {self.script_info.name or '空白'}的{TASK_MODE_ZH[self.task_info.mode]}任务报告"
            has_uncompleted = summary.uncompleted_count > 0
            user_result_text = build_user_result_text(
                self.script_info.user_list, has_uncompleted
            )
            result = self.build_proxy_report(result_text=user_result_text)

            try:
                await push_notification(
                    mode="代理结果",
                    title=title,
                    message=result,
                    user_config=None,
                    task_info=self.task_info,
                )
            except Exception as e:
                logger.opt(exception=True).warning(f"推送代理结果时出现异常: {e}")
                await Publisher.send(
                    id=self.task_info.task_id,
                    type=protocol.TASK_NOTICE,
                    data=WSTaskNoticeData(
                        level="error", message=f"推送代理结果时出现异常: {e}"
                    ),
                )

        self.script_info.status = "完成"

    async def on_crash(self, e: Exception):

        self.script_info.status = "异常"
        logger.opt(exception=True).warning(f"通用脚本任务出现异常: {e}")
        await Publisher.send(
            id=self.task_info.task_id,
            type=protocol.TASK_NOTICE,
            data=WSTaskNoticeData(level="error", message=f"通用脚本任务出现异常: {e}"),
        )
