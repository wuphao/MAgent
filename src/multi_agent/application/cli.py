from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from multi_agent.domain.assets import SourceLocator
from multi_agent.domain.errors import format_validation_errors
from multi_agent.domain.evidence import Evidence
from multi_agent.domain.observations import Observation, ObservationRef, TypedValue
from multi_agent.storage.assets import AssetManifest, AssetRepository
from multi_agent.storage.snapshots import SnapshotRepository, default_data_dir
from multi_agent.storage.sqlite import EvidenceRepository, SQLiteStore


PARSER_VERSION = "stage01-json-inventory/1"
MAPPING_REVISION = "stage01-inventory/1"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Register a source file and publish traceable v2 inventory evidence."
    )
    parser.add_argument("case", type=Path, help="JSON input file to register.")
    parser.add_argument("--project-id", default="stage01", help="Project namespace for stored evidence.")
    parser.add_argument("--source-namespace", default="synthetic", help="Source namespace for subject keys.")
    parser.add_argument("--data-dir", type=Path, default=default_data_dir(), help="Directory for SQLite and assets.")
    parser.add_argument("--output", type=Path, help="Optionally save the v2 inventory JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_inventory(
            case_path=args.case,
            project_id=args.project_id,
            source_namespace=args.source_namespace,
            data_dir=args.data_dir,
        )
    except ValidationError as exc:
        print(json.dumps({"status": "contract_error", "errors": format_validation_errors(exc)}, ensure_ascii=False, indent=2))
        return 2

    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0


def run_inventory(
    case_path: Path,
    project_id: str,
    source_namespace: str,
    data_dir: Path,
) -> dict[str, Any]:
    raw_text = case_path.read_text(encoding="utf-8")
    document = json.loads(raw_text)
    if not isinstance(document, dict):
        raise ValueError("stage01 inventory expects a JSON object")

    store = SQLiteStore(data_dir / "stage01.sqlite3")
    assets = AssetRepository(store, data_dir / "assets")
    evidence_repo = EvidenceRepository(store)
    snapshots = SnapshotRepository(store)

    asset = assets.register(
        AssetManifest(
            project_id=project_id,
            path=case_path,
            source_namespace=source_namespace,
            media_type="application/json",
        )
    )
    subject_ref = _subject_ref(project_id, source_namespace, document)
    observations = _inventory_observations(
        project_id,
        subject_ref,
        asset.asset_id,
        asset.revision,
        asset.available_at,
        document,
    )
    evidence_id = _stable_id("evidence", project_id, asset.asset_id, "source_inventory", MAPPING_REVISION)
    evidence = Evidence(
        project_id=project_id,
        evidence_id=evidence_id,
        revision=1,
        kind="source_inventory",
        observation_refs=[
            ObservationRef(observation_id=item.observation_id, revision=item.revision)
            for item in observations
        ],
        scope={"asset_id": asset.asset_id, "asset_revision": asset.revision, "subject_ref": subject_ref},
        metadata={
            "capability_status": "capability_unavailable",
            "capability_message": "stage01 publishes only source inventory and traceability; analysis agents are not implemented in v2 yet.",
        },
    )
    publish_key = _stable_id("publish", project_id, asset.asset_id, MAPPING_REVISION)
    commit = evidence_repo.publish(observations, [evidence], publish_key)
    snapshot_id = _stable_id("snapshot", project_id, evidence.evidence_id, str(evidence.revision))
    try:
        snapshot = snapshots.freeze(
            member_refs=[ObservationRef(observation_id=item.observation_id, revision=item.revision) for item in observations],
            versions={"parser": PARSER_VERSION, "mapping": MAPPING_REVISION},
            project_id=project_id,
            snapshot_id=snapshot_id,
        )
    except sqlite3.IntegrityError:
        snapshot = snapshots.get(project_id, snapshot_id).snapshot

    return {
        "status": "success",
        "engine": "v2",
        "project_id": project_id,
        "asset": {
            "asset_id": asset.asset_id,
            "revision": asset.revision,
            "content_hash": asset.content_hash,
            "media_type": asset.media_type,
            "uri": asset.uri,
        },
        "snapshot": {
            "snapshot_id": snapshot.snapshot_id,
            "member_count": len(snapshot.member_refs),
            "versions": snapshot.versions,
        },
        "commit": {
            "inserted_observations": commit.inserted_observations,
            "reused_observations": commit.reused_observations,
            "inserted_evidence": commit.inserted_evidence,
            "reused_evidence": commit.reused_evidence,
        },
        "inventory": [
            {
                "observation_id": item.observation_id,
                "revision": item.revision,
                "concept_id": item.concept_id,
                "value": item.value.model_dump(mode="json"),
                "source": item.source.model_dump(mode="json"),
            }
            for item in observations
        ],
        "capabilities": [
            {
                "capability": "clinical_analysis",
                "status": "capability_unavailable",
                "reason": "v2 stage01 has not implemented professional analysis agents.",
            }
        ],
    }


def _inventory_observations(
    project_id: str,
    subject_ref: str,
    asset_id: str,
    asset_revision: int,
    available_at,
    document: dict[str, Any],
) -> list[Observation]:
    observations: list[Observation] = []
    for key in sorted(document):
        value = document[key]
        concept_id = f"source.top_level.{key}.count"
        count = len(value) if isinstance(value, list) else 1
        record_locator = f"$.{key}"
        idempotency_key = _stable_id(
            "observation-key",
            asset_id,
            str(asset_revision),
            record_locator,
            concept_id,
            MAPPING_REVISION,
            "count",
        )
        observation_id = _stable_id("observation", project_id, idempotency_key)
        observations.append(
            Observation(
                project_id=project_id,
                observation_id=observation_id,
                revision=1,
                subject_ref=subject_ref,
                concept_id=concept_id,
                value=TypedValue(value_type="number", value=count, comparator="="),
                event_time=None,
                event_time_precision="unknown",
                available_at=available_at,
                source=SourceLocator(
                    asset_id=asset_id,
                    asset_revision=asset_revision,
                    record_locator=record_locator,
                    value_locator=f"{record_locator}.__count__",
                    parser_version=PARSER_VERSION,
                    locator_type="json_path",
                ),
                validation_status="valid",
                idempotency_key=idempotency_key,
                mapping_revision=MAPPING_REVISION,
            )
        )
    return observations


def _subject_ref(project_id: str, source_namespace: str, document: dict[str, Any]) -> str:
    patient = document.get("patient")
    if isinstance(patient, dict):
        source_key = patient.get("patient_number") or patient.get("patient_id")
        if source_key:
            return _stable_id("subject", project_id, source_namespace, str(source_key))
    return _stable_id("subject", project_id, source_namespace, "unlinked-source-document")


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


if __name__ == "__main__":
    raise SystemExit(main())
