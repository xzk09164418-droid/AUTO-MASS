"""邮箱控制生命周期：串行处理指令及可重试回执，业务仍由占用服务执行。"""

import asyncio

from app.core.external_holds import external_holds
from app.models.schema import ExternalHoldEnvelopeIn
from app.services.external_control_mail import read_commands, send_receipt
from app.utils import dpapi_decrypt, get_logger

logger = get_logger("外部控制邮箱")


async def run_mail_control(script_exists) -> None:
    """默认关闭；网络 I/O 在线程执行，异常退避且保留日志，不影响调度主循环。

    邮件 UID 与回执入队同一事务保存。SMTP 没有恰好一次交付保证：发送成功而
    落盘前崩溃可能重发同一 requestId 的回执，但绝不会重复执行占用操作。
    """
    delay = 5
    while True:
        try:
            settings, cursor = await external_holds.mail_context()
            if settings["enabled"]:
                account = settings["email"]
                password = dpapi_decrypt(settings["authorizationCode"])
                position, commands = await asyncio.to_thread(
                    read_commands, account, password, cursor
                )
                if not await external_holds.mail_checkpoint(position):
                    continue
                for uid, envelope in commands:
                    result = None
                    if envelope is not None:
                        try:
                            result = await external_holds.execute(
                                ExternalHoldEnvelopeIn.model_validate(envelope),
                                script_exists=script_exists,
                                mailbox=account,
                            )
                        except ValueError:
                            # 不记录校验异常文本：Pydantic 可能把敏感原始输入附在错误里。
                            logger.warning(f"拒绝无效邮箱指令: UID={uid}")
                            result = {
                                "code": 400,
                                "status": "error",
                                "message": "指令格式、签名或有效期校验失败",
                            }
                    position["uid"] = uid
                    if not await external_holds.mail_checkpoint(position, result):
                        break
                for key, result in (
                    await external_holds.mail_receipts(account)
                ).items():
                    await asyncio.to_thread(send_receipt, account, password, result)
                    await external_holds.mail_receipt_sent(key)
                external_holds.mail_error = ""
            delay = 5
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # 网络异常可能包含服务器原文；只记录异常类型，不附加账号授权信息。
            external_holds.mail_error = f"邮箱连接或处理失败: {type(error).__name__}"
            logger.error(external_holds.mail_error)
            delay = min(300, delay * 2)
        await asyncio.sleep(delay)


async def test_mail_connection() -> None:
    """只验证登录及只读收件箱，不处理历史指令、不发邮件、不更改游标。"""
    settings, _ = await external_holds.mail_context()
    if not settings["email"] or not settings["authorizationCode"]:
        raise ValueError("请先保存邮箱和授权码")
    password = dpapi_decrypt(settings["authorizationCode"])
    await asyncio.to_thread(read_commands, settings["email"], password, {})
