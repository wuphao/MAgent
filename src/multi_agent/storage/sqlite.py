from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pydantic import TypeAdapter

from multi_agent.domain.evidence import Evidence, EvidenceRef
from multi_agent.domain.observations import Observation


OBSERVATION_ADAPTER = TypeAdapter(Observation)
EVIDENCE_ADAPTER = TypeAdapter(Evidence)


@dataclass(frozen=True)
class CommitResult:
    project_id: str
    idempotency_key: str
    inserted_observations: int
    reused_observations: int
    inserted_evidence: int
    reused_evidence: int
    observation_refs: list[tuple[str, int]]
    evidence_refs: list[tuple[str, int]]


class SQLiteStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def migrate(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS assets (
                    project_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    source_namespace TEXT NOT NULL,
                    uri TEXT NOT NULL,
                    available_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (project_id, asset_id, revision),
                    UNIQUE (project_id, content_hash)
                );

                CREATE TABLE IF NOT EXISTS subject_links (
                    project_id TEXT NOT NULL,
                    source_namespace TEXT NOT NULL,
                    source_subject_key TEXT NOT NULL,
                    subject_ref TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (project_id, source_namespace, source_subject_key)
                );

                CREATE TABLE IF NOT EXISTS observations (
                    project_id TEXT NOT NULL,
                    observation_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    subject_ref TEXT NOT NULL,
                    concept_id TEXT NOT NULL,
                    event_time TEXT,
                    validation_status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (project_id, observation_id, revision),
                    UNIQUE (project_id, idempotency_key)
                );

                CREATE TABLE IF NOT EXISTS evidence (
                    project_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    publish_key TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (project_id, evidence_id, revision),
                    UNIQUE (project_id, publish_key, evidence_id, revision)
                );

                CREATE TABLE IF NOT EXISTS snapshots (
                    project_id TEXT NOT NULL,
                    snapshot_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    versions_json TEXT NOT NULL,
                    PRIMARY KEY (project_id, snapshot_id)
                );

                CREATE TABLE IF NOT EXISTS snapshot_members (
                    project_id TEXT NOT NULL,
                    snapshot_id TEXT NOT NULL,
                    member_kind TEXT NOT NULL,
                    member_id TEXT NOT NULL,
                    member_revision INTEGER NOT NULL,
                    PRIMARY KEY (project_id, snapshot_id, member_kind, member_id, member_revision),
                    FOREIGN KEY (project_id, snapshot_id) REFERENCES snapshots(project_id, snapshot_id)
                );

                CREATE TABLE IF NOT EXISTS runs (
                    project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    snapshot_id TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (project_id, run_id)
                );

                INSERT OR IGNORE INTO schema_migrations(version) VALUES (1);
                """
            )


class EvidenceRepository:
    def __init__(self, store: SQLiteStore):
        self.store = store
        self.store.migrate()

    def publish(
        self,
        observations: Iterable[Observation],
        evidence: Iterable[Evidence],
        idempotency_key: str,
    ) -> CommitResult:
        observations = list(observations)
        evidence = list(evidence)
        project_ids = {item.project_id for item in observations + evidence}
        if len(project_ids) != 1:
            raise ValueError("publish requires exactly one project_id")
        project_id = project_ids.pop()

        inserted_observations = 0
        reused_observations = 0
        inserted_evidence = 0
        reused_evidence = 0
        observation_refs: list[tuple[str, int]] = []
        evidence_refs: list[tuple[str, int]] = []

        with self.store.connect() as connection:
            connection.execute("BEGIN")
            for observation in observations:
                before = connection.total_changes
                connection.execute(
                    """
                    INSERT OR IGNORE INTO observations (
                        project_id, observation_id, revision, idempotency_key,
                        subject_ref, concept_id, event_time, validation_status, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        observation.project_id,
                        observation.observation_id,
                        observation.revision,
                        observation.idempotency_key,
                        observation.subject_ref,
                        observation.concept_id,
                        observation.event_time,
                        observation.validation_status,
                        observation.model_dump_json(),
                    ),
                )
                if connection.total_changes == before:
                    reused_observations += 1
                    existing = connection.execute(
                        """
                        SELECT observation_id, revision, payload_json FROM observations
                        WHERE project_id = ? AND idempotency_key = ?
                        """,
                        (observation.project_id, observation.idempotency_key),
                    ).fetchone()
                    if existing is None:
                        raise RuntimeError("observation idempotency lookup failed")
                    payload = json.loads(existing["payload_json"])
                    candidate = json.loads(observation.model_dump_json())
                    if payload != candidate:
                        raise ValueError("idempotency key conflicts with different observation payload")
                    observation_refs.append((existing["observation_id"], existing["revision"]))
                else:
                    inserted_observations += 1
                    observation_refs.append((observation.observation_id, observation.revision))

            known_refs = set(observation_refs)
            for item in evidence:
                for ref in item.observation_refs:
                    key = (ref.observation_id, ref.revision)
                    if key not in known_refs:
                        found = connection.execute(
                            """
                            SELECT 1 FROM observations
                            WHERE project_id = ? AND observation_id = ? AND revision = ?
                            """,
                            (item.project_id, ref.observation_id, ref.revision),
                        ).fetchone()
                        if found is None:
                            raise ValueError("evidence references a missing observation revision")

                before = connection.total_changes
                connection.execute(
                    """
                    INSERT OR IGNORE INTO evidence (
                        project_id, evidence_id, revision, publish_key, kind, status, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.project_id,
                        item.evidence_id,
                        item.revision,
                        idempotency_key,
                        item.kind,
                        item.status,
                        item.model_dump_json(),
                    ),
                )
                if connection.total_changes == before:
                    reused_evidence += 1
                    existing = connection.execute(
                        """
                        SELECT evidence_id, revision, payload_json FROM evidence
                        WHERE project_id = ? AND publish_key = ? AND evidence_id = ? AND revision = ?
                        """,
                        (item.project_id, idempotency_key, item.evidence_id, item.revision),
                    ).fetchone()
                    if existing is None:
                        raise RuntimeError("evidence idempotency lookup failed")
                    payload = json.loads(existing["payload_json"])
                    candidate = json.loads(item.model_dump_json())
                    if payload != candidate:
                        raise ValueError("idempotency key conflicts with different evidence payload")
                    evidence_refs.append((existing["evidence_id"], existing["revision"]))
                else:
                    inserted_evidence += 1
                    evidence_refs.append((item.evidence_id, item.revision))

        return CommitResult(
            project_id=project_id,
            idempotency_key=idempotency_key,
            inserted_observations=inserted_observations,
            reused_observations=reused_observations,
            inserted_evidence=inserted_evidence,
            reused_evidence=reused_evidence,
            observation_refs=observation_refs,
            evidence_refs=evidence_refs,
        )

    def get(self, ref: EvidenceRef, project_scope: str) -> Evidence:
        with self.store.connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json FROM evidence
                WHERE project_id = ? AND evidence_id = ? AND revision = ?
                """,
                (project_scope, ref.evidence_id, ref.revision),
            ).fetchone()
        if row is None:
            raise KeyError(f"evidence not found: {project_scope}/{ref.evidence_id}@{ref.revision}")
        return EVIDENCE_ADAPTER.validate_json(row["payload_json"])

    def get_observation(self, project_id: str, observation_id: str, revision: int) -> Observation:
        with self.store.connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json FROM observations
                WHERE project_id = ? AND observation_id = ? AND revision = ?
                """,
                (project_id, observation_id, revision),
            ).fetchone()
        if row is None:
            raise KeyError(f"observation not found: {project_id}/{observation_id}@{revision}")
        return OBSERVATION_ADAPTER.validate_json(row["payload_json"])

    def list_observations(self, project_id: str) -> list[Observation]:
        with self.store.connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM observations
                WHERE project_id = ?
                ORDER BY observation_id, revision
                """,
                (project_id,),
            ).fetchall()
        return [OBSERVATION_ADAPTER.validate_json(row["payload_json"]) for row in rows]
