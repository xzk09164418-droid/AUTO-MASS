"""外部占用应用服务：HTTP、邮箱和调度器共享唯一状态机。

不变量：占用提交与脚本准入必须持有同一把锁；持久化先于内存发布；只有最后
一个运行实例完成清理才能授予占用。外部停止使用专用异常，不得转化为用户取消
整个队列。此模块不读取脚本私有配置，也不承担邮件协议或页面呈现。
"""

import asyncio
import base64
import copy
import hashlib
import hmac
import json
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from app.core.external_hold_store import ExternalHoldStore
from app.models.schema import (
    ExternalControlSettingsIn,
    ExternalHoldCommandIn,
    ExternalHoldEnvelopeIn,
)
from app.utils import dpapi_decrypt, dpapi_encrypt, get_logger
from app.utils.platform.common.process_scope import (
    request_task_process_stop,
    task_process_stop_failed,
)

logger = get_logger("外部项目占用")
T = TypeVar("T")


class ExternalHoldDeferred(Exception):
    """本次项目应进入延后区；不是任务失败或整队取消。"""

    def __init__(self, *, interrupted: bool = False) -> None:
        self.interrupted = interrupted
        super().__init__("项目因外部占用延后")


class ExternalHolds:
    def __init__(self, path: Path = Path("data/external-holds.sqlite3")) -> None:
        self.store = ExternalHoldStore(path)
        self.lock = asyncio.Lock()
        self.changed = asyncio.Event()
        self.state: dict | None = None
        self.running: dict[str, dict[asyncio.Task, bool]] = {}
        self.mail_error = ""

    async def initialize(self) -> None:
        async with self.lock:
            if self.state is None:
                self.state = await asyncio.to_thread(self.store.load)
                # 旧进程不会跨本程序重启继续由本调度器管理；占用本身仍保留。
                candidate = copy.deepcopy(self.state)
                for hold in candidate["holds"].values():
                    if hold["state"] == "stopping":
                        hold["state"] = "failed"
                        hold["message"] = "程序重启，无法确认之前的停止结果；请重新申请"
                await self._commit(candidate)
            await self._expire()

    async def _commit(self, candidate: dict) -> None:
        """提交不可被外层取消打断，否则磁盘已成功、内存仍旧会破坏互斥。"""
        write = asyncio.create_task(asyncio.to_thread(self.store.save, candidate))
        cancelled = False
        while not write.done():
            try:
                await asyncio.shield(write)
            except asyncio.CancelledError:
                cancelled = True
        write.result()
        self.state = candidate
        self.changed.set()
        if cancelled:
            # 将取消推迟到下一个 await，让调用者先完成与提交配套的同步状态通知。
            asyncio.current_task().cancel()

    @staticmethod
    def _live(state: dict, script_id: str) -> list[dict]:
        return [
            h
            for h in state["holds"].values()
            if h["scriptId"] == script_id
            and h["state"] in ("active", "stopping", "failed")
        ]

    def _mark_ready(self, candidate: dict, script_id: str) -> None:
        if not self._live(candidate, script_id):
            candidate["sequence"] += 1
            candidate["released"][script_id] = candidate["sequence"]

    async def _expire(self) -> None:
        now = time.time()
        expired = [
            key
            for key, hold in self.state["holds"].items()
            if hold["state"] in ("active", "stopping", "failed")
            and hold["expiresAt"] <= now
        ]
        stalled = [
            key
            for key, hold in self.state["holds"].items()
            if hold["state"] == "stopping"
            and key not in expired
            and now - hold.get("stoppingAt", now) >= 60
        ]
        stale_requests = [
            key
            for key, value in self.state["requests"].items()
            if value.get("validUntil", 0) <= now
        ]
        if not expired and not stale_requests and not stalled:
            return
        candidate = copy.deepcopy(self.state)
        # 过了签名接受窗口的请求已经不能重放；清理查询去重记录，避免持续轮询
        # 让状态库无限增长。占用及释放墓碑不随查询记录一起删除。
        for key in stale_requests:
            candidate["requests"].pop(key, None)
        for key in stalled:
            candidate["holds"][key]["state"] = "failed"
            candidate["holds"][key]["message"] = (
                "停止超过 60 秒仍未完成清理，不能确认占用生效"
            )
        # 到期顺序而非字典插入顺序决定同一轮检测到的多个项目的恢复顺序。
        for key in sorted(
            expired, key=lambda key: candidate["holds"][key]["expiresAt"]
        ):
            hold = candidate["holds"][key]
            hold["state"] = "expired"
            self._mark_ready(candidate, hold["scriptId"])
        await self._commit(candidate)
        if stalled:
            logger.error(f"外部占用停止确认超时: {len(stalled)} 项")
        if expired:
            logger.info(f"外部占用到期: {len(expired)} 项")

    async def availability(
        self, script_ids: list[str]
    ) -> tuple[set[str], dict[str, int]]:
        await self.initialize()
        async with self.lock:
            await self._expire()
            return (
                {sid for sid in script_ids if self._live(self.state, sid)},
                dict(self.state["released"]),
            )

    async def wait_changed(self, script_ids: list[str]) -> None:
        """在锁内再次检查可等待的到期点，使用事件与到期定时器而非忙轮询。"""
        async with self.lock:
            await self._expire()
            if any(not self._live(self.state, sid) for sid in script_ids):
                return
            self.changed.clear()
            deadlines = [
                h["expiresAt"]
                for h in self.state["holds"].values()
                if h["state"] in ("active", "stopping", "failed")
            ]
            if not deadlines:
                return
            delay = max(0.001, min(deadlines) - time.time())
        try:
            await asyncio.wait_for(self.changed.wait(), timeout=delay)
        except TimeoutError:
            pass

    async def execute(
        self,
        envelope: ExternalHoldEnvelopeIn,
        *,
        action: str | None = None,
        script_exists: Callable[[str], bool],
        mailbox: str | None = None,
    ) -> dict:
        await self.initialize()
        try:
            raw = base64.b64decode(
                envelope.payload + "=" * (-len(envelope.payload) % 4),
                altchars=b"-_",
                validate=True,
            )
            command = ExternalHoldCommandIn.model_validate_json(raw)
            if any(
                ord(char) < 32 or ord(char) == 127
                for value in (command.callerId, command.holdId, command.requestId)
                for char in value
            ):
                raise ValueError("标识符不得包含控制字符")
            if str(uuid.UUID(command.scriptId)) != command.scriptId:
                raise ValueError("脚本 ID 必须使用规范 UUID")
        except (ValueError, UnicodeError):
            raise ValueError("指令格式无效") from None
        async with self.lock:
            await self._expire()
            if mailbox is not None and (
                not self.state["settings"]["enabled"]
                or self.state["settings"]["email"] != mailbox
            ):
                raise ValueError("邮箱控制已停用或账号已变更")
            encrypted = self.state["settings"]["callers"].get(command.callerId)
            if not encrypted:
                raise ValueError("调用方或签名无效")
            secret = dpapi_decrypt(encrypted)
            expected = hmac.new(
                secret.encode(), envelope.payload.encode("ascii"), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(expected, envelope.signature):
                raise ValueError("调用方或签名无效")
            if action and command.action != action:
                raise ValueError("接口与指令动作不一致")
            issued = command.issuedAt.timestamp()
            if not -60 <= time.time() - issued <= 300:
                raise ValueError("指令已过期或签发时间超前")
            key = json.dumps([command.callerId, command.holdId])
            request_key = json.dumps([command.callerId, command.requestId])
            digest = hashlib.sha256(raw).hexdigest()
            previous = self.state["requests"].get(request_key)
            if previous:
                if previous["digest"] != digest:
                    raise ValueError("请求 ID 已用于其他内容")
                return previous["result"]
            if command.action == "acquire" and not script_exists(command.scriptId):
                raise ValueError("脚本不存在")
            candidate = copy.deepcopy(self.state)
            hold = candidate["holds"].get(key)
            if hold and hold["scriptId"] != command.scriptId:
                raise ValueError("占用 ID 已用于其他脚本")
            if command.action == "acquire" and hold is None:
                if (
                    command.ttlSeconds is None
                    or issued + command.ttlSeconds <= time.time()
                ):
                    raise ValueError("申请必须指定尚未到期的有效期")
                hold = {
                    "holdId": command.holdId,
                    "callerId": command.callerId,
                    "scriptId": command.scriptId,
                    "expiresAt": issued + command.ttlSeconds,
                    "stoppingAt": time.time(),
                    "state": "stopping"
                    if self.running.get(command.scriptId)
                    else "active",
                    "message": "",
                }
                if any(
                    h["state"] == "failed"
                    for h in self._live(candidate, command.scriptId)
                ):
                    hold["state"] = "failed"
                    hold["message"] = (
                        "存在未解决的停止失败，请确认进程状态并手动解除旧占用"
                    )
                candidate["holds"][key] = hold
            elif command.action == "release":
                if hold is None:
                    # 释放墓碑防止同一占用 ID 的迟到申请重新建立占用。
                    hold = {
                        "holdId": command.holdId,
                        "callerId": command.callerId,
                        "scriptId": command.scriptId,
                        "expiresAt": issued,
                        "state": "released",
                        "message": "",
                    }
                    candidate["holds"][key] = hold
                elif hold["state"] in ("active", "stopping", "failed"):
                    hold["state"] = "released"
                    self._mark_ready(candidate, command.scriptId)
            result = {
                "code": 200,
                "status": "success",
                "message": "指令已处理",
                "requestId": command.requestId,
                "hold": copy.deepcopy(hold),
                "remainingHolds": len(self._live(candidate, command.scriptId)),
            }
            if hold and hold["state"] == "failed":
                result.update(code=500, status="error", message=hold["message"])
            candidate["requests"][request_key] = {
                "digest": digest,
                "result": result,
                "validUntil": issued + 300,
            }
            await self._commit(candidate)
            if command.action == "acquire" and hold and hold["state"] == "stopping":
                for child in self.running.get(command.scriptId, {}):
                    # 先标记原因，再取消；父队列只捕获这个原因，用户取消仍向上传播。
                    if not self.running[command.scriptId][child]:
                        self.running[command.scriptId][child] = True
                        request_task_process_stop(child)
                        child.cancel()
            logger.info(
                f"外部占用指令: {command.action}, 脚本={command.scriptId}, 调用方={command.callerId}"
            )
            return result

    async def run(self, script_id: str, start: Callable[[], asyncio.Task[T]]) -> T:
        """在准入锁内创建子任务，取消后等待子任务自身的完整清理链。

        start 必须同步返回任务，不能在登记前让出事件循环。不同父队列可能同时
        引用同一脚本，故运行登记按任务区分，最后一项结束后才授予外部占用。
        """
        await self.initialize()
        async with self.lock:
            await self._expire()
            if self._live(self.state, script_id):
                raise ExternalHoldDeferred
            child = start()
            self.running.setdefault(script_id, {})[child] = False
        deferred = False
        result: T
        try:
            result = await child
        except asyncio.CancelledError:
            current = asyncio.current_task()
            deferred = self.running[script_id][child] and not (
                current and current.cancelling()
            )
            if not deferred:
                raise
        finally:
            async with self.lock:
                self.running[script_id].pop(child)
                if task_process_stop_failed(child):
                    candidate = copy.deepcopy(self.state)
                    for hold in self._live(candidate, script_id):
                        hold["state"] = "failed"
                        hold["message"] = "项目进程清理失败，不能确认占用生效"
                    await self._commit(candidate)
                if not self.running[script_id]:
                    self.running.pop(script_id)
                    candidate = copy.deepcopy(self.state)
                    changed = False
                    for hold in self._live(candidate, script_id):
                        if hold["state"] == "stopping":
                            if task_process_stop_failed(child):
                                hold["state"] = "failed"
                                hold["message"] = "项目进程清理失败，不能确认占用生效"
                            else:
                                hold["state"] = "active"
                            changed = True
                    if changed:
                        await self._commit(candidate)
        if deferred:
            raise ExternalHoldDeferred(interrupted=True)
        return result

    async def snapshot(self) -> dict:
        await self.initialize()
        async with self.lock:
            await self._expire()
            settings = self.state["settings"]
            return {
                "settings": {
                    "enabled": settings["enabled"],
                    "email": settings["email"],
                    "hasAuthorizationCode": bool(settings["authorizationCode"]),
                    "callers": list(settings["callers"]),
                },
                "holds": copy.deepcopy(list(self.state["holds"].values())),
                "results": [
                    copy.deepcopy(r["result"])
                    for r in list(self.state["requests"].values())[-50:]
                ],
                "mailError": self.mail_error,
            }

    async def save_settings(self, settings: ExternalControlSettingsIn) -> None:
        await self.initialize()
        async with self.lock:
            candidate = copy.deepcopy(self.state)
            current = candidate["settings"]
            if settings.email and (
                "@" not in settings.email or any(c in settings.email for c in "\r\n")
            ):
                raise ValueError("邮箱地址无效")
            current.update(enabled=settings.enabled, email=settings.email.strip())
            if (
                settings.authorizationCode
                and settings.authorizationCode.get_secret_value()
            ):
                current["authorizationCode"] = dpapi_encrypt(
                    settings.authorizationCode.get_secret_value()
                )
            if settings.callerId:
                if settings.removeCaller:
                    current["callers"].pop(settings.callerId, None)
                elif settings.callerSecret:
                    secret = settings.callerSecret.get_secret_value()
                    if len(secret) < 32:
                        raise ValueError("调用方密钥至少需要 32 个字符")
                    current["callers"][settings.callerId] = dpapi_encrypt(secret)
            if settings.enabled and not (
                current["email"] and current["authorizationCode"]
            ):
                raise ValueError("请先配置邮箱和授权码")
            await self._commit(candidate)

    async def force_release(self, caller_id: str, hold_id: str) -> None:
        await self.initialize()
        async with self.lock:
            candidate = copy.deepcopy(self.state)
            hold = candidate["holds"].get(json.dumps([caller_id, hold_id]))
            if hold and hold["state"] in ("active", "stopping", "failed"):
                hold["state"] = "released"
                self._mark_ready(candidate, hold["scriptId"])
                await self._commit(candidate)
                logger.warning(f"用户手动解除外部占用: {hold['scriptId']}")

    async def mail_context(self) -> tuple[dict, dict]:
        """提供传输层所需的设置副本；密文只在邮箱协调器内解密。"""
        await self.initialize()
        async with self.lock:
            return copy.deepcopy(self.state["settings"]), copy.deepcopy(
                self.state["mail"]
            )

    async def mail_checkpoint(self, position: dict, result: dict | None = None) -> bool:
        """邮件游标与回执原子落盘；配置切换后丢弃旧连接的检查点。"""
        async with self.lock:
            settings = self.state["settings"]
            if not settings["enabled"] or settings["email"] != position["account"]:
                return False
            candidate = copy.deepcopy(self.state)
            candidate["mail"] = dict(position)
            if result is not None:
                key = f"{position['account']}:{position['validity']}:{position['uid']}"
                candidate["outbox"][key] = {
                    "account": position["account"],
                    "result": result,
                }
            await self._commit(candidate)
            return True

    async def mail_receipts(self, account: str) -> dict:
        """只返回已经可以确认结果的回执，停止过程中不发送成功通知。"""
        async with self.lock:
            await self._expire()
            pending = {}
            for key, entry in self.state["outbox"].items():
                if entry["account"] != account:
                    continue
                result = copy.deepcopy(entry["result"])
                hold = result.get("hold")
                if hold:
                    current = self.state["holds"].get(
                        json.dumps([hold["callerId"], hold["holdId"]])
                    )
                    if current and current["state"] == "stopping":
                        continue
                    if current:
                        result["hold"] = copy.deepcopy(current)
                        result["remainingHolds"] = len(
                            self._live(self.state, current["scriptId"])
                        )
                        if current["state"] == "failed":
                            result.update(
                                code=500, status="error", message=current["message"]
                            )
                pending[key] = result
            return pending

    async def mail_receipt_sent(self, key: str) -> None:
        async with self.lock:
            candidate = copy.deepcopy(self.state)
            candidate["outbox"].pop(key, None)
            await self._commit(candidate)


external_holds = ExternalHolds()
