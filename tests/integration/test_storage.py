from __future__ import annotations

from datetime import datetime, timezone

from multi_agent.domain.assets import SourceLocator
from multi_agent.domain.evidence import Evidence, EvidenceRef
from multi_agent.domain.observations import Observation, ObservationRef, TypedValue
from multi_agent.storage.snapshots import SnapshotRepository
from multi_agent.storage.sqlite import EvidenceRepository, SQLiteStore


def _observation(observation_id: str, revision: int, value: int, key: str) -> Observation:
    return Observation(
        project_id="p1",
        observation_id=observation_id,
        revision=revision,
        subject_ref="subject_s001",
        concept_id="xx.total",
        value=TypedValue(value_type="number", value=value, comparator="="),
        event_time="2024-01-01",
        event_time_precision="date",
        available_at=datetime.now(timezone.utc),
        source=SourceLocator(
            asset_id="asset_a",
            asset_revision=1,
            record_locator="$.xx_v1[0]",
            value_locator="$.xx_v1[0].total",
            parser_version="parser/1",
        ),
        validation_status="valid",
        idempotency_key=key,
        mapping_revision="mapping/1",
    )


def test_publish_is_idempotent_and_survives_reopen(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "stage01.sqlite3")
    repo = EvidenceRepository(store)
    observation = _observation("obs_xx_total", 1, 4, "asset:record:xx.total:mapping")
    evidence = Evidence(
        project_id="p1",
        evidence_id="ev_xx_total",
        revision=1,
        kind="observation",
        observation_refs=[ObservationRef(observation_id=observation.observation_id, revision=1)],
    )

    first = repo.publish([observation], [evidence], "publish-1")
    second = repo.publish([observation], [evidence], "publish-1")
    reopened = EvidenceRepository(SQLiteStore(tmp_path / "stage01.sqlite3"))
    loaded = reopened.get_observation("p1", "obs_xx_total", 1)

    assert first.inserted_observations == 1
    assert second.inserted_observations == 0
    assert second.reused_observations == 1
    assert loaded.value.value == 4


def test_snapshot_keeps_explicit_revision_after_new_revision(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "stage01.sqlite3")
    repo = EvidenceRepository(store)
    snapshots = SnapshotRepository(store)
    original = _observation("obs_xx_total", 1, 4, "key-r1")
    updated = _observation("obs_xx_total", 2, 6, "key-r2")
    ev1 = Evidence(
        project_id="p1",
        evidence_id="ev_xx_total",
        revision=1,
        kind="observation",
        observation_refs=[ObservationRef(observation_id="obs_xx_total", revision=1)],
    )
    ev2 = Evidence(
        project_id="p1",
        evidence_id="ev_xx_total",
        revision=2,
        kind="observation",
        observation_refs=[ObservationRef(observation_id="obs_xx_total", revision=2)],
    )

    repo.publish([original], [ev1], "publish-r1")
    snapshot = snapshots.freeze(
        member_refs=[ObservationRef(observation_id="obs_xx_total", revision=1)],
        versions={"mapping": "mapping/1"},
        project_id="p1",
        snapshot_id="snapshot-r1",
    )
    repo.publish([updated], [ev2], "publish-r2")
    record = snapshots.get("p1", snapshot.snapshot_id)
    old_value = repo.get_observation("p1", record.members[0].observation_id, record.members[0].revision)

    assert record.members[0].revision == 1
    assert old_value.value.value == 4


def test_project_scope_prevents_cross_project_read(tmp_path) -> None:
    repo = EvidenceRepository(SQLiteStore(tmp_path / "stage01.sqlite3"))
    observation = _observation("obs_xx_total", 1, 4, "scope-key")
    evidence = Evidence(
        project_id="p1",
        evidence_id="ev_xx_total",
        revision=1,
        kind="observation",
        observation_refs=[ObservationRef(observation_id="obs_xx_total", revision=1)],
    )

    repo.publish([observation], [evidence], "publish-scope")

    try:
        repo.get(EvidenceRef(evidence_id=evidence.evidence_id, revision=evidence.revision), "p2")
    except KeyError:
        return
    raise AssertionError("cross-project evidence read should fail")
