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
import sys
import tempfile
from pathlib import Path

from app.utils import ProcessRunner, get_logger
from app.utils.platform import IS_WINDOWS
from app.utils.platform.common.process_runner import (
    ProcessResult,
    _terminate_process_tree,
    create_subprocess,
    decode_bytes,
)
from app.utils.platform.process import platform_process

logger = get_logger("自定义脚本执行工具")


async def _run_windows_hook(
    cmd: list[str], path: Path, env: dict[str, str] | None
) -> ProcessResult:
    # The task backend already runs in the selected Windows session. Wait for the
    # hook itself: a program deliberately detached with START may inherit stdout.
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        process = await create_subprocess(
            *cmd,
            cwd=path.parent,
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=output,
            stderr=errors,
        )
        try:
            rc = await asyncio.wait_for(process.wait(), timeout=600)
        except (TimeoutError, asyncio.CancelledError):
            if process.returncode is None:
                await asyncio.to_thread(_terminate_process_tree, process.pid)
                await process.wait()
            raise
        output.seek(0)
        errors.seek(0)
        return ProcessResult(
            decode_bytes(output.read()), decode_bytes(errors.read()), rc
        )


async def execute_script_task(script_path: Path, task_name: str) -> bool:
    """执行脚本任务并等待结束"""

    if not script_path.is_file():
        logger.warning(f"{task_name}脚本不存在")
        return False

    try:
        logger.info(
            f"开始执行{task_name}: {script_path}, 工作目录: {script_path.parent}"
        )

        script_path = script_path.resolve()
        env = None
        # 解释器只接收脚本文件，文件内容由对应的原生解释器执行。
        if script_path.suffix.lower() == ".py":
            cmd = [sys.executable, str(script_path)]
        elif script_path.suffix.lower() in [".bat", ".cmd"]:
            if not IS_WINDOWS:
                logger.warning(f"{task_name} 批处理文件需要 Windows 命令解释器")
                return False
            interpreter = str(Path(os.environ["SystemRoot"]) / "System32/cmd.exe")
            # Expand this one quoted filename in cmd itself, without CALL or delayed
            # expansion. Literal %, !, &, spaces and parentheses in the path survive.
            env = dict(os.environ, AUTO_MAS_HOOK_FILE=f'"{script_path}"')
            cmd = [interpreter, "/d", "/v:off", "/c", "%AUTO_MAS_HOOK_FILE%"]
        elif script_path.suffix.lower() == ".exe":
            cmd = [str(script_path)]
        elif script_path.suffix.lower() == ".ps1":
            cmd = [
                "powershell.exe" if IS_WINDOWS else "pwsh",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
            ]
        elif script_path.suffix.lower() == ".js":
            cmd = ["node", str(script_path)]
        elif script_path.suffix.lower() == ".sh":
            cmd = ["bash", str(script_path)]
        elif script_path.suffix.lower() == "":
            logger.warning(f"{task_name}脚本没有指定后缀名, 无法执行")
            return False
        else:
            # 使用系统默认程序打开
            await platform_process.open_protocol(str(script_path))
            return True

        if IS_WINDOWS:
            result = await _run_windows_hook(cmd, script_path, env)
        else:
            result = await ProcessRunner.run_process(
                *cmd,
                cwd=script_path.parent,
                timeout=600,
                kill_tree_on_cancel=True,
            )

        if result.returncode == 0:
            logger.success(
                f"{task_name}进程正常退出(返回码: {result.returncode}), "
                f"输出:\n{result.stdout}"
            )
            if result.stderr:
                logger.warning(f"{task_name}错误输出:\n{result.stderr}")
            return True
        else:
            logger.warning(f"{task_name}执行失败({result.returncode}):")
            logger.warning(f"  - 标准输出:{result.stdout}")
            logger.warning(f"  - 错误输出:{result.stderr}")
            return False

    except Exception as e:
        logger.opt(exception=True).warning(f"执行{task_name}时出现异常: {e}")
        return False
