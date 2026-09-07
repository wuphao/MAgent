from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from multi_agent.domain.requests import AnalysisRequest
from multi_agent.domain.tasks import Plan, TaskRecord, TaskSpec, TaskState


ALLOWED_TRANSITIONS: set[tuple[TaskState, TaskState]] = {
    ("pending", "ready"),
    ("pending", "needs_metadata"),
    ("pending", "skipped"),
    ("ready", "running"),
    ("running", "succeeded"),
    ("running", "retry_wait"),
    ("running", "failed"),
    ("retry_wait", "ready"),
    ("ready", "skipped"),
}


class TaskStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def migrate(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs_v2 (
                    run_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    cancel_requested INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS tasks_v2 (
                    run_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    spec_json TEXT NOT NULL,
                    result_json TEXT,
                    error_code TEXT,
                    message TEXT,
                    lease_owner TEXT,
                    lease_expires_at TEXT,
                    attempt_id TEXT,
                    fencing_token INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (run_id, task_id),
                    FOREIGN KEY (run_id) REFERENCES runs_v2(run_id)
                );

                CREATE TABLE IF NOT EXISTS task_attempts_v2 (
                    run_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    error_code TEXT,
                    message TEXT,
                    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    finished_at TEXT,
                    PRIMARY KEY (run_id, task_id, attempt)
                );

                CREATE TABLE IF NOT EXISTS budget_ledger_v2 (
                    run_id TEXT NOT NULL,
                    entry_id TEXT NOT NULL,
                    task_id TEXT,
                    kind TEXT NOT NULL,
                    calls INTEGER NOT NULL DEFAULT 0,
                    tokens INTEGER NOT NULL DEFAULT 0,
                    cost REAL,
                    usage_unknown INTEGER NOT NULL DEFAULT 0,
                    note TEXT,
                    PRIMARY KEY (run_id, entry_id)
                );
                """
            )
            for column, definition in {
                "lease_owner": "TEXT",
                "lease_expires_at": "TEXT",
                "attempt_id": "TEXT",
                "fencing_token": "INTEGER NOT NULL DEFAULT 0",
            }.items():
                _add_column(connection, "tasks_v2", column, definition)

    def create_run(self, request: AnalysisRequest, plan: Plan) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO runs_v2(run_id, project_id, goal, request_json, status, cancel_requested)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (plan.run_id, request.project_id, request.goal, request.model_dump_json(), "pending", int(request.cancel_requested)),
            )
            for task in plan.tasks:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO tasks_v2(run_id, task_id, state, attempts, spec_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (plan.run_id, task.task_id, "pending", 0, task.model_dump_json()),
                )


    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT run_id, project_id, goal, status, cancel_requested FROM runs_v2 WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return dict(row) if row else None

    def set_cancel_requested(self, run_id: str) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE runs_v2 SET cancel_requested = 1 WHERE run_id = ?", (run_id,))

    def cancel_requested(self, run_id: str) -> bool:
        with self.connect() as connection:
            row = connection.execute("SELECT cancel_requested FROM runs_v2 WHERE run_id = ?", (run_id,)).fetchone()
        return bool(row and row["cancel_requested"])

    def transition(self, run_id: str, task_id: str, expected: TaskState, new: TaskState) -> bool:
        if (expected, new) not in ALLOWED_TRANSITIONS:
            raise ValueError(f"illegal transition: {expected}->{new}")
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE tasks_v2 SET state = ?
                WHERE run_id = ? AND task_id = ? AND state = ?
                """,
                (new, run_id, task_id, expected),
            )
            return cursor.rowcount == 1

    def record_attempt(self, run_id: str, task_id: str, attempt: int, status: str, error_code: str | None = None, message: str | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO task_attempts_v2(run_id, task_id, attempt, status, error_code, message, finished_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (run_id, task_id, attempt, status, error_code, message),
            )
            connection.execute(
                """
                UPDATE tasks_v2
                SET attempts = MAX(attempts, ?), error_code = ?, message = ?
                WHERE run_id = ? AND task_id = ?
                """,
                (attempt, error_code, message, run_id, task_id),
            )

    def store_result(self, run_id: str, task_id: str, result: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE tasks_v2 SET result_json = ?
                WHERE run_id = ? AND task_id = ?
                """,
                (json.dumps(result, ensure_ascii=False), run_id, task_id),
            )

    def get_tasks(self, run_id: str) -> list[TaskRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id, state, attempts, spec_json, result_json, error_code, message
                FROM tasks_v2 WHERE run_id = ? ORDER BY task_id
                """,
                (run_id,),
            ).fetchall()
        records = []
        for row in rows:
            records.append(
                TaskRecord(
                    run_id=row["run_id"],
                    spec=TaskSpec.model_validate_json(row["spec_json"]),
                    state=row["state"],
                    attempts=row["attempts"],
                    result=json.loads(row["result_json"]) if row["result_json"] else None,
                    error_code=row["error_code"],
                    message=row["message"],
                )
            )
        return records


class BudgetLedger:
    def __init__(self, store: TaskStore, run_id: str, max_calls: int = 0, max_tokens: int = 0):
        self.store = store
        self.run_id = run_id
        self.max_calls = max_calls
        self.max_tokens = max_tokens

    def reserve(self, entry_id: str, task_id: str | None, calls: int, tokens: int) -> bool:
        with self.store.connect() as connection:
            used = connection.execute(
                """
                SELECT COALESCE(SUM(calls), 0) AS calls, COALESCE(SUM(tokens), 0) AS tokens
                FROM budget_ledger_v2 WHERE run_id = ?
                """,
                (self.run_id,),
            ).fetchone()
            if self.max_calls and used["calls"] + calls > self.max_calls:
                return False
            if self.max_tokens and used["tokens"] + tokens > self.max_tokens:
                return False
            connection.execute(
                """
                INSERT INTO budget_ledger_v2(run_id, entry_id, task_id, kind, calls, tokens)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (self.run_id, entry_id, task_id, "reserve", calls, tokens),
            )
            return True

    def settle(self, entry_id: str, task_id: str | None, calls: int, tokens: int, cost: float | None = None, usage_unknown: bool = False, note: str | None = None) -> None:
        with self.store.connect() as connection:
            connection.execute(
                """
                INSERT INTO budget_ledger_v2(run_id, entry_id, task_id, kind, calls, tokens, cost, usage_unknown, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (self.run_id, entry_id, task_id, "settle", calls, tokens, cost, int(usage_unknown), note),
            )

    def entries(self) -> list[dict[str, Any]]:
        with self.store.connect() as connection:
            rows = connection.execute("SELECT * FROM budget_ledger_v2 WHERE run_id = ? ORDER BY entry_id", (self.run_id,)).fetchall()
        return [dict(row) for row in rows]


def _add_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


