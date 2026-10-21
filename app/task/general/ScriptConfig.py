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
import shlex
from pathlib import Path

from app.core.ws import Publisher, protocol
from app.models.config import GeneralConfig, GeneralUserConfig
from app.models.ConfigBase import MultipleConfig
from app.models.emulator import DeviceBase
from app.models.schema import WSTaskNoticeData
from app.models.task import ScriptItem, TaskExecuteBase
from app.services import System
from app.utils import ProcessManager, get_logger

logger = get_logger("通用脚本设置")


class ScriptConfigTask(TaskExecuteBase):
    """脚本设置模式（已精简：不再注入或回写外部配置文件，仅通过外部程序自身的启动参数启动和关闭）"""

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

    async def prepare(self):
        self.general_process_manager = ProcessManager()
        self.wait_event = asyncio.Event()

        self.script_path = Path(self.script_config.get("Script", "ScriptPath"))

        arguments_list = []
        path_list = []

        for argument in [
            part.strip()
            for part in str(self.script_config.get("Script", "Arguments")).split("|")
            if part.strip()
        ]:
            arg_parts = [
                part.strip() for part in argument.split("%", 1) if part.strip()
            ]

            path_list.append(
                (
                    self.script_path / arg_parts[0]
                    if len(arg_parts) > 1
                    else self.script_path
                ).resolve()
            )
            arguments_list.append(shlex.split(arg_parts[-1]))

        self.script_arguments = arguments_list[0] if len(arguments_list) > 0 else []
        self.script_set_exe_path = (
            path_list[1] if len(path_list) > 1 else self.script_path
        )
        self.script_set_arguments = arguments_list[1] if len(arguments_list) > 1 else []

    async def main_task(self):
        await self.prepare()
        await self.set_general()
        logger.info(
            f"运行脚本设置任务: {self.script_set_exe_path}, 参数: {self.script_set_arguments}"
        )
        await self.general_process_manager.open_process(
            self.script_set_exe_path, *self.script_set_arguments
        )

        self.wait_event.clear()
        await self.wait_event.wait()

    async def set_general(self) -> None:
        """清理残留进程（不再注入外部配置文件）"""
        logger.info(f"清理残留进程以启动脚本设置: {self.cur_user_item.user_id}")
        await System.kill_process(self.script_set_exe_path, kill_tree=True)

    async def final_task(self):
        await self.general_process_manager.kill()
        await System.kill_process(self.script_set_exe_path, kill_tree=True)
        del self.general_process_manager
        self.cur_user_item.status = "完成"
        logger.success("通用脚本设置会话已结束（不执行配置回写）")

    async def on_crash(self, e: Exception):
        self.cur_user_item.status = "异常"
        logger.opt(exception=True).warning(f"脚本设置任务出现异常: {e}")
        await Publisher.send(
            id=self.task_info.task_id,
            type=protocol.TASK_NOTICE,
            data=WSTaskNoticeData(level="error", message=f"脚本设置任务出现异常: {e}"),
        )
