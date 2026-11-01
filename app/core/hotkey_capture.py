"""后端与主桌面之间的热键录制租约和注册确认。"""

import asyncio
import json
import os
import time
import uuid
from pathlib import Path

CAPTURE_FILE = Path("data/hotkey-capture.json")
RELAY_ACK = Path("data/hotkey-capture-relay.json")
RELAY_STATUS = Path("data/hotkey-relay-status.json")
_expiry_task: asyncio.Task | None = None
operation_lock = asyncio.Lock()


def report_relay(bindings: tuple, error: str | None) -> None:
    RELAY_STATUS.parent.mkdir(parents=True, exist_ok=True)
    temporary = RELAY_STATUS.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"bindings": bindings, "error": error, "at": time.time()}),
        encoding="utf-8",
    )
    temporary.replace(RELAY_STATUS)


async def wait_for_relay(bindings: tuple, since: float) -> None:
    if os.environ.get("AUTO_MAS_EXECUTION_SESSION_ID") is None:
        return
    for _ in range(60):
        try:
            status = json.loads(RELAY_STATUS.read_text(encoding="utf-8"))
            if status.get("at", 0) >= since and status.get("bindings") == list(
                bindings
            ):
                if status.get("error"):
                    raise RuntimeError(f"主桌面热键注册失败：{status['error']}")
                return
        except (OSError, ValueError):
            pass
        await asyncio.sleep(0.1)
    raise RuntimeError("主桌面未确认热键生效，请检查主桌面启动器是否运行")


def current_capture() -> dict:
    try:
        value = json.loads(CAPTURE_FILE.read_text(encoding="utf-8"))
        return value if value["expires"] > time.time() else {}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def acknowledge_capture(token: str) -> None:
    RELAY_ACK.parent.mkdir(parents=True, exist_ok=True)
    RELAY_ACK.write_text(json.dumps({"token": token}), encoding="utf-8")


async def begin_capture(manager) -> str:
    """先确认两个桌面都已暂停注册，再允许页面开始录制。"""
    global _expiry_task
    async with operation_lock:
        if current_capture():
            raise RuntimeError("另一个窗口正在录制热键，请结束后再试")
        token = uuid.uuid4().hex
        CAPTURE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CAPTURE_FILE.write_text(
            json.dumps({"token": token, "expires": time.time() + 35}), encoding="utf-8"
        )
        try:
            await manager.reload()
            if os.environ.get("AUTO_MAS_EXECUTION_SESSION_ID") is not None:
                for _ in range(50):
                    try:
                        ack = json.loads(RELAY_ACK.read_text(encoding="utf-8"))
                        if ack.get("token") == token:
                            break
                    except (OSError, ValueError):
                        pass
                    await asyncio.sleep(0.1)
                else:
                    raise RuntimeError("主桌面热键未确认暂停，本次不开始录制")
        except BaseException:
            CAPTURE_FILE.unlink(missing_ok=True)
            await manager.reload()
            raise
        if _expiry_task is not None:
            _expiry_task.cancel()
        _expiry_task = asyncio.create_task(_expire(manager, token))
        return token


async def _expire(manager, token: str) -> None:
    # 预留主桌面确认时间；页面的 25 秒录制期限始终早于租约到期。
    await asyncio.sleep(
        max(0, current_capture().get("expires", time.time()) - time.time())
    )
    try:
        await end_capture(manager, token)
    except Exception as error:
        await manager.notify_result({"message": f"恢复热键失败：{error}"}, failed=True)


async def end_capture(manager, token: str) -> None:
    async with operation_lock:
        try:
            value = json.loads(CAPTURE_FILE.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        if value.get("token") != token:
            raise RuntimeError("热键录制已过期，请重新录制")
        CAPTURE_FILE.unlink(missing_ok=True)
        await manager.reload()
