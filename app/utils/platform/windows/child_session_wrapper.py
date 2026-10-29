"""本地远程桌面（Child Session）子会话进程包装器（Wrapper）。

通过计划任务 `Schedule.Service` (`TASK_RUN_USE_SESSION_ID`) 在 Child Session 内拉起本包装器，
由本包装器在远程桌面会话内部启动目标脚本/外部程序，实时将运行状态、子进程 PID 与退出码（returncode）
写入共享状态文件，并在收到停止信号或需要强制清理时执行 3 遍 `taskkill /F /T`。
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

FORCE_KILL_PASSES = 3


def _current_session_id() -> int | None:
    if os.name != "nt":
        return None
    try:
        session_id = ctypes.c_uint(0)
        pid = ctypes.windll.kernel32.GetCurrentProcessId()
        if ctypes.windll.kernel32.ProcessIdToSessionId(pid, ctypes.byref(session_id)):
            return int(session_id.value)
    except Exception:
        pass
    return None


def _write_state_atomic(state_file: Path, payload: dict[str, Any]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = state_file.with_suffix(state_file.suffix + ".tmp")
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        tmp_file.write_text(data, encoding="utf-8")
        os.replace(tmp_file, state_file)
    except OSError:
        try:
            state_file.write_text(data, encoding="utf-8")
        except OSError:
            pass


def force_kill_tree_three_times(pid: int | None, exe_name: str | None = None) -> None:
    """按需求强制调用 `taskkill /F /T` 强杀 3 遍，确保目标进程树彻底终止。"""

    for _ in range(FORCE_KILL_PASSES):
        if pid is not None and pid > 0:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception:
                pass
        if exe_name:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/IM", exe_name],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception:
                pass
        time.sleep(0.1)


def run_wrapper(
    state_file: Path,
    command: list[str],
    cwd: Path | None = None,
    env_file: Path | None = None,
) -> int:
    stop_file = state_file.with_suffix(state_file.suffix + ".stop")
    started_at = time.time()
    session_id = _current_session_id()

    state: dict[str, Any] = {
        "wrapper_pid": os.getpid(),
        "target_pid": None,
        "session_id": session_id,
        "command": command,
        "cwd": str(cwd) if cwd else None,
        "status": "starting",
        "returncode": None,
        "started_at": started_at,
        "updated_at": started_at,
        "ended_at": None,
        "error": None,
    }
    _write_state_atomic(state_file, state)

    env = os.environ.copy()
    if env_file and env_file.is_file():
        try:
            extra_env = json.loads(env_file.read_text(encoding="utf-8"))
            if isinstance(extra_env, dict):
                for k, v in extra_env.items():
                    env[str(k)] = str(v)
        except Exception:
            pass

    try:
        proc = subprocess.Popen(
            command,
            cwd=str(cwd) if cwd else None,
            env=env,
            stdin=subprocess.DEVNULL,
            # pythonw 没有标准流，不能让子进程继承无效句柄并在退出刷新时失败。
            stdout=None if sys.stdout is not None else subprocess.DEVNULL,
            stderr=None if sys.stderr is not None else subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        now = time.time()
        state.update(
            {
                "status": "error",
                "returncode": -1,
                "updated_at": now,
                "ended_at": now,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        _write_state_atomic(state_file, state)
        return 1

    state["target_pid"] = proc.pid
    state["status"] = "running"
    state["updated_at"] = time.time()
    _write_state_atomic(state_file, state)

    try:
        while True:
            ret = proc.poll()
            if ret is not None:
                now = time.time()
                state.update(
                    {
                        "status": "exited",
                        "returncode": int(ret),
                        "updated_at": now,
                        "ended_at": now,
                    }
                )
                _write_state_atomic(state_file, state)
                return int(ret)

            if stop_file.exists():
                force_kill_tree_three_times(proc.pid)
                try:
                    ret = proc.wait(timeout=3)
                except Exception:
                    ret = -9
                now = time.time()
                state.update(
                    {
                        "status": "killed",
                        "returncode": int(ret) if ret is not None else -9,
                        "updated_at": now,
                        "ended_at": now,
                    }
                )
                _write_state_atomic(state_file, state)
                try:
                    stop_file.unlink(missing_ok=True)
                except OSError:
                    pass
                return state["returncode"]

            now = time.time()
            if now - float(state["updated_at"]) >= 1.0:
                state["updated_at"] = now
                _write_state_atomic(state_file, state)

            time.sleep(0.2)
    except KeyboardInterrupt:
        force_kill_tree_three_times(proc.pid)
        now = time.time()
        state.update(
            {
                "status": "killed",
                "returncode": -9,
                "updated_at": now,
                "ended_at": now,
            }
        )
        _write_state_atomic(state_file, state)
        return -9


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AUTO-MAS Child Session Process Wrapper"
    )
    parser.add_argument("--state-file", required=True, help="JSON 状态输出文件路径")
    parser.add_argument("--cwd", default=None, help="工作目录")
    parser.add_argument("--env-file", default=None, help="附加环境变量 JSON 文件")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="待执行的命令及参数")

    args = parser.parse_args(argv)
    cmd = list(args.command)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        return 2

    state_path = Path(args.state_file).resolve()
    cwd_path = Path(args.cwd).resolve() if args.cwd else None
    env_path = Path(args.env_file).resolve() if args.env_file else None
    return run_wrapper(state_path, cmd, cwd=cwd_path, env_file=env_path)


if __name__ == "__main__":
    raise SystemExit(main())
