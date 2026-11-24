"""Select the run or settings executable without interpreting its Windows arguments."""

import re
from pathlib import Path


def is_shared_interpreter(path: Path) -> bool:
    return path.name.casefold() in {
        "cmd.exe",
        "powershell.exe",
        "pwsh.exe",
        "python.exe",
        "pythonw.exe",
    }


def launch_commands(script_path: Path, arguments: str) -> list[tuple[Path, str]]:
    # Old profiles select a relative executable inside a directory (or via ../).
    # A configured executable otherwise owns its entire argument string.
    legacy = script_path.is_dir() or arguments.lstrip().startswith(("..\\", "../"))
    if legacy and not is_shared_interpreter(script_path):
        entries = re.split(
            r"\|(?=[^%|\"<>]+?\.(?:exe|bat|cmd)\s*%)", arguments, flags=re.I
        )
        commands = []
        for entry in entries:
            relative, sep, tail = entry.partition("%")
            if not sep or not relative.strip().lower().endswith(
                (".exe", ".bat", ".cmd")
            ):
                break
            commands.append(((script_path / relative.strip()).resolve(), tail))
        else:
            return commands
    return [(script_path.resolve(), arguments)]
