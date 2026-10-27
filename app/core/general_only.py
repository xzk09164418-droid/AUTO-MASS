"""通用脚本版本的存量配置整理：先留存原文，再去除专项及其队列引用。"""

import hashlib
import json
import os
import tempfile
from pathlib import Path

from app.utils import get_logger

logger = get_logger("通用脚本配置迁移")


def _write_atomic(path: Path, data: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".general-only-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def retain_general_scripts(config_dir: Path) -> None:
    script_path = config_dir / "ScriptConfig.json"
    if not script_path.exists():
        return
    original = script_path.read_bytes()
    scripts = json.loads(original.decode("utf-8-sig"))
    instances = scripts.get("instances", [])
    removed = {item["uid"] for item in instances if item["type"] != "GeneralConfig"}
    if not removed:
        return
    scripts["instances"] = [item for item in instances if item["uid"] not in removed]
    for uid in removed:
        scripts.pop(uid, None)
    sources = {script_path: original}
    updates = {}
    queue_path = config_dir / "QueueConfig.json"
    if queue_path.exists():
        sources[queue_path] = queue_path.read_bytes()
        queues = json.loads(sources[queue_path].decode("utf-8-sig"))
        for row in queues.get("instances", []):
            items = queues[row["uid"]].get("SubConfigsInfo", {}).get("QueueItem", {})
            remove_items = {
                item["uid"]
                for item in items.get("instances", [])
                if items[item["uid"]].get("Info", {}).get("ScriptId") in removed
            }
            if remove_items:
                items["instances"] = [
                    item
                    for item in items["instances"]
                    if item["uid"] not in remove_items
                ]
                for uid in remove_items:
                    items.pop(uid, None)
        updates[queue_path] = json.dumps(queues, ensure_ascii=False, indent=4).encode(
            "utf-8"
        )
    updates[script_path] = json.dumps(scripts, ensure_ascii=False, indent=4).encode(
        "utf-8"
    )
    fingerprint = hashlib.sha256(b"".join(sources.values())).hexdigest()[:16]
    backup = config_dir / "general-only-backup" / fingerprint
    backup.mkdir(parents=True, exist_ok=True)
    for path, data in sources.items():
        saved = backup / path.name
        if saved.exists():
            if saved.read_bytes() != data:
                raise RuntimeError(f"配置备份内容不一致: {saved}")
        else:
            with saved.open("xb") as stream:
                stream.write(data)
    written = []
    try:
        for path, data in updates.items():
            _write_atomic(path, data)
            written.append(path)
    except Exception:
        for path in reversed(written):
            _write_atomic(path, sources[path])
        raise
    logger.info(
        f"已保留通用脚本，移除 {len(removed)} 个专项配置及其队列引用；原配置备份: {backup}"
    )
