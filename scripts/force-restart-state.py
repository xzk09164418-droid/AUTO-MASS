"""强制重启的离线占用重置；不导入后端，不发送邮件或启动队列。"""

import argparse
import copy
import json
import math
import sqlite3
from contextlib import closing
from pathlib import Path


def read_state(path: Path) -> dict | None:
    if not path.exists():
        return None
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        row = db.execute("SELECT value FROM state WHERE id=1").fetchone()
    return json.loads(row[0]) if row else None


def plan(root: Path) -> dict:
    state = read_state(root / "data/external-holds.sqlite3")
    warnings = []
    if state:
        warnings = [
            "脚本占用未登记进程身份，无法结束调用方：" + hold["callerId"]
            for hold in state["holds"].values()
            if hold["state"] in ("active", "stopping", "failed")
        ]
    processes = []
    directory = root / "data/external-processes"
    if directory.exists():
        if directory.is_symlink() or directory.is_junction():
            raise ValueError("外部进程目录不可使用链接")
        for file in directory.glob("*.json"):
            try:
                if file.is_symlink():
                    raise ValueError("linked identity")
                record = json.loads(file.read_text(encoding="utf-8-sig"))
                if not isinstance(record["caller"], str) or not isinstance(
                    record["processes"], list
                ):
                    raise ValueError("invalid identity record")
                if not record["processes"]:
                    warnings.append("桌面借用未登记进程身份：" + record["caller"])
                for process in record["processes"]:
                    if (
                        type(process.get("pid")) is not int
                        or process["pid"] <= 0
                        or type(process.get("sessionId")) is not int
                        or process["sessionId"] <= 0
                        or type(process.get("createdAt")) not in (int, float)
                        or not math.isfinite(process["createdAt"])
                    ):
                        raise ValueError("invalid process identity")
                processes.extend(
                    {**process, "caller": record["caller"]}
                    for process in record["processes"]
                )
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                warnings.append("无法验证外部进程记录，未结束对应程序：" + file.name)
    return {"processes": processes, "warnings": sorted(set(warnings))}


def reset(root: Path, backup: Path) -> None:
    path = root / "data/external-holds.sqlite3"
    if not path.exists():
        return
    if path.is_symlink():
        raise ValueError("外部占用数据库不可使用链接")
    backup.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        with closing(sqlite3.connect(backup / path.name)) as snapshot:
            db.backup(snapshot)
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT value FROM state WHERE id=1").fetchone()
        if row is None:
            return
        state = json.loads(row[0])
        scripts = set()
        for hold in state["holds"].values():
            if hold["state"] in ("active", "stopping", "failed"):
                hold.update(state="released", message="强制重启已解除占用")
                scripts.add(hold["scriptId"])
        for script in sorted(scripts):
            state["sequence"] += 1
            state["released"][script] = state["sequence"]
        # 保留去重键、签名摘要、邮件游标和配置，只更新旧回执中已经失效的占用状态。
        for entry in [*state["requests"].values(), *state["outbox"].values()]:
            result = entry["result"]
            hold = result.get("hold")
            if hold and hold["scriptId"] in scripts:
                current = state["holds"].get(
                    json.dumps([hold["callerId"], hold["holdId"]])
                )
                if current:
                    result.update(
                        hold=copy.deepcopy(current),
                        remainingHolds=0,
                        code=200,
                        status="success",
                        message="强制重启已解除占用",
                    )
        db.execute(
            "UPDATE state SET value=? WHERE id=1",
            (json.dumps(state, ensure_ascii=False),),
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "reset"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    if args.action == "plan":
        print(json.dumps(plan(args.root), ensure_ascii=True))
    else:
        if args.backup is None:
            parser.error("reset requires --backup")
        reset(args.root, args.backup)
