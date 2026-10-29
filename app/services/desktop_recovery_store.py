"""桌面恢复记录；只保存 MAS 队列位置，不读取脚本内部执行状态。"""

import json
import os
import uuid
from pathlib import Path
from typing import Any


class RecoveryRecordError(RuntimeError):
    """记录缺失或损坏，不能据此执行电源动作。"""


class DesktopRecoveryStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve() / "data" / "desktop_recovery"

    def read(self, name: str) -> dict[str, Any]:
        try:
            value = json.loads((self.root / name).read_text(encoding="utf-8"))
            if not isinstance(value, dict) or value.get("version") != 1:
                raise ValueError("恢复记录版本不匹配")
            return value
        except (OSError, ValueError) as exc:
            raise RecoveryRecordError(f"恢复记录不可用: {name}") from exc

    def write(self, name: str, value: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        destination = self.root / name
        temporary = self.root / f".{uuid.uuid4().hex}.tmp"
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump({**value, "version": 1}, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

    def control(self) -> dict[str, Any]:
        value = self.read("control.json")
        if (
            value.get("phase")
            not in {"idle", "recovering", "resuming", "paused", "reboot"}
            or type(value.get("reboot_used")) is not bool
        ):
            raise RecoveryRecordError("防重复重启标记损坏")
        return value

    def initialize(self) -> dict[str, Any]:
        if not (self.root / "control.json").exists():
            # 有历史恢复资料却没有安全标记时，不能当作首次启动重置重启次数。
            if self.root.exists() and any(self.root.iterdir()):
                raise RecoveryRecordError("缺少防重复重启标记，请人工检查恢复目录")
            self.write("control.json", {"phase": "idle", "reboot_used": False})
        return self.control()

    def tasks(self) -> dict[str, dict[str, Any]]:
        value = self.read("tasks.json").get("tasks")
        if not isinstance(value, dict):
            raise RecoveryRecordError("恢复队列清单损坏")
        for key, entry in value.items():
            try:
                uuid.UUID(key)
                uuid.UUID(entry["id"])
                if entry["mode"] not in {"AutoProxy", "CycleRun"}:
                    raise ValueError("不可恢复的任务类型")
            except (KeyError, ValueError, TypeError, AttributeError) as exc:
                raise RecoveryRecordError("恢复队列身份损坏") from exc
        return value

    def save_position(self, task_id: str, script_id: str) -> None:
        task_id = str(uuid.UUID(task_id))
        script_id = str(uuid.UUID(script_id))
        name = f"position-{task_id}.json"
        try:
            old = self.read(name)
            if old.get("task_id") == task_id:
                self.write(f"position-{task_id}.previous.json", old)
        except RecoveryRecordError:
            pass
        self.write(name, {"task_id": task_id, "script_id": script_id})

    def position(self, task_id: str) -> str | None:
        task_id = str(uuid.UUID(task_id))
        for suffix in (".json", ".previous.json"):
            try:
                entry = self.read(f"position-{task_id}{suffix}")
                if entry.get("task_id") == task_id:
                    return str(uuid.UUID(entry["script_id"]))
            except (RecoveryRecordError, ValueError, KeyError, TypeError):
                continue
        # 用户明确选择：没有有效检查点时从该队列开头运行。
        return None
