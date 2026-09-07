from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from multi_agent.storage.dependencies import DependencyStore
from multi_agent.storage.leases import LeaseStore
from multi_agent.storage.outbox import OutboxStore
from multi_agent.storage.sqlite import SQLiteStore
from multi_agent.storage.tasks import TaskStore


class RecoveryManager:
    def __init__(self, task_store: TaskStore, evidence_store: SQLiteStore):
        self.task_store = task_store
        self.evidence_store = evidence_store
        self.leases = LeaseStore(task_store)
        self.outbox = OutboxStore(evidence_store)

    def recover(self) -> dict[str, Any]:
        expired = self.leases.expire_running()
        pending_events = self.outbox.pending()
        return {
            "status": "recovered",
            "expired_leases_requeued": expired,
            "pending_outbox_events": len(pending_events),
        }


class StagingArtifactCommitter:
    """Idempotent local artifact commit for interrupted file writes."""

    def __init__(self, root: Path):
        self.root = root
        self.staging = root / "staging"
        self.objects = root / "objects"
        self.staging.mkdir(parents=True, exist_ok=True)
        self.objects.mkdir(parents=True, exist_ok=True)

    def stage(self, idempotency_key: str, content: bytes) -> dict[str, str]:
        digest = hashlib.sha256(content).hexdigest()
        path = self.staging / f"{idempotency_key}.{digest}.tmp"
        path.write_bytes(content)
        return {"idempotency_key": idempotency_key, "content_hash": digest, "staging_path": str(path)}

    def commit(self, staged: dict[str, str]) -> dict[str, str]:
        source = Path(staged["staging_path"])
        digest = staged["content_hash"]
        final = self.objects / digest[:2] / digest
        final.parent.mkdir(parents=True, exist_ok=True)
        if not final.exists():
            if not source.exists():
                raise FileNotFoundError(f"staged artifact missing: {source}")
            if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                raise ValueError("staged artifact hash mismatch")
            source.replace(final)
        else:
            source.unlink(missing_ok=True)
        return {"status": "committed", "content_hash": digest, "uri": str(final)}

    def repair_staging(self) -> dict[str, int]:
        repaired = 0
        removed = 0
        for path in list(self.staging.glob("*.tmp")):
            parts = path.name.split(".")
            if len(parts) < 3:
                path.unlink(missing_ok=True)
                removed += 1
                continue
            digest = parts[-2]
            if hashlib.sha256(path.read_bytes()).hexdigest() == digest:
                self.commit({"staging_path": str(path), "content_hash": digest})
                repaired += 1
            else:
                path.unlink(missing_ok=True)
                removed += 1
        return {"repaired": repaired, "removed": removed}
