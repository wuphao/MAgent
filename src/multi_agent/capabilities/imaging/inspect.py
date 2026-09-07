from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ImagingAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str
    modality: Literal["MRI", "PET"]
    path: str
    content_hash: str
    exists: bool
    acquisition_date: str | None = None
    tracer: str | None = None
    sequence_identity: str | None = None
    spatial_info: dict = Field(default_factory=dict)
    preprocessing: dict = Field(default_factory=dict)


class ImagingInspector:
    version = "stage07-imaging-inspect/1"

    def inspect(self, path: Path, modality: Literal["MRI", "PET"], **metadata) -> ImagingAsset:
        exists = path.exists()
        digest = _fingerprint(path) if exists else "0" * 64
        return ImagingAsset(
            asset_id=_stable_id("imaging_asset", modality, str(path.resolve()) if exists else str(path), digest),
            modality=modality,
            path=str(path),
            content_hash=digest,
            exists=exists,
            acquisition_date=metadata.get("acquisition_date"),
            tracer=metadata.get("tracer"),
            sequence_identity=metadata.get("sequence_identity"),
            spatial_info=metadata.get("spatial_info") or {},
            preprocessing=metadata.get("preprocessing") or {},
        )


def _fingerprint(path: Path) -> str:
    h = hashlib.sha256()
    if path.is_file():
        h.update(path.read_bytes())
        return h.hexdigest()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        h.update(str(child.relative_to(path)).encode("utf-8"))
        h.update(hashlib.sha256(child.read_bytes()).digest())
    return h.hexdigest()


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"
