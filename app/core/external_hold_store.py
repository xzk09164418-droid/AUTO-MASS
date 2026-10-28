"""外部占用的事务存储；只负责持久化，不决定调度或邮件策略。

数据库与主配置分离，避免运行中的占用写入用户保存的队列。每次变更以完整
快照提交，命令去重、释放墓碑与占用状态因此不会出现部分提交。连接只在调用
线程内使用；上层用同一异步锁串行提交，磁盘 I/O 则放入工作线程。
"""

import json
import sqlite3
from contextlib import closing
from pathlib import Path


class ExternalHoldStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
            )
            row = db.execute("SELECT value FROM state WHERE id=1").fetchone()
        return (
            json.loads(row[0])
            if row
            else {
                "holds": {},
                "requests": {},
                "released": {},
                "sequence": 0,
                "settings": {
                    "enabled": False,
                    "email": "",
                    "authorizationCode": "",
                    "callers": {},
                },
                "mail": {},
                "outbox": {},
            }
        )

    def save(self, state: dict) -> None:
        # SQLite 的事务替换保证断电/异常时仍可读取上一次完整状态。
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO state(id,value) VALUES(1,?)",
                (json.dumps(state, ensure_ascii=False),),
            )
