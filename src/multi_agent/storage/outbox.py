from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from multi_agent.storage.sqlite import SQLiteStore


class OutboxStore:
    def __init__(self, store: SQLiteStore):
        self.store = store
        self.store.migrate()
        self._migrate()

    def _migrate(self) -> None:
        with self.store.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS outbox_v2 (
                    event_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    consumed_at TEXT
                )
                """
            )

    def enqueue(self, event_id: str, project_id: str, event_type: str, payload: dict[str, Any]) -> bool:
        with self.store.connect() as connection:
            try:
                connection.execute(
                    "INSERT INTO outbox_v2(event_id, project_id, event_type, payload_json) VALUES (?, ?, ?, ?)",
                    (event_id, project_id, event_type, json.dumps(payload, ensure_ascii=False)),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def pending(self, project_id: str | None = None) -> list[dict[str, Any]]:
        with self.store.connect() as connection:
            if project_id:
                rows = connection.execute("SELECT * FROM outbox_v2 WHERE project_id = ? AND status = 'pending' ORDER BY created_at", (project_id,)).fetchall()
            else:
                rows = connection.execute("SELECT * FROM outbox_v2 WHERE status = 'pending' ORDER BY created_at").fetchall()
        return [_row(row) for row in rows]

    def mark_consumed(self, event_id: str) -> bool:
        with self.store.connect() as connection:
            cursor = connection.execute("UPDATE outbox_v2 SET status = 'consumed', consumed_at = CURRENT_TIMESTAMP WHERE event_id = ? AND status = 'pending'", (event_id,))
            return cursor.rowcount == 1


def _row(row) -> dict[str, Any]:
    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json"))
    return item
