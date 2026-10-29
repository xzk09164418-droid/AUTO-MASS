"""外部控制 HTTP 适配层；所有调度和持久化规则交给应用服务。"""

import ipaddress
import uuid
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core import Config
from app.core.external_holds import external_holds
from app.models.schema import (
    ExternalControlContractOut,
    ExternalControlSettingsIn,
    ExternalControlSnapshotOut,
    ExternalHoldEnvelopeIn,
    ExternalHoldForceReleaseIn,
    ExternalHoldOut,
    OutBase,
)
from app.utils import get_logger

logger = get_logger("外部控制 API")


def require_local(request: Request) -> None:
    """不信任转发头；同时阻止远程网页借助本机浏览器提交管理操作。"""
    try:
        if (
            not request.client
            or not ipaddress.ip_address(request.client.host).is_loopback
        ):
            raise ValueError
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).hostname not in (
            "127.0.0.1",
            "localhost",
            "::1",
        ):
            raise ValueError
    except ValueError:
        raise HTTPException(
            status_code=403, detail="外部控制接口仅接受本机调用"
        ) from None


router = APIRouter(
    prefix="/external-holds", tags=[], dependencies=[Depends(require_local)]
)


def script_exists(script_id: str) -> bool:
    return uuid.UUID(script_id) in Config.ScriptConfig


async def execute_command(body: ExternalHoldEnvelopeIn, action: str) -> ExternalHoldOut:
    try:
        return ExternalHoldOut(
            **await external_holds.execute(
                body, action=action, script_exists=script_exists
            )
        )
    except ValueError as error:
        logger.warning("外部指令被拒绝")
        return ExternalHoldOut(code=400, status="error", message=str(error))
    except Exception as error:
        logger.error(f"外部指令处理失败: {type(error).__name__}")
        return ExternalHoldOut(
            code=500, status="error", message="外部指令处理失败，请查看日志"
        )


@router.post("/acquire", response_model=ExternalHoldOut, summary="申请脚本外部占用")
async def acquire_external_hold(body: ExternalHoldEnvelopeIn) -> ExternalHoldOut:
    return await execute_command(body, "acquire")


@router.post("/release", response_model=ExternalHoldOut, summary="释放自己的脚本占用")
async def release_external_hold(body: ExternalHoldEnvelopeIn) -> ExternalHoldOut:
    return await execute_command(body, "release")


@router.post("/status", response_model=ExternalHoldOut, summary="查询自己的脚本占用")
async def get_external_hold_status(body: ExternalHoldEnvelopeIn) -> ExternalHoldOut:
    return await execute_command(body, "status")


@router.get(
    "/management",
    response_model=ExternalControlSnapshotOut,
    summary="本机外部控制设置与状态",
)
async def get_external_control_snapshot() -> ExternalControlSnapshotOut:
    return ExternalControlSnapshotOut(**await external_holds.snapshot())


@router.post("/settings", response_model=OutBase, summary="保存本机邮箱与调用方设置")
async def save_external_control_settings(body: ExternalControlSettingsIn) -> OutBase:
    try:
        await external_holds.save_settings(body)
        return OutBase()
    except ValueError as error:
        return OutBase(code=400, status="error", message=str(error))


@router.post("/force-release", response_model=OutBase, summary="用户手动解除占用")
async def force_release_external_hold(body: ExternalHoldForceReleaseIn) -> OutBase:
    await external_holds.force_release(body.callerId, body.holdId)
    return OutBase()


@router.get(
    "/contract",
    response_model=ExternalControlContractOut,
    summary="当前外部控制字段说明",
)
async def get_external_control_contract(request: Request) -> ExternalControlContractOut:
    # 与接口校验使用同一模型，字段默认值/范围变更会自动同步到页面。
    from app.api.child_session import (
        ChildSessionLeaseAcquireIn,
        ChildSessionLeaseReleaseIn,
    )
    from app.models.schema import ExternalHoldCommandIn

    return ExternalControlContractOut(
        backendUrl=f"http://127.0.0.1:{request.scope['server'][1]}",
        schemas={
            model.__name__: model.model_json_schema()
            for model in (
                ChildSessionLeaseAcquireIn,
                ChildSessionLeaseReleaseIn,
                ExternalHoldCommandIn,
                ExternalHoldEnvelopeIn,
            )
        },
    )


@router.post("/mail-test", response_model=OutBase, summary="验证 QQ 邮箱连接")
async def test_external_mail_connection() -> OutBase:
    from app.core.external_control_mail import test_mail_connection

    try:
        await test_mail_connection()
        return OutBase(message="邮箱连接成功；未处理历史邮件")
    except Exception as error:
        logger.error(f"邮箱连接测试失败: {type(error).__name__}")
        return OutBase(
            code=400,
            status="error",
            message="邮箱连接失败，请检查账号、授权码和 IMAP 服务",
        )
