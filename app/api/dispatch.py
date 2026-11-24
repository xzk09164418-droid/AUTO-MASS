#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2024-2025 DLmaster361
#   Copyright © 2025 MoeSnowyFox
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


from typing import Any

from fastapi import APIRouter, Body
from pydantic import Field

from app.api.external_holds import router as external_holds_router
from app.core import Config, TaskManager
from app.core.hotkey_manager import HotkeyManager
from app.models.schema import *
from app.services import System
from app.utils import get_logger

router = APIRouter(prefix="/api/dispatch", tags=["任务调度"])
logger = get_logger("任务调度 API")


router.include_router(external_holds_router)


class NavigationActionOut(OutBase):
    data: dict[str, Any] = Field(
        default_factory=dict, description="启停或上下任务切换结果"
    )


@router.get(
    "/runtime-snapshot",
    tags=["Get"],
    summary="获取运行中任务初始快照",
    response_model=TaskRuntimeSnapshot,
    status_code=200,
)
async def get_task_runtime_snapshot(includeLogs: bool = True) -> TaskRuntimeSnapshot:
    """返回当前运行任务；WS 只承载后续状态、日志与完成事件。"""

    return TaskManager.get_runtime_snapshot(include_logs=includeLogs)


@router.get(
    "/task/{task_id}",
    tags=["Get"],
    summary="按 taskId 查询单个任务状态",
    response_model=TaskStatusOut,
    status_code=200,
)
async def get_task_status(task_id: str) -> TaskStatusOut:
    """返回运行中或最近完成任务的终态；不包含日志。"""

    result = TaskManager.get_task_status(task_id)
    if result is None:
        return TaskStatusOut(
            code=404,
            status="error",
            message=f"任务 {task_id} 既不在运行中, 也不在最近完成的记录里",
            taskId=task_id,
        )
    return result


@router.get(
    "/power/countdown-snapshot",
    tags=["Get"],
    summary="获取电源倒计时初始快照",
    response_model=PowerCountdownSnapshot,
    status_code=200,
)
async def get_power_countdown_snapshot() -> PowerCountdownSnapshot:
    """返回当前倒计时；WS 只承载后续逐秒更新与取消事件。"""

    return System.get_power_countdown_snapshot()


@router.post(
    "/start",
    tags=["Action"],
    summary="添加任务",
    response_model=TaskCreateOut,
    status_code=200,
)
async def add_task(task: TaskCreateIn = Body(...)) -> TaskCreateOut:

    try:
        task_id = await TaskManager.add_task(
            mode=task.mode,
            id=task.taskId,
            resume_from_script_id=task.resumeFromScriptId,
            user_id=task.userId,
            user_ids=task.userIds,
            queue_user_ids=task.queueUserIds,
            view_only=task.viewOnly,
            instance_idx=task.instanceIdx,
        )
    except Exception as e:
        logger.opt(exception=True).warning(f"add_task失败: {type(e).__name__}: {e}")
        return TaskCreateOut(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}", taskId=""
        )
    return TaskCreateOut(taskId=str(task_id))


@router.post(
    "/stop",
    tags=["Action"],
    summary="中止任务",
    response_model=OutBase,
    status_code=200,
)
async def stop_task(task: DispatchIn = Body(...)) -> OutBase:

    try:
        await TaskManager.stop_task(task.taskId)
    except Exception as e:
        logger.opt(exception=True).warning(f"stop_task失败: {type(e).__name__}: {e}")
        return OutBase(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )
    return OutBase()


@router.post(
    "/navigation/toggle",
    tags=["Action"],
    summary="控制程序启停（与全局启停热键同源）",
    response_model=NavigationActionOut,
    status_code=200,
)
async def toggle_start_stop() -> NavigationActionOut:
    try:
        data = await TaskManager.toggle_start_stop()
        await HotkeyManager.notify_result(data)
        return NavigationActionOut(data=data)
    except Exception as e:
        logger.opt(exception=True).warning(f"toggle_start_stop失败: {e}")
        await HotkeyManager.notify_result({"message": str(e)}, failed=True)
        return NavigationActionOut(
            code=500, status="error", message=f"{type(e).__name__}: {e}"
        )


@router.post(
    "/navigation/previous",
    tags=["Action"],
    summary="切换到上一个任务（与全局上一任务热键同源）",
    response_model=NavigationActionOut,
    status_code=200,
)
async def navigate_previous_task() -> NavigationActionOut:
    try:
        data = await TaskManager.navigate_task(-1)
        await HotkeyManager.notify_result(data)
        return NavigationActionOut(data=data)
    except Exception as e:
        logger.opt(exception=True).warning(f"navigate_previous_task失败: {e}")
        await HotkeyManager.notify_result({"message": str(e)}, failed=True)
        return NavigationActionOut(
            code=500, status="error", message=f"{type(e).__name__}: {e}"
        )


