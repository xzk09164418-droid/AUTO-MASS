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
    from app.core.desktop_recovery import RESUME_ENV, DesktopRecovery, rebuild_or_reboot

    # 桥接进程只加载全局设置，不启动定时器、不迁移脚本配置、不创建第二份任务队列。
    await Config.connect(Config.config_path / "Config.json")
    if not ChildSessionManager.enabled:
        return None
    # 登录任务也会被子会话登录触发；只有主桌面的桥接进程可以创建后端。
    existing_session = ChildSessionManager.wts_get_child_session_id()
    if existing_session is None:
        status = await ChildSessionManager._http_call("/status", timeout=2)
        if status is not None:
            existing_session = status.get("childSessionId")
    if actual_session == existing_session:
        logger.info("忽略子会话内重复触发的启动入口，等待主桌面启动任务后端")
        return 0
    store = DesktopRecovery.store
    control = store.initialize()
    if not (store.root / "tasks.json").exists() and control["phase"] == "idle":
        store.write("tasks.json", {"tasks": {}})
    # 暂停标记不能因启动器重启而丢失；人工恢复由独立管理命令显式执行。
    while control["phase"] == "paused":
        await asyncio.sleep(2)
        control = store.control()
    session_id = None
    for attempt in range(3):
        try:
            session_id = await ChildSessionManager.ensure_connected()
            if session_id is not None:
                break
        except Exception:
            await DesktopRecovery.notify(f"启动时连接远程桌面失败（{attempt + 1}/3）")
        if attempt < 2:
            await asyncio.sleep(5)
    while session_id is None:
        session_id = await rebuild_or_reboot(ChildSessionManager, store)
        if session_id is None:
            while store.control()["phase"] in {"paused", "reboot"}:
                await asyncio.sleep(2)
    if actual_session == session_id:
        logger.info("忽略子会话内未受监督的启动入口")
        return 0

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
        hotkeys = asyncio.create_task(run_hotkey_relay(http_port))
        while True:
            control = store.control()
            while control["phase"] == "paused":
                await asyncio.sleep(2)
                control = store.control()
            resuming = control["phase"] in {"resuming", "reboot", "recovering"}
            env[EXECUTION_SESSION_ENV] = str(session_id)
            env[RESUME_ENV] = "1" if resuming else "0"
            if resuming:
                control["phase"] = "resuming"
                store.write("control.json", control)
            (store.root / "request.json").unlink(missing_ok=True)
            process = await ChildSessionManager.launch_in_child_session(
                sys.executable,
                str(Path(__file__).resolve().parents[2] / "main.py"),
                *argv,
                cwd=Path.cwd(),
                env=env,
            )
            logger.info(f"主桌面监督任务后端，Session={session_id}，恢复={resuming}")
            failures = 0
            while True:
                request = (store.root / "request.json").exists()
                if process.returncode is not None and not request:
                    if process.returncode == 0 or not store.tasks():
                        return process.returncode
                    store.write("request.json", {"reason": "任务后端异常退出"})
                    await DesktopRecovery.notify("任务后端异常退出，准备从检查点恢复")
                    break
                if request:
                    break
                status = await ChildSessionManager._http_call("/status", timeout=2)
                healthy = (
                    status is not None
                    and status.get("childSessionId") == session_id
                    and (
                        status.get("connectedState") == 1
                        or bool(status.get("externalLeaseHolder"))
                    )
                )
                # 外部借用会主动断开画面，保留原会话时不触发故障恢复。
                failures = 0 if healthy else failures + 1
                if failures >= 3:
                    store.write(
                        "request.json", {"reason": "主桌面检测到执行会话或宿主失联"}
                    )
                    await DesktopRecovery.notify(
                        "主桌面检测到执行会话或宿主失联，准备恢复"
                    )
                    break
                await asyncio.sleep(2)
            # 后端检测到 request 后冻结检查点并停任务；即使它已失联也由主桌面继续监督。
            await asyncio.sleep(2)
            replacement = await rebuild_or_reboot(ChildSessionManager, store)
            while replacement is None:
                # 不清理宿主或再次弹倒计时，等待明确的人工恢复命令。
                while store.control()["phase"] in {"paused", "reboot"}:
                    await asyncio.sleep(2)
                replacement = await rebuild_or_reboot(ChildSessionManager, store)
            if replacement is None:
                raise RuntimeError("恢复后未获得有效子会话")
            # 注销后包装器无法再更新退出文件，不等待旧文件变成 exited。
            process.state_file.with_name(f"job_{process.job_id}.env.json").unlink(
                missing_ok=True
            )
            process = None
            session_id = replacement
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
    from app.core.child_session import ChildSessionManager
    from app.core.desktop_recovery import DesktopRecovery
    from app.utils.platform.windows.session import EXECUTION_SESSION_ENV

    expected = os.environ.get(EXECUTION_SESSION_ENV)
    if expected is None:
        return
    parent_pid = os.environ.get(PARENT_PID_ENV)
    failures = 0
    while True:
        reason = None
        try:
            await ChildSessionManager.maintain_external_leases()
        except Exception:
            logger.exception("维护外部桌面租约失败")
        if (DesktopRecovery.store.root / "request.json").exists():
            await DesktopRecovery.request("主桌面已请求恢复执行环境")
            return
        if parent_pid is not None:
            try:
                parent = psutil.Process(int(parent_pid))
                # Windows/.NET 与 psutil 的 FILETIME 转换精度不同，仍核对 PID 与创建时间。
                if (
                    abs(parent.create_time() - float(os.environ[PARENT_TIME_ENV]))
                    > 0.001
                ):
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
            await DesktopRecovery.request(reason)
            return
        await asyncio.sleep(2)
