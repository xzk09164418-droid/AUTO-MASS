"""外部程序调用示例（仅依赖 Python 标准库）。

密钥从 AUTO_MAS_CONTROL_SECRET 读取，QQ 授权码从 AUTO_MAS_QQ_AUTH 读取。
同一次占用的 acquire/status/release 必须使用相同 caller/script/hold，重试同一
封邮件应重发已经生成的信封，而不是重新生成时间和请求 ID。
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import smtplib
import ssl
import urllib.request
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage


def sign_command(command: dict, secret: str) -> dict[str, str]:
    """签名覆盖编码后的原文，接收端不重新序列化 JSON。"""
    payload = (
        base64.urlsafe_b64encode(json.dumps(command, ensure_ascii=False).encode())
        .decode()
        .rstrip("=")
    )
    return {
        "payload": payload,
        "signature": hmac.new(
            secret.encode(), payload.encode("ascii"), hashlib.sha256
        ).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["acquire", "release", "status"])
    parser.add_argument("--caller", required=True)
    parser.add_argument("--script", required=True, type=uuid.UUID)
    parser.add_argument("--hold", required=True)
    parser.add_argument("--ttl", type=int)
    parser.add_argument("--transport", choices=["http", "mail", "json"], default="json")
    parser.add_argument("--base", help="从本机与热键页面复制当前后端地址")
    parser.add_argument("--account", help="发给自己的 QQ 邮箱账号")
    args = parser.parse_args()
    if args.action == "acquire" and (args.ttl is None or not 1 <= args.ttl <= 86400):
        parser.error("acquire 必须指定 --ttl，范围 1 至 86400 秒")
    secret = os.environ.get("AUTO_MAS_CONTROL_SECRET", "")
    if len(secret) < 32:
        parser.error("请设置至少 32 字符的 AUTO_MAS_CONTROL_SECRET")
    command = {
        "version": 1,
        "requestId": str(uuid.uuid4()),
        "callerId": args.caller,
        "action": args.action,
        "scriptId": str(args.script),
        "holdId": args.hold,
        "issuedAt": datetime.now(timezone.utc).isoformat(),
    }
    if args.action == "acquire":
        command["ttlSeconds"] = args.ttl
    body = json.dumps(sign_command(command, secret))
    if args.transport == "json":
        print(body)
    elif args.transport == "http":
        if not args.base:
            parser.error("HTTP 调用必须指定 --base")
        request = urllib.request.Request(
            args.base.rstrip("/") + "/api/dispatch/external-holds/" + args.action,
            data=body.encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            print(response.read().decode())
    else:
        password = os.environ.get("AUTO_MAS_QQ_AUTH", "")
        if not args.account or not password:
            parser.error("邮件调用需要 --account 和 AUTO_MAS_QQ_AUTH")
        message = EmailMessage()
        message["From"] = message["To"] = args.account
        message["Subject"] = "[AUTO-MAS COMMAND v1]"
        message.set_content(body)
        with smtplib.SMTP_SSL(
            "smtp.qq.com", 465, context=ssl.create_default_context(), timeout=15
        ) as client:
            client.login(args.account, password)
            client.send_message(message)
        print("指令邮件已发送；收到 active 回执后才能使用项目。")


if __name__ == "__main__":
    main()
