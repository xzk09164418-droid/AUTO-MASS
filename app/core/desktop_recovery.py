"""桌面恢复编排：后端记录进度，主桌面监督注销、重建及电源升级。"""

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from app.services.desktop_recovery_store import (
    DesktopRecoveryStore,
    RecoveryRecordError,
)
from app.utils import get_logger

logger = get_logger("桌面恢复")
RESUME_ENV = "AUTO_MAS_DESKTOP_RECOVERY"


class _DesktopRecovery:
    def __init__(self) -> None:
        self.frozen = False
        self.restoring = False
        self.startup_claimed = False

    @property
    def store(self) -> DesktopRecoveryStore:
        return DesktopRecoveryStore(Path.cwd())

    @property
    def enabled(self) -> bool:
        return os.name == "nt" and "AUTO_MAS_EXECUTION_SESSION_ID" in os.environ

    def admission(self, *, restoring: bool = False) -> None:
        if not self.enabled:
            return
        control = self.store.control()
        if self.frozen or (control["phase"] != "idle" and not restoring):
            raise RuntimeError("远程桌面恢复中或已暂停，暂不接受新的任务")

    def enroll(self, task_info: Any, *, previous_id: str | None = None) -> None:
        if not self.enabled or task_info.mode != "AutoProxy":
            return
        store = self.store
        if (store.root / "tasks.json").exists():
            tasks = store.tasks()
        else:
            tasks = {}
        entry = {
            "id": task_info.queue_id or task_info.script_id,
            "mode": "CycleRun" if task_info.is_cycle else "AutoProxy",
            "user_id": task_info.user_id,
            "user_ids": sorted(task_info.user_ids)
            if task_info.user_ids is not None
            else None,
            "queue_user_ids": {
                key: sorted(value)
                for key, value in task_info.user_ids_by_script.items()
            }
            if task_info.user_ids_by_script is not None
            else None,
        }
        if previous_id is not None:
            position = store.position(previous_id)
            if position:
                store.save_position(task_info.task_id, position)
            tasks.pop(previous_id, None)
        tasks[task_info.task_id] = entry
        # 首次身份清单必须写成功才允许开始；运行中检查点失败保留旧版本。
        store.write("tasks.json", {"tasks": tasks})

    def checkpoint(self, task_info: Any, script_id: str) -> None:
        if not self.enabled or self.frozen or task_info.mode != "AutoProxy":
            return
        try:
            self.store.save_position(task_info.task_id, script_id)
        except OSError:
            logger.exception("保存任务进度失败，将保留旧检查点")

    def finish(self, task_id: str, *, success: bool) -> None:
        if not self.enabled or self.frozen:
            return
        try:
            store = self.store
            tasks = store.tasks()
            tasks.pop(task_id, None)
            store.write("tasks.json", {"tasks": tasks})
            if not tasks and success and not self.restoring:
                control = store.control()
                if control["phase"] == "idle":
                    store.write("control.json", {"phase": "idle", "reboot_used": False})
        except (OSError, RecoveryRecordError):
            logger.exception("更新恢复队列记录失败")

    async def notify(self, message: str) -> None:
        logger.error(message)
        try:
            from app.core.notify import dispatch, global_target
            from app.core.notify_channels import initialize_notification_channels
            from app.models.notification import NotifyPayload

            initialize_notification_channels()
            result = await dispatch(
                NotifyPayload(title="AUTO-MAS 远程桌面异常", text=message),
                [global_target(include_system=True)],
            )
            if result.failed:
                logger.warning("远程桌面异常通知有渠道投递失败")
        except Exception:
            logger.exception("远程桌面异常通知发送失败")

    async def request(self, reason: str) -> None:
        if not self.enabled or self.frozen:
            return
        from app.core.config import Config
        from app.core.task_manager import TaskManager
        from app.runtime_tasks import RuntimeTasks

        for info in tuple(TaskManager.task_info.values()):
            if 0 <= info.current_index < len(info.script_list):
                self.checkpoint(info, info.script_list[info.current_index].script_id)
        self.frozen = True
        try:
            self.store.write("request.json", {"reason": reason})
        except OSError:
            # 主桌面还会独立监测宿主与后端，不把保存失败当成恢复成功。
            logger.exception("恢复请求落盘失败")
        await self.notify(reason)
        Config.power_sign = "NoAction"
        # 请求可能来自队列任务本身，不能在该任务中等待取消自己。
        RuntimeTasks.spawn(TaskManager.stop_task("ALL"), name="desktop-recovery-pause")

    async def restore(self) -> bool:
        """后台初始化完成后恢复一次；返回 True 时禁止额外启动默认队列。"""
        if not self.enabled:
            return False
        control = self.store.control()
        if control["phase"] == "paused":
            self.startup_claimed = True
            return True
        if os.environ.get(RESUME_ENV) != "1":
            return False
        if self.startup_claimed:
            return True
        self.startup_claimed = True
        self.restoring = True
        from app.core.task_manager import TaskManager

        try:
            tasks = self.store.tasks()
            for task_id, entry in tasks.items():
                await TaskManager.add_task(
                    entry["mode"],
                    entry["id"],
                    resume_from_script_id=self.store.position(task_id),
                    user_id=entry.get("user_id"),
                    user_ids=entry.get("user_ids"),
                    queue_user_ids=entry.get("queue_user_ids"),
                    desktop_recovery_task_id=task_id,
                    trigger_source="startup_task",
                )
            control["phase"] = "idle"
            self.store.write("control.json", control)
            return True
        except Exception:
            self.frozen = True
            control["phase"] = "paused"
            self.store.write("control.json", control)
            await TaskManager.stop_task("ALL")
            await self.notify("恢复任务清单不可用，已暂停；请检查队列配置与恢复记录")
            return True
        finally:
            self.restoring = False