@router.post(
    "/navigation/next",
    tags=["Action"],
    summary="切换到下一个任务（与全局下一任务热键同源）",
    response_model=NavigationActionOut,
    status_code=200,
)
async def navigate_next_task() -> NavigationActionOut:
    try:
        data = await TaskManager.navigate_task(1)
        await HotkeyManager.notify_result(data)
        return NavigationActionOut(data=data)
    except Exception as e:
        logger.opt(exception=True).warning(f"navigate_next_task失败: {e}")
        await HotkeyManager.notify_result({"message": str(e)}, failed=True)
        return NavigationActionOut(
            code=500, status="error", message=f"{type(e).__name__}: {e}"
        )


@router.get(
    "/navigation/state", response_model=NavigationActionOut, include_in_schema=False
)
async def queue_control_state() -> NavigationActionOut:
    return NavigationActionOut(data=TaskManager.control_snapshot())


@router.post(
    "/navigation/control", response_model=NavigationActionOut, include_in_schema=False
)
async def queue_control_action(payload: QueueControlIn) -> NavigationActionOut:
    try:
        if payload.action == "select":
            result = TaskManager.select_controlled_queue(payload.queueId)
        elif payload.action in ("resume", "previous", "next"):
            result = TaskManager.control_running_queue(payload.taskId, payload.action)
        else:
            result = await TaskManager.control_prompt(
                payload.taskId, payload.token, payload.action
            )
        await HotkeyManager.notify_result(result)
        return NavigationActionOut(data=result)
    except (ValueError, RuntimeError) as error:
        return NavigationActionOut(code=400, status="error", message=str(error))


@router.post(
    "/hotkey/capture", response_model=NavigationActionOut, include_in_schema=False
)
async def capture_hotkey(payload: HotkeyCaptureIn = Body(...)) -> NavigationActionOut:
    from app.core.hotkey_capture import begin_capture, end_capture

    try:
        if payload.action == "begin":
            token = await begin_capture(HotkeyManager)
            return NavigationActionOut(data={"token": token})
        if payload.action == "end" and payload.token:
            await end_capture(HotkeyManager, payload.token)
            return NavigationActionOut()
        raise ValueError("无效的热键录制操作")
    except Exception as error:
        return NavigationActionOut(code=500, status="error", message=str(error))


@router.post(
    "/hotkey/reload",
    tags=["Action"],
    summary="重新加载全局热键绑定",
    response_model=NavigationActionOut,
    status_code=200,
)
async def reload_hotkeys() -> NavigationActionOut:
    try:
        await HotkeyManager.reload()
        return NavigationActionOut(data={"bindings": HotkeyManager.registered_bindings})
    except Exception as e:
        return NavigationActionOut(
            code=500, status="error", message=f"{type(e).__name__}: {e}"
        )


@router.post(
    "/get/power",
    tags=["Get"],
    summary="获取电源标志",
    response_model=PowerOut,
    status_code=200,
)
async def get_power() -> PowerOut:

    try:
        signal = System.current_power_operation or Config.power_sign
    except Exception as e:
        logger.opt(exception=True).warning(f"get_power失败: {type(e).__name__}: {e}")
        return PowerOut(
            code=500,
            status="error",
            message=f"{type(e).__name__}: {str(e)}",
            signal="NoAction",
        )
    return PowerOut(signal=signal)


@router.post(
    "/set/power",
    tags=["Action"],
    summary="设置电源标志",
    response_model=OutBase,
    status_code=200,
)
async def set_power(task: PowerIn = Body(...)) -> OutBase:

    try:
        Config.power_sign = task.signal
        Config.power_delay = 0
        await System.cancel_pending_power_task()
    except Exception as e:
        logger.opt(exception=True).warning(f"set_power失败: {type(e).__name__}: {e}")
        return OutBase(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )
    return OutBase()


@router.post(
    "/cancel/power",
    tags=["Action"],
    summary="取消电源任务",
    response_model=OutBase,
    status_code=200,
)
async def cancel_power_task() -> OutBase:

    try:
        await System.cancel_power_task()
    except Exception as e:
        logger.opt(exception=True).warning(
            f"cancel_power_task失败: {type(e).__name__}: {e}"
        )
        return OutBase(
            code=500, status="error", message=f"{type(e).__name__}: {str(e)}"
        )
    return OutBase()
