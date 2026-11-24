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
from pathlib import Path

from app.core.ws import Publisher, protocol
from app.models.config import GeneralConfig, GeneralUserConfig
from app.models.ConfigBase import MultipleConfig
from app.models.emulator import DeviceBase
from app.models.schema import WSTaskNoticeData
from app.models.task import ScriptItem, TaskExecuteBase
from app.services import System
from app.task.general.tools.backup_archive import archive_native_backup
from app.task.general.tools.launch import is_shared_interpreter, launch_commands
from app.utils import ProcessManager, get_logger

logger = get_logger("通用脚本设置")


class ScriptConfigTask(TaskExecuteBase):
    """打开源程序设置，保留源程序写入的原生配置。"""

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

        commands = launch_commands(
            self.script_path, str(self.script_config.get("Script", "Arguments"))
        )
        self.script_set_exe_path, self.script_set_arguments = (
            commands[1] if len(commands) > 1 else commands[0]
        )

    async def main_task(self):
        await self.prepare()
        await self.archive_native_config()
        await self.set_general()
        logger.info(
            f"运行脚本设置任务: {self.script_set_exe_path}, 参数: {self.script_set_arguments}"
        )
        directory = self.script_config.get("Script", "WorkingDirectory")
        await self.general_process_manager.open_process(
            self.script_set_exe_path,
            raw_arguments=self.script_set_arguments,
            cwd=Path(directory) if directory else None,
        )

        self.wait_event.clear()
        await self.wait_event.wait()

    async def archive_native_config(self) -> None:
        raw = str(self.script_config.get("Script", "ConfigPath") or "").strip()
        if raw in ("", "."):
            return
        path = Path(raw)
        if not path.is_absolute():
            path = Path(str(self.script_config.get("Info", "RootPath") or ".")) / path
        if path.exists():
            await asyncio.to_thread(
                archive_native_backup,
                self.script_info.script_id,
                path,
                str(self.script_config.get("Script", "ConfigPathMode")),
            )

    async def set_general(self) -> None:
        """清理残留进程（不再注入外部配置文件）"""
        logger.info(f"清理残留进程以启动脚本设置: {self.cur_user_item.user_id}")
        if not is_shared_interpreter(self.script_set_exe_path):
            await System.kill_process(self.script_set_exe_path, kill_tree=True)

    async def final_task(self):
        await self.general_process_manager.kill()
        if not is_shared_interpreter(self.script_set_exe_path):
            await System.kill_process(self.script_set_exe_path, kill_tree=True)
        del self.general_process_manager
        await self.archive_native_config()
        self.cur_user_item.status = "完成"
        logger.success("通用脚本设置会话已结束，源程序写入的原生配置已保留")

    async def on_crash(self, e: Exception):
        self.cur_user_item.status = "异常"
        logger.opt(exception=True).warning(f"脚本设置任务出现异常: {e}")
        await Publisher.send(
            id=self.task_info.task_id,
            type=protocol.TASK_NOTICE,
            data=WSTaskNoticeData(level="error", message=f"脚本设置任务出现异常: {e}"),
        )
