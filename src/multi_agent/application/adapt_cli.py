from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from multi_agent.domain.evidence import Evidence
from multi_agent.domain.mapping import CandidateBatch
from multi_agent.domain.observations import Observation, ObservationRef
from multi_agent.ingestion.manifest import InputManifest
from multi_agent.ingestion.parsers import Parser
from multi_agent.ingestion.profiler import Profiler
from multi_agent.mapping.executor import MappingExecutor
from multi_agent.mapping.spec import MappingSpec
from multi_agent.mapping.validator import MappingValidator
from multi_agent.storage.assets import AssetRepository
from multi_agent.storage.snapshots import SnapshotRepository, default_data_dir
from multi_agent.storage.sqlite import EvidenceRepository, SQLiteStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic stage02 mapping and publish valid observations.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--project-id", default="stage02")
    parser.add_argument("--source-namespace", default="synthetic")
    parser.add_argument("--media-type")
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_adaptation(
        input_path=args.input,
        mapping_path=args.mapping,
        project_id=args.project_id,
        source_namespace=args.source_namespace,
        data_dir=args.data_dir,
        media_type=args.media_type,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0


def run_adaptation(
    input_path: Path,
    mapping_path: Path,
    project_id: str,
    source_namespace: str,
    data_dir: Path,
    media_type: str | None = None,
) -> dict[str, Any]:
    store = SQLiteStore(data_dir / "stage02.sqlite3")
    assets = AssetRepository(store, data_dir / "assets")
    parser = Parser(assets)
    document = parser.parse(
        InputManifest(
            project_id=project_id,
            path=input_path,
            source_namespace=source_namespace,
            media_type=media_type,
        )
    )
    profile = Profiler().profile(document)
    spec = MappingSpec.from_path(mapping_path)
    batch = MappingExecutor().execute(spec, document)
    report = MappingValidator().validate(batch)
    observations = _observations_from_batch(batch, document)
    evidence_id = _stable_id("evidence", project_id, document.asset_id, spec.mapping_id, spec.version)
    evidence = Evidence(
        project_id=project_id,
        evidence_id=evidence_id,
        revision=1,
        kind="observation",
        observation_refs=[
            ObservationRef(observation_id=item.observation_id, revision=item.revision)
            for item in observations
        ],
        scope={
            "asset_id": document.asset_id,
            "asset_revision": document.asset_revision,
            "mapping_id": spec.mapping_id,
            "mapping_revision": spec.version,
        },
        metadata={"validation_status": report.status},
    )
    publish_key = _stable_id("publish", project_id, document.asset_id, spec.mapping_id, spec.version)
    commit = EvidenceRepository(store).publish(observations, [evidence], publish_key)
    snapshot_repo = SnapshotRepository(store)
    snapshot_id = _stable_id("snapshot", project_id, document.asset_id, spec.mapping_id, spec.version)
    try:
        snapshot = snapshot_repo.freeze(
            member_refs=[
                ObservationRef(observation_id=item.observation_id, revision=item.revision)
                for item in observations
            ],
            versions={"parser": document.parser_version, "mapping": spec.version},
            project_id=project_id,
            snapshot_id=snapshot_id,
        )
    except sqlite3.IntegrityError:
        snapshot = snapshot_repo.get(project_id, snapshot_id).snapshot
    return {
        "status": "success",
        "engine": "v2-stage02",
        "project_id": project_id,
        "asset_id": document.asset_id,
        "profile": profile.model_dump(mode="json"),
        "validation": report.model_dump(mode="json"),
        "commit": {
            "inserted_observations": commit.inserted_observations,
            "reused_observations": commit.reused_observations,
            "inserted_evidence": commit.inserted_evidence,
            "reused_evidence": commit.reused_evidence,
        },
        "snapshot": {
            "snapshot_id": snapshot.snapshot_id,
            "member_count": len(snapshot.member_refs),
        },
        "projection": semantic_projection(batch),
    }


def semantic_projection(batch: CandidateBatch) -> list[dict[str, Any]]:
    return sorted(
        [
            {
                "subject_ref": item.subject_ref,
                "source_subject_key": item.source_subject_key,
                "concept_id": item.concept_id,
                "value": item.value.model_dump(mode="json"),
                "event_time": item.event_time,
                "event_time_precision": item.event_time_precision,
                "record_key": item.record_key,
            }
            for item in batch.candidates
        ],
        key=lambda item: (
            item["source_subject_key"],
            item["event_time"] or "",
            item["record_key"],
            item["concept_id"],
        ),
    )


def _observations_from_batch(batch: CandidateBatch, document) -> list[Observation]:
    observations: list[Observation] = []
    for item in batch.candidates:
        observation_id = _stable_id("observation", batch.project_id, item.idempotency_key)
        observations.append(
            Observation(
                project_id=batch.project_id,
                observation_id=observation_id,
                revision=1,
                subject_ref=item.subject_ref,
                concept_id=item.concept_id,
                value=item.value,
                event_time=item.event_time,
                event_time_precision=item.event_time_precision,
                available_at=document.available_at,
                source=item.source,
                validation_status="valid",
                idempotency_key=item.idempotency_key,
                mapping_revision=item.mapping_revision,
                metadata={
                    "source_subject_key": item.source_subject_key,
                    "record_key": item.record_key,
                },
            )
        )
    return observations


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


if __name__ == "__main__":
    raise SystemExit(main())
