"""通用脚本配置迁移：先备份，原位转换 MaaEnd，再移除其余停用专项。

MaaEnd 的脚本/用户 ID 不变，队列引用不变。原生配置始终归源程序所有，
迁移不解释或改写 MXU 私有字段；旧专项的快速配置留在备份中。
"""

import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path

from app.utils import get_logger

logger = get_logger("通用脚本配置迁移")


def maaend_to_general(source: dict) -> dict:
    """将 MAS 的 MaaEnd 配置转成原生 CLI 启动的通用脚本配置。

    自动执行使用 MXU 已公开的 CLI，设置入口无参数，防止打开配置时启动任务。
    多用户信息、通知、次数和运行限制保留；账号切换与游戏任务由原生程序配置。
    不把旧专项快速配置误当作通用脚本仍能执行的能力。
    """
    root = Path(source.get("Info", {}).get("Path", ""))
    users = copy.deepcopy(source.get("SubConfigsInfo", {}).get("UserData", {}))
    for row in users.get("instances", []):
        row["type"] = "GeneralUserConfig"
        user = users[row["uid"]]
        info = user.get("Info", {})
        user["Info"] = {
            key: value
            for key, value in info.items()
            if key
            in {
                "Name",
                "Status",
                "RemainedDay",
                "Notes",
                "IfScriptBeforeTask",
                "ScriptBeforeTask",
                "IfScriptAfterTask",
                "ScriptAfterTask",
            }
        }
        user["Info"].update(Base="native", IfUseMasConfig=False)
        users[row["uid"]] = {
            key: value
            for key, value in user.items()
            if key in {"Info", "Data", "Notify", "SubConfigsInfo"}
        }
    return {
        "Info": {
            "Name": source.get("Info", {}).get("Name", "MaaEnd"),
            "RootPath": str(root),
        },
        "Script": {
            "ScriptPath": str(root),
            "Arguments": "MaaEnd.exe%--autostart --quit-after-run|MaaEnd.exe%",
            "ConfigPath": str(root / "config" / "mxu-MaaEnd.json"),
            "ConfigPathMode": "File",
        },
        "Run": {
            key: value
            for key, value in source.get("Run", {}).items()
            if key
            in {"HardTimeLimit", "ProxyTimesLimit", "RunTimeLimit", "RunTimesLimit"}
        },
        "SubConfigsInfo": {"UserData": users},
    }


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
    # 全新安装首次启动只建出空文件，第二次启动时不能把它当 JSON 解析
    if not original.strip():
        return
    scripts = json.loads(original.decode("utf-8-sig"))
    instances = scripts.get("instances", [])
    converted = []
    for item in instances:
        if item["type"] == "MaaEndConfig":
            scripts[item["uid"]] = maaend_to_general(scripts[item["uid"]])
            item["type"] = "GeneralConfig"
            converted.append(item["uid"])
    removed = {item["uid"] for item in instances if item["type"] != "GeneralConfig"}
    if not removed and not converted:
        return
    scripts["instances"] = [item for item in instances if item["uid"] not in removed]
    for uid in removed:
        scripts.pop(uid, None)
    sources = {script_path: original}
    updates = {}
    queue_path = config_dir / "QueueConfig.json"
    if removed and queue_path.exists():
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
        f"已转换 {len(converted)} 个 MaaEnd 为通用脚本，移除 {len(removed)} 个停用专项及其队列引用；原配置备份: {backup}"
    )
