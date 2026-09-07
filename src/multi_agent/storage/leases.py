from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from multi_agent.storage.tasks import TaskStore


class LeaseStore:
    def __init__(self, task_store: TaskStore):
        self.task_store = task_store
        self._migrate()

    def _migrate(self) -> None:
        with self.task_store.connect() as connection:
            _add_column(connection, "tasks_v2", "lease_owner", "TEXT")
            _add_column(connection, "tasks_v2", "lease_expires_at", "TEXT")
            _add_column(connection, "tasks_v2", "attempt_id", "TEXT")
            _add_column(connection, "tasks_v2", "fencing_token", "INTEGER NOT NULL DEFAULT 0")

    def claim(self, run_id: str, task_id: str, owner: str, lease_seconds: int = 60) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=lease_seconds)
        attempt_id = f"attempt-{run_id}-{task_id}-{int(now.timestamp() * 1000)}"
        with self.task_store.connect() as connection:
            connection.execute("BEGIN")
            row = connection.execute(
                """
                SELECT state, lease_expires_at, fencing_token FROM tasks_v2
                WHERE run_id = ? AND task_id = ?
                """,
                (run_id, task_id),
            ).fetchone()
            if row is None:
                connection.rollback()
                return None
            lease_expired = row["lease_expires_at"] is None or row["lease_expires_at"] <= now.isoformat()
            if row["state"] not in {"pending", "ready", "retry_wait", "running"} or not lease_expired:
                connection.rollback()
                return None
            token = int(row["fencing_token"] or 0) + 1
            connection.execute(
                """
                UPDATE tasks_v2
                SET state = 'running', lease_owner = ?, lease_expires_at = ?, attempt_id = ?, fencing_token = ?
                WHERE run_id = ? AND task_id = ? AND fencing_token = ?
                """,
                (owner, expires.isoformat(), attempt_id, token, run_id, task_id, int(row["fencing_token"] or 0)),
            )
            connection.commit()
        return {"run_id": run_id, "task_id": task_id, "owner": owner, "attempt_id": attempt_id, "fencing_token": token, "lease_expires_at": expires.isoformat()}

    def complete(self, run_id: str, task_id: str, fencing_token: int, result_json: str, state: str = "succeeded") -> bool:
        with self.task_store.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE tasks_v2
                SET state = ?, result_json = ?, lease_owner = NULL, lease_expires_at = NULL
                WHERE run_id = ? AND task_id = ? AND state = 'running' AND fencing_token = ?
                """,
                (state, result_json, run_id, task_id, fencing_token),
            )
            return cursor.rowcount == 1

    def expire_running(self, owner: str | None = None) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self.task_store.connect() as connection:
            if owner:
                cursor = connection.execute(
                    """
                    UPDATE tasks_v2 SET state = 'ready', lease_owner = NULL, lease_expires_at = NULL
                    WHERE state = 'running' AND lease_owner = ? AND lease_expires_at <= ?
                    """,
                    (owner, now),
                )
            else:
                cursor = connection.execute(
                    """
                    UPDATE tasks_v2 SET state = 'ready', lease_owner = NULL, lease_expires_at = NULL
                    WHERE state = 'running' AND lease_expires_at <= ?
                    """,
                    (now,),
                )
            return cursor.rowcount


def _add_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
