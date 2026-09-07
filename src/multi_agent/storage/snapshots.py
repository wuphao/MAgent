from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass

from multi_agent.domain.assets import utc_now
from multi_agent.domain.evidence import EvidenceRef
from multi_agent.domain.observations import ObservationRef
from multi_agent.domain.runs import ReportSnapshot
from multi_agent.storage.sqlite import SQLiteStore


@dataclass(frozen=True)
class SnapshotRecord:
    snapshot: ReportSnapshot
    members: list[EvidenceRef | ObservationRef]


class SnapshotRepository:
    def __init__(self, store: SQLiteStore):
        self.store = store
        self.store.migrate()

    def freeze(
        self,
        member_refs: list[EvidenceRef | ObservationRef],
        versions: dict[str, str] | None = None,
        *,
        project_id: str,
        snapshot_id: str | None = None,
    ) -> ReportSnapshot:
        snapshot_id = snapshot_id or _snapshot_id(member_refs, versions or {})
        snapshot = ReportSnapshot(
            project_id=project_id,
            snapshot_id=snapshot_id,
            member_refs=member_refs,
            versions=versions or {},
            created_at=utc_now(),
        )
        with self.store.connect() as connection:
            connection.execute(
                """
                INSERT INTO snapshots(project_id, snapshot_id, created_at, versions_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    snapshot.project_id,
                    snapshot.snapshot_id,
                    snapshot.created_at.isoformat(),
                    json.dumps(snapshot.versions, ensure_ascii=False, sort_keys=True),
                ),
            )
            for ref in member_refs:
                if isinstance(ref, EvidenceRef):
                    member_kind = "evidence"
                    member_id = ref.evidence_id
                else:
                    member_kind = "observation"
                    member_id = ref.observation_id
                connection.execute(
                    """
                    INSERT INTO snapshot_members(
                        project_id, snapshot_id, member_kind, member_id, member_revision
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        snapshot_id,
                        member_kind,
                        member_id,
                        ref.revision,
                    ),
                )
        return snapshot

    def get(self, project_id: str, snapshot_id: str) -> SnapshotRecord:
        with self.store.connect() as connection:
            row = connection.execute(
                """
                SELECT created_at, versions_json FROM snapshots
                WHERE project_id = ? AND snapshot_id = ?
                """,
                (project_id, snapshot_id),
            ).fetchone()
            if row is None:
                raise KeyError(f"snapshot not found: {project_id}/{snapshot_id}")
            member_rows = connection.execute(
                """
                SELECT member_kind, member_id, member_revision FROM snapshot_members
                WHERE project_id = ? AND snapshot_id = ?
                ORDER BY member_kind, member_id, member_revision
                """,
                (project_id, snapshot_id),
            ).fetchall()

        members: list[EvidenceRef | ObservationRef] = []
        for member in member_rows:
            if member["member_kind"] == "evidence":
                members.append(
                    EvidenceRef(evidence_id=member["member_id"], revision=member["member_revision"])
                )
            else:
                members.append(
                    ObservationRef(observation_id=member["member_id"], revision=member["member_revision"])
                )
        snapshot = ReportSnapshot(
            project_id=project_id,
            snapshot_id=snapshot_id,
            member_refs=members,
            versions=json.loads(row["versions_json"]),
            created_at=row["created_at"],
        )
        return SnapshotRecord(snapshot=snapshot, members=members)


def default_data_dir() -> Path:
    from pathlib import Path

    return Path("data") / "v2"


def _snapshot_id(member_refs: list[EvidenceRef | ObservationRef], versions: dict[str, str]) -> str:
    payload = {
        "members": [
            ref.model_dump(mode="json")
            for ref in member_refs
        ],
        "versions": versions,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:20]
    return f"snapshot_{digest}"