DesktopRecovery = _DesktopRecovery()


async def guard_ready(root: Path) -> bool:
    """日常核实 UU；显式实机测试另须核实本轮 SYSTEM 回退保护。"""
    test_root = os.environ.get("AUTO_MAS_RECOVERY_TEST_ROOT")
    if test_root is not None:
        if not test_root.strip():
            return False
        root = Path(test_root)
    script = Path(__file__).resolve().parents[2] / "scripts" / "rdp-recovery-guard.ps1"
    process = await asyncio.create_subprocess_exec(
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-Action",
        "Status" if test_root is not None else "DailyStatus",
        "-Root",
        str(root),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=15)
        return process.returncode == 0 and json.loads(stdout).get("ready") is True
    except (ValueError, asyncio.TimeoutError):
        if process.returncode is None:
            process.kill()
            await process.wait()
        return False


async def confirm_reboot(root: Path) -> bool:
    process = await asyncio.create_subprocess_exec(
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(Path(__file__).resolve().parents[2] / "scripts" / "rdp-reboot-confirm.ps1"),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        return await asyncio.wait_for(process.wait(), timeout=75) == 0
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return False


async def rebuild_or_reboot(manager: Any, store: DesktopRecoveryStore) -> int | None:
    """在主桌面执行一次重建；失败才进入用户确认的电脑重启流程。"""
    control = store.control()
    root = store.root.parent.parent
    if not await guard_ready(root):
        control["phase"] = "paused"
        store.write("control.json", control)
        await DesktopRecovery.notify(
            "UU 远程服务或实机测试保护未就绪，已暂停注销和重启"
        )
        return None
    control["phase"] = "recovering"
    store.write("control.json", control)
    response = await manager._http_call(
        "/logoff", method="POST", payload={}, timeout=20
    )
    if response is None or response.get("ok") is not True:
        await asyncio.to_thread(manager.wts_terminate_child_session, True)
    if await asyncio.to_thread(manager.wts_get_child_session_id) is not None:
        control["phase"] = "paused"
        store.write("control.json", control)
        await DesktopRecovery.notify(
            "原执行会话未确认注销，已暂停，避免启动两份任务后端"
        )
        return None
    for attempt in range(3):
        try:
            session_id = await manager.ensure_connected()
            if session_id is not None:
                control["phase"] = "resuming"
                store.write("control.json", control)
                return session_id
        except Exception:
            await DesktopRecovery.notify(f"注销后重建远程桌面失败（{attempt + 1}/3）")
        if attempt < 2:
            await asyncio.sleep(5)
    if control["reboot_used"]:
        control["phase"] = "paused"
        store.write("control.json", control)
        await DesktopRecovery.notify(
            "同一故障已自动重启过电脑，停止自动恢复，等待人工处理"
        )
        return None
    if not await guard_ready(root) or not await confirm_reboot(root):
        control["phase"] = "paused"
        store.write("control.json", control)
        return None
    # 用户确认/倒计时结束后再次检查，不能使用弹窗前的旧保护状态。
    if not await guard_ready(root):
        control["phase"] = "paused"
        store.write("control.json", control)
        return None
    control.update(phase="reboot", reboot_used=True)
    store.write("control.json", control)
    # 此安全标记必须可靠落盘，否则无法满足“同一故障最多重启一次”。
    await asyncio.to_thread(manager.wts_terminate_child_session, True)
    process = await asyncio.create_subprocess_exec(
        "shutdown.exe",
        "/r",
        "/t",
        "0",
        "/d",
        "p:0:0",
        "/c",
        "AUTO-MAS 远程桌面恢复失败，重启后恢复队列",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if await process.wait() != 0:
        control["phase"] = "paused"
        store.write("control.json", control)
        await DesktopRecovery.notify("系统拒绝重启，恢复任务已暂停")
    return None
