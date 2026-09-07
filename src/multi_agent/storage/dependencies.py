from __future__ import annotations

import json
from collections import deque
from typing import Any

from multi_agent.storage.sqlite import SQLiteStore


class DependencyStore:
    def __init__(self, store: SQLiteStore):
        self.store = store
        self.store.migrate()
        self._migrate()

    def _migrate(self) -> None:
        with self.store.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dependency_edges_v2 (
                    project_id TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_revision TEXT NOT NULL,
                    target_kind TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    target_revision TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (project_id, source_kind, source_id, source_revision, target_kind, target_id, target_revision)
                )
                """
            )

    def record_edge(self, project_id: str, source: tuple[str, str, str], target: tuple[str, str, str], metadata: dict[str, Any] | None = None) -> bool:
        with self.store.connect() as connection:
            before = connection.total_changes
            connection.execute(
                """
                INSERT OR IGNORE INTO dependency_edges_v2(
                    project_id, source_kind, source_id, source_revision, target_kind, target_id, target_revision, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (project_id, source[0], source[1], source[2], target[0], target[1], target[2], json.dumps(metadata or {}, ensure_ascii=False)),
            )
            return connection.total_changes > before

    def affected_closure(self, project_id: str, source: tuple[str, str, str]) -> list[dict[str, str]]:
        seen = {source}
        queue = deque([source])
        affected: list[dict[str, str]] = []
        with self.store.connect() as connection:
            while queue:
                current = queue.popleft()
                rows = connection.execute(
                    """
                    SELECT target_kind, target_id, target_revision FROM dependency_edges_v2
                    WHERE project_id = ? AND source_kind = ? AND source_id = ? AND source_revision = ?
                    """,
                    (project_id, current[0], current[1], current[2]),
                ).fetchall()
                for row in rows:
                    target = (row["target_kind"], row["target_id"], row["target_revision"])
                    if target in seen:
                        continue
                    seen.add(target)
                    queue.append(target)
                    affected.append({"kind": target[0], "id": target[1], "revision": target[2]})
        return affected
