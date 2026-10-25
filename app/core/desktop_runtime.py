"""将整个任务后端放入同一个 RDP 子会话，主桌面仅保留宿主与启动桥接。"""

import asyncio
import os
import sys
from contextlib import suppress
from pathlib import Path

import psutil

from app.utils.logger import get_logger

logger = get_logger("桌面执行环境")
PARENT_PID_ENV = "AUTO_MAS_DESKTOP_PARENT_PID"
PARENT_TIME_ENV = "AUTO_MAS_DESKTOP_PARENT_TIME"


async def ensure_execution_session() -> None:
    """调度前确认后端仍在目标子桌面，运行中开启隔离需要重启后端。"""
    if os.name != "nt":
        return
    from app.core.child_session import ChildSessionManager
    from app.utils.platform.windows.session import (
        EXECUTION_SESSION_ENV,
        in_execution_session,
    )

    expected = os.environ.get(EXECUTION_SESSION_ENV)
    if expected is None and not ChildSessionManager.enabled:
        return
    if expected is None or not in_execution_session():
        raise RuntimeError("请重新启动主程序，将任务后端迁入 RDP 子桌面后再运行任务")
    session_id = await ChildSessionManager.ensure_connected()
    if session_id != int(expected):
        raise RuntimeError("RDP 执行会话已改变，请重新启动主程序")


async def relay_to_execution_session(argv: list[str], *, http_port: int) -> int | None:
    """主桌面启动后端并等待退出；已在目标会话或未启用时返回 None。"""
    if os.name != "nt":
        return None

    from app.utils.platform.windows.session import (
        EXECUTION_SESSION_ENV,
        get_process_session_id,
    )

    actual_session = get_process_session_id()
    expected = os.environ.get(EXECUTION_SESSION_ENV)
    if expected is not None:
        if actual_session != int(expected):
            raise RuntimeError(
                f"执行会话不匹配：期望 Session={expected}，实际 Session={actual_session}"
            )
        logger.info(
            f"窗口检测、识别、点击与程序启动统一在 Session={actual_session} 执行"
        )
        return None

    from app.core import Config
    from app.core.child_session import ChildSessionManager

    # 桥接进程只加载全局设置，不启动定时器、不迁移脚本配置、不创建第二份任务队列。
    await Config.connect(Config.config_path / "Config.json")
    if not ChildSessionManager.enabled:
        return None
    session_id = await ChildSessionManager.ensure_connected()
    if session_id is None:
        raise RuntimeError("无法建立 RDP 子桌面，已停止启动任务后端")
    if actual_session == session_id:
        os.environ[EXECUTION_SESSION_ENV] = str(session_id)
        return None

    # 计划任务继承宿主环境；显式传递运行时端口和开发模式等启动约定。
    env = {
        key: value
        for key, value in os.environ.items()
        if key.startswith(("AUTO_MAS_", "PYTHON"))
    }
    env.update(
        {
            EXECUTION_SESSION_ENV: str(session_id),
            PARENT_PID_ENV: str(os.getpid()),
            PARENT_TIME_ENV: str(psutil.Process().create_time()),
        }
    )
    from app.core.hotkey_relay import run_hotkey_relay

    process = None
    hotkeys = None
    try:
        process = await ChildSessionManager.launch_in_child_session(
            sys.executable,
            str(Path(__file__).resolve().parents[2] / "main.py"),
            *argv,
            cwd=Path.cwd(),
            env=env,
        )
        logger.info(f"主桌面仅保留启动桥接，任务后端位于 Session={session_id}")
        hotkeys = asyncio.create_task(run_hotkey_relay(http_port))
        return await process.wait()
    finally:
        if hotkeys is not None:
            hotkeys.cancel()
            with suppress(asyncio.CancelledError):
                await hotkeys
        if process is not None:
            if process.returncode is None:
                process.terminate()
                with suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(process.wait(), timeout=15)
            process.state_file.with_name(f"job_{process.job_id}.env.json").unlink(
                missing_ok=True
            )
        # 只回收本桥接创建的宿主，不关闭已在运行的共享宿主。
        if ChildSessionManager._host_process is not None:
            await ChildSessionManager.stop()


async def watch_execution_session() -> None:
    """桥接退出或目标会话丢失时停止后端，避免监督器强杀后留下第二份调度器。"""
    if os.name != "nt":
        return
    from app.core import Config
    from app.core.child_session import ChildSessionManager
    from app.utils.platform.windows.session import EXECUTION_SESSION_ENV

    expected = os.environ.get(EXECUTION_SESSION_ENV)
    if expected is None:
        return
    parent_pid = os.environ.get(PARENT_PID_ENV)
    failures = 0
    while True:
        reason = None
        if parent_pid is not None:
            try:
                parent = psutil.Process(int(parent_pid))
                # Windows/.NET 与 psutil 的 FILETIME 转换精度不同，仍核对 PID 与创建时间。
                if abs(parent.create_time() - float(os.environ[PARENT_TIME_ENV])) > 0.001:
                    reason = "主桌面启动桥接已退出"
            except (psutil.Error, KeyError, ValueError):
                reason = "主桌面启动桥接已退出"
        status = await ChildSessionManager._http_call("/status", timeout=2)
        failures = failures + 1 if status is None else 0
        if status is not None and status.get("childSessionId") != int(expected):
            reason = "RDP 执行会话已改变"
        elif failures >= 3:
            reason = "RDP 宿主已失联"
        if reason:
            logger.error(f"{reason}，停止任务后端，请重新启动主程序")
            if Config.server is not None:
                Config.server.should_exit = True
            return
        await asyncio.sleep(2)
