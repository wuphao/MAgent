from __future__ import annotations

import hashlib
from pydantic import BaseModel, ConfigDict, Field

from multi_agent.capabilities.imaging.inspect import ImagingAsset


class CompatibilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    reasons: list[str] = Field(default_factory=list)
    cache_key: str | None = None
    required_model: str = "DiaMond"
    validated_requirements: list[str] = Field(default_factory=list)
    unknown_requirements: list[str] = Field(default_factory=list)


class DiaMondCompatibilityValidator:
    version = "stage07-diamond-compatibility/1"

    def validate(self, mri: ImagingAsset | None, pet: ImagingAsset | None, checkpoint_hash: str | None = None) -> CompatibilityResult:
        reasons: list[str] = []
        unknown: list[str] = []
        if mri is None or not mri.exists:
            reasons.append("MRI asset is missing")
        if pet is None or not pet.exists:
            reasons.append("PET asset is missing")
        if pet is not None and pet.tracer not in {"FDG", "18F-FDG"}:
            reasons.append("PET tracer is missing or not confirmed as FDG")
        if mri is not None and not mri.sequence_identity:
            unknown.append("MRI sequence identity is not confirmed")
        if checkpoint_hash is None:
            reasons.append("DiaMond checkpoint hash is unavailable")
        if reasons or unknown:
            return CompatibilityResult(status="incompatible", reasons=reasons, unknown_requirements=unknown)
        cache_key = _stable_id("diamond_cache", mri.content_hash, pet.content_hash, checkpoint_hash or "", self.version)
        return CompatibilityResult(
            status="compatible",
            cache_key=cache_key,
            validated_requirements=["MRI asset exists", "FDG PET asset exists", "checkpoint hash provided"],
        )


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"
