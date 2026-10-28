"""QQ 邮箱传输层：只读收件、发送回执，不引用调度器。

收件使用 UID 与 BODY.PEEK，不能用 UNSEEN 作为游标：用户阅读邮件不应使指令
丢失，程序读取指令也不应改变用户邮箱状态。签名校验由统一应用服务完成。
"""

import imaplib
import json
import smtplib
import ssl
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses

COMMAND_SUBJECT = "[AUTO-MAS COMMAND v1]"
RECEIPT_SUBJECT = "[AUTO-MAS RECEIPT v1]"


def read_commands(
    account: str, password: str, cursor: dict
) -> tuple[dict, list[tuple[int, dict | None]]]:
    """返回当前邮箱位置与增量指令；首次连接或 UIDVALIDITY 改变只建立基线。"""
    with imaplib.IMAP4_SSL(
        "imap.qq.com", 993, ssl_context=ssl.create_default_context(), timeout=15
    ) as client:
        client.login(account, password)
        kind, _ = client.select("INBOX", readonly=True)
        if kind != "OK":
            raise RuntimeError("无法读取收件箱")
        validity = client.response("UIDVALIDITY")[1][0].decode()
        known = cursor.get("account") == account and cursor.get("validity") == validity
        criteria = f"UID {cursor.get('uid', 0) + 1}:*" if known else "ALL"
        kind, rows = client.uid("search", None, criteria)
        if kind != "OK":
            raise RuntimeError("无法读取邮件列表")
        uids = [int(uid) for uid in rows[0].split()]
        if cursor.get("account") != account or cursor.get("validity") != validity:
            return {
                "account": account,
                "validity": validity,
                "uid": max(uids, default=0),
            }, []
        messages = []
        for uid in [uid for uid in uids if uid > cursor.get("uid", 0)][:50]:
            kind, parts = client.uid("fetch", str(uid), "(BODY.PEEK[]<0.65537>)")
            if kind != "OK":
                raise RuntimeError("无法读取邮件内容")
            body = next((item[1] for item in parts if isinstance(item, tuple)), b"")
            command = None
            if len(body) <= 65536:
                message = BytesParser(policy=policy.default).parsebytes(body)
                senders = [
                    addr.lower()
                    for _, addr in getaddresses(message.get_all("From", []))
                ]
                recipients = [
                    addr.lower() for _, addr in getaddresses(message.get_all("To", []))
                ]
                if (
                    str(message.get("Subject", "")) == COMMAND_SUBJECT
                    and senders == [account.lower()]
                    and account.lower() in recipients
                ):
                    part = message.get_body(preferencelist=("plain",))
                    try:
                        command = (
                            json.loads(part.get_content())
                            if part
                            else {"invalid": True}
                        )
                    except (ValueError, UnicodeError):
                        command = {"invalid": True}
            messages.append((uid, command))
        return dict(cursor), messages


def send_receipt(account: str, password: str, result: dict) -> None:
    """回执永远发往配置账号，不使用邮件正文提供的地址，避免形成转发器。"""
    message = EmailMessage()
    message["From"] = account
    message["To"] = account
    message["Subject"] = RECEIPT_SUBJECT
    message.set_content(json.dumps(result, ensure_ascii=False, indent=2))
    with smtplib.SMTP_SSL(
        "smtp.qq.com", 465, timeout=15, context=ssl.create_default_context()
    ) as client:
        client.login(account, password)
        client.send_message(message)
