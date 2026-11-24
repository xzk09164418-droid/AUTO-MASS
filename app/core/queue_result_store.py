"""按运行 ID 保存最近 200 次队列的逐项结束快照，不存日志。"""

import sqlite3
from contextlib import closing
from pathlib import Path

from app.models.schema import TaskStatusOut

_PATH = Path("data/queue-results.sqlite3")


def save_queue_result(result: TaskStatusOut) -> None:
    payload = result.model_dump_json(exclude={"detail", "error"})
    with closing(sqlite3.connect(_PATH)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS results (id TEXT UNIQUE, payload TEXT NOT NULL)")
        db.execute("INSERT OR REPLACE INTO results VALUES (?, ?)", (result.taskId, payload))
        db.execute("DELETE FROM results WHERE rowid IN "
                   "(SELECT rowid FROM results ORDER BY rowid DESC LIMIT -1 OFFSET 200)")


def read_queue_result(task_id: str) -> TaskStatusOut | None:
    if not _PATH.is_file():
        return None
    with closing(sqlite3.connect(_PATH.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        row = db.execute("SELECT payload FROM results WHERE id = ?", (task_id,)).fetchone()
    return TaskStatusOut.model_validate_json(row[0]) if row else None
