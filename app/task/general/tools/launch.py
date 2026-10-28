"""解析通用脚本的运行/设置入口，允许设置入口显式使用空参数。"""

import shlex
from pathlib import Path


def launch_commands(script_path: Path, arguments: str) -> list[tuple[Path, list[str]]]:
    """解析 ``相对程序%参数|设置程序%参数``，不丢弃百分号后的空参数。

    第二入口的空参数是有意的：原生配置窗口不能继承自动执行参数。
    未使用百分号的旧配置仍以 ScriptPath 为程序路径。
    """
    commands = []
    for entry in arguments.split("|"):
        if not entry.strip():
            continue
        executable, separator, command = entry.strip().partition("%")
        path = script_path / executable.strip() if separator else script_path
        commands.append((path.resolve(), shlex.split(command if separator else entry)))
    return commands or [(script_path.resolve(), [])]
