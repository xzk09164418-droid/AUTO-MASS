"""通用脚本归属异常的持久提示与运行前选择，不负责进程识别。"""

import asyncio
import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.models.schema import GeneralOwnershipPromptData


@dataclass
class PendingOwnershipPrompt:
    data: GeneralOwnershipPromptData
    answer: asyncio.Future[bool] | None


class GeneralOwnership:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.pending: dict[str, PendingOwnershipPrompt] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def fingerprint(config) -> str:
        keys = (
            "ScriptPath",
            "Arguments",
            "WorkingDirectory",
            "UseLaunchListOnFirstRun",
            "IfTrackProcess",
            "TrackProcessName",
            "TrackProcessExe",
            "TrackProcessCmdline",
            "TaskKill",
            "TaskKillMode",
            "Restart",
        )
        data = {key: config.get("Script", key) for key in keys}
        return hashlib.sha256(
            json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

    def _path(self, script_id: str) -> Path:
        return self.root / f"{uuid.UUID(script_id)}.json"

    def _save(self, script_id: str, fingerprint: str, confirmed: bool) -> None:
        path = self._path(script_id)
        if confirmed:
            path.unlink(missing_ok=True)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"fingerprint": fingerprint}), encoding="utf-8")
        os.replace(temporary, path)

    async def record(self, script_id: str, config, *, confirmed: bool) -> None:
        async with self._lock:
            await asyncio.to_thread(
                self._save, script_id, self.fingerprint(config), confirmed
            )

    def _needs_prompt(self, script_id: str, fingerprint: str) -> bool:
        path = self._path(script_id)
        if not path.exists():
            return False
        return (
            json.loads(path.read_text(encoding="utf-8")).get("fingerprint")
            == fingerprint
        )

    async def before_run(
        self, script_id: str, script_name: str, config, *, automated: bool
    ) -> bool:
        async with self._lock:
            needed = await asyncio.to_thread(
                self._needs_prompt, script_id, self.fingerprint(config)
            )
        if not needed:
            return True
        # 定时任务不等待浏览器；同一脚本的重复定时提示只保留最新一条。
        for key, item in list(self.pending.items()):
            if item.data.scriptId == script_id and item.answer is None:
                self.pending.pop(key)
        request_id = str(uuid.uuid4())
        answer = None if automated else asyncio.get_running_loop().create_future()
        self.pending[request_id] = PendingOwnershipPrompt(
            GeneralOwnershipPromptData(
                requestId=request_id,
                scriptId=script_id,
                scriptName=script_name,
                automated=automated,
                reason="上次运行无法确认脚本主体归属，建议检查追踪设置或更改清理范围。",
            ),
            answer,
        )
        if automated:
            return False
        assert answer is not None
        try:
            # True 表示继续原逻辑；选择修改则跳过本次，不自动重启任务。
            return await answer
        finally:
            self.pending.pop(request_id, None)

    def prompts(self) -> list[GeneralOwnershipPromptData]:
        return [item.data for item in self.pending.values()]

    def respond(self, request_id: str, *, edit: bool) -> bool:
        item = self.pending.pop(request_id, None)
        if item is None:
            return False
        if item.answer is not None and not item.answer.done():
            item.answer.set_result(not edit)
        return True


general_ownership = GeneralOwnership(Path("data/general-ownership"))
