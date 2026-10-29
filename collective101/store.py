import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS agents(id TEXT PRIMARY KEY, config TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS missions(
          id TEXT PRIMARY KEY, prompt TEXT NOT NULL, provider TEXT NOT NULL,
          status TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
          constraints_json TEXT NOT NULL, input_json TEXT NOT NULL,
          max_calls INTEGER NOT NULL, calls INTEGER NOT NULL DEFAULT 0,
          tokens INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(
          id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES missions(id),
          key TEXT NOT NULL, spec TEXT NOT NULL, status TEXT NOT NULL,
          agent_id TEXT, reviewer_id TEXT, attempts INTEGER NOT NULL DEFAULT 0,
          result TEXT, verdict TEXT, error TEXT, version INTEGER NOT NULL,
          UNIQUE(mission_id,key));
        CREATE TABLE IF NOT EXISTS events(
          seq INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT NOT NULL REFERENCES missions(id),
          kind TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS grants(
          mission_id TEXT NOT NULL, task_id TEXT NOT NULL, agent_id TEXT NOT NULL,
          capability TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
          PRIMARY KEY(mission_id,task_id,agent_id,capability));
        CREATE TABLE IF NOT EXISTS evaluations(
          id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT NOT NULL,
          task_id TEXT NOT NULL, agent_id TEXT NOT NULL, reviewer_id TEXT NOT NULL,
          accepted INTEGER NOT NULL, mode TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS artifacts(
          id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, task_id TEXT NOT NULL,
          version INTEGER NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS result_history(
          id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT NOT NULL, task_id TEXT NOT NULL,
          version INTEGER NOT NULL, attempt INTEGER NOT NULL, result TEXT NOT NULL,
          verdict TEXT NOT NULL, created_at TEXT NOT NULL);
        """)
        self.db.commit()

    @contextmanager
    def transaction(self):
        with self.lock:
            try:
                yield self.db
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

    def query(self, sql, values=()) -> list[dict]:
        with self.lock:
            return [dict(row) for row in self.db.execute(sql, values).fetchall()]

    def execute(self, sql, values=()):
        with self.transaction() as db:
            db.execute(sql, values)

    def event(self, mission_id, kind, **data):
        self.execute("INSERT INTO events(mission_id,kind,data,created_at) VALUES(?,?,?,?)",
                     (mission_id, kind, encode(data), now()))

    def mission(self, mission_id) -> dict:
        rows = self.query("SELECT * FROM missions WHERE id=?", (mission_id,))
        if not rows:
            raise ValueError(f"Unknown mission: {mission_id}")
        result = rows[0]
        for column in ("constraints_json", "input_json"):
            result[column.removesuffix("_json")] = json.loads(result.pop(column))
        return result

    def tasks(self, mission_id) -> list[dict]:
        rows = self.query("SELECT * FROM tasks WHERE mission_id=? ORDER BY rowid", (mission_id,))
        for row in rows:
            for column in ("spec", "result", "verdict"):
                row[column] = json.loads(row[column]) if row[column] is not None else None
        return rows

    def reserve_call(self, mission_id):
        with self.transaction() as db:
            changed = db.execute("UPDATE missions SET calls=calls+1 WHERE id=? AND calls<max_calls", (mission_id,)).rowcount
            if not changed:
                raise CallBudgetExceeded("Mission model-call limit reached")

    def close(self):
        self.db.close()


class CallBudgetExceeded(RuntimeError):
    pass
