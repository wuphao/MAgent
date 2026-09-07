from __future__ import annotations

import hashlib
import mimetypes
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter

from multi_agent.domain.assets import SourceAsset, utc_now
from multi_agent.storage.sqlite import SQLiteStore


SOURCE_ASSET_ADAPTER = TypeAdapter(SourceAsset)


@dataclass(frozen=True)
class AssetManifest:
    project_id: str
    path: Path
    source_namespace: str
    media_type: str | None = None


class AssetRepository:
    def __init__(self, store: SQLiteStore, asset_root: Path):
        self.store = store
        self.asset_root = asset_root
        self.asset_root.mkdir(parents=True, exist_ok=True)
        self.store.migrate()

    def register(self, manifest: AssetManifest) -> SourceAsset:
        source_path = manifest.path.resolve()
        content_hash = _sha256_file(source_path)
        asset_id = f"asset_{content_hash[:16]}"
        media_type = manifest.media_type or mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
        shard = self.asset_root / content_hash[:2]
        final_path = shard / content_hash
        temporary_path = shard / f".{content_hash}.tmp"
        shard.mkdir(parents=True, exist_ok=True)
        if not final_path.exists():
            shutil.copyfile(source_path, temporary_path)
            if _sha256_file(temporary_path) != content_hash:
                temporary_path.unlink(missing_ok=True)
                raise ValueError("copied asset hash does not match source")
            temporary_path.replace(final_path)

        asset = SourceAsset(
            project_id=manifest.project_id,
            asset_id=asset_id,
            revision=1,
            content_hash=content_hash,
            media_type=media_type,
            source_namespace=manifest.source_namespace,
            uri=str(final_path),
            available_at=utc_now(),
            metadata={"original_name": source_path.name},
        )
        with self.store.connect() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO assets (
                        project_id, asset_id, revision, content_hash, media_type,
                        source_namespace, uri, available_at, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        asset.project_id,
                        asset.asset_id,
                        asset.revision,
                        asset.content_hash,
                        asset.media_type,
                        asset.source_namespace,
                        asset.uri,
                        asset.available_at.isoformat(),
                        asset.model_dump_json(),
                    ),
                )
            except sqlite3.IntegrityError:
                row = connection.execute(
                    """
                    SELECT payload_json FROM assets
                    WHERE project_id = ? AND content_hash = ?
                    """,
                    (manifest.project_id, content_hash),
                ).fetchone()
                if row is None:
                    raise
                return SOURCE_ASSET_ADAPTER.validate_json(row["payload_json"])
        return asset

    def get(self, project_id: str, asset_id: str, revision: int = 1) -> SourceAsset:
        with self.store.connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json FROM assets
                WHERE project_id = ? AND asset_id = ? AND revision = ?
                """,
                (project_id, asset_id, revision),
            ).fetchone()
        if row is None:
            raise KeyError(f"asset not found: {project_id}/{asset_id}@{revision}")
        return SOURCE_ASSET_ADAPTER.validate_json(row["payload_json"])


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
