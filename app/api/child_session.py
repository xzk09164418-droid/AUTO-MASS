"""本地远程桌面（Child Session）控制与外部程序借用/回传 HTTP API 路由。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from app.core.child_session import ChildSessionManager
from app.models.schema import OutBase
from app.utils import get_logger

router = APIRouter(prefix="/api/child-session", tags=["本地远程桌面"])
logger = get_logger("远程桌面 API")


class ChildSessionStatusOut(OutBase):
    data: dict[str, Any] = Field(default_factory=dict, description="远程桌面与租约状态")


class ChildSessionLeaseAcquireIn(BaseModel):
    caller: str = Field(default="external_program", description="申请使用远程桌面的外部程序标识")
    disconnectRdpView: bool = Field(
        default=True,
        description="是否在让渡期间断开 AUTO-MAS 宿主自身的 RDP 预览连接（以便外部程序连接 Child Session）",
    )
    timeoutSeconds: float = Field(
        default=3600.0,
        ge=1.0,
        le=86400.0,
        description="租约最长保护时间（秒），防止外部程序崩溃未回传导致永久挂起",
    )
    waitForGrant: bool = Field(
        default=False,
        description="是否阻塞等待至当前正在运行的子任务结束并完成让渡后再返回",
    )
    waitTimeout: float = Field(
        default=300.0,
        ge=1.0,
        le=7200.0,
        description="当 waitForGrant=True 时的最大等待秒数",
    )


class ChildSessionLeaseAcquireOut(OutBase):
    leaseId: str = Field(default="", description="租约唯一 ID，供停止使用时回传")
    leaseStatus: str = Field(default="", description="pending（等待当前子任务结束）或 granted（已获准使用）")
    childSessionId: Optional[int] = Field(default=None, description="当前 Child Session ID")
    lease: dict[str, Any] = Field(default_factory=dict, description="完整租约信息")


class ChildSessionLeaseReleaseIn(BaseModel):
    leaseId: Optional[str] = Field(default=None, description="要释放的租约 ID")
    caller: Optional[str] = Field(default=None, description="按外部程序名称释放全部关联租约")


class ChildSessionLeaseReleaseOut(OutBase):
    releasedLeaseIds: list[str] = Field(default_factory=list, description="已释放的租约 ID 列表")
    remainingLeases: list[dict[str, Any]] = Field(default_factory=list, description="剩余活跃租约")


class ChildSessionWindowControlIn(BaseModel):
    visible: Optional[bool] = Field(default=None, description="显示或隐藏远程桌面窗口")
    watchMode: Optional[bool] = Field(default=None, description="观看模式（屏蔽本机键鼠输入进入分身）")
    smartSizing: Optional[bool] = Field(default=None, description="画面自适应窗口缩放")
    topmost: Optional[bool] = Field(default=None, description="窗口置顶")
    shortcut: Optional[str] = Field(default=None, description="向远程桌面发送组合键，如 Win+D 或 Win+Tab")


@router.get(
    "/status",
    summary="查询本地远程桌面状态及外部程序借用情况",
    response_model=ChildSessionStatusOut,
)
async def get_child_session_status() -> ChildSessionStatusOut:
    status = await ChildSessionManager.get_status()
    return ChildSessionStatusOut(data=status)


@router.post(
    "/acquire",
    summary="外部程序申请使用本地远程桌面（队列将在相邻子任务间隔让渡桌面）",
    response_model=ChildSessionLeaseAcquireOut,
)
@router.post(
    "/request",
    summary="外部程序申请使用本地远程桌面（别名接口）",
    response_model=ChildSessionLeaseAcquireOut,
)
async def acquire_child_session_lease(
    body: ChildSessionLeaseAcquireIn = Body(...),
) -> ChildSessionLeaseAcquireOut:
    try:
        lease = await ChildSessionManager.acquire_external_lease(
            body.caller,
            disconnect_rdp_view=body.disconnectRdpView,
            timeout_seconds=body.timeoutSeconds,
            wait_for_grant=body.waitForGrant,
            wait_timeout=body.waitTimeout,
        )
        sid = ChildSessionManager.wts_get_child_session_id()
        return ChildSessionLeaseAcquireOut(
            leaseId=lease.lease_id,
            leaseStatus=lease.status,
            childSessionId=sid,
            lease=lease.to_dict(),
        )
    except Exception as exc:
        logger.opt(exception=True).warning(f"申请远程桌面租约失败: {exc}")
        return ChildSessionLeaseAcquireOut(
            code=500,
            status="error",
            message=f"{type(exc).__name__}: {exc}",
        )


@router.post(
    "/release",
    summary="外部程序停止使用本地远程桌面后的回传接口（恢复 AUTO-MAS 队列执行）",
    response_model=ChildSessionLeaseReleaseOut,
)
@router.post(
    "/callback",
    summary="外部程序停止使用本地远程桌面后的回传接口（别名）",
    response_model=ChildSessionLeaseReleaseOut,
)
async def release_child_session_lease(
    body: ChildSessionLeaseReleaseIn = Body(...),
) -> ChildSessionLeaseReleaseOut:
    try:
        released = await ChildSessionManager.release_external_lease(
            lease_id=body.leaseId,
            caller=body.caller,
        )
        return ChildSessionLeaseReleaseOut(
            releasedLeaseIds=released,
            remainingLeases=ChildSessionManager.list_leases(),
        )
    except Exception as exc:
        logger.opt(exception=True).warning(f"回传释放远程桌面租约失败: {exc}")
        return ChildSessionLeaseReleaseOut(
            code=500,
            status="error",
            message=f"{type(exc).__name__}: {exc}",
        )


@router.post(
    "/connect",
    summary="立即建立或重连常驻本地远程桌面连接",
    response_model=ChildSessionStatusOut,
)
async def connect_child_session() -> ChildSessionStatusOut:
    try:
        await ChildSessionManager.ensure_connected()
        return ChildSessionStatusOut(data=await ChildSessionManager.get_status())
    except Exception as exc:
        return ChildSessionStatusOut(
            code=500, status="error", message=f"{type(exc).__name__}: {exc}"
        )


@router.post(
    "/window",
    summary="控制本地远程桌面窗口（显示/隐藏/观看模式/缩放/置顶/快捷键）",
    response_model=ChildSessionStatusOut,
)
async def control_child_session_window(
    body: ChildSessionWindowControlIn = Body(...),
) -> ChildSessionStatusOut:
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    if payload.get("visible") is True:
        await ChildSessionManager.ensure_host_running(force_visible=True)
    await ChildSessionManager._http_call("/window", method="POST", payload=payload, timeout=5.0)
    return ChildSessionStatusOut(data=await ChildSessionManager.get_status())


@router.post(
    "/logoff",
    summary="断开并注销本地远程桌面会话",
    response_model=OutBase,
)
async def logoff_child_session() -> OutBase:
    resp = await ChildSessionManager._http_call("/logoff", method="POST", payload={}, timeout=15.0)
    if resp is None:
        ChildSessionManager.wts_terminate_child_session(wait=True)
    return OutBase()
