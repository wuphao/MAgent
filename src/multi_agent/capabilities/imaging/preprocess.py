from __future__ import annotations

from pathlib import Path

from multi_agent.capabilities.imaging.inspect import ImagingAsset
from multi_agent.capabilities.imaging.validate import CompatibilityResult


class DiaMondPreprocessor:
    version = "stage07-diamond-preprocess/1"

    def prepare(self, mri: ImagingAsset, pet: ImagingAsset, compatibility: CompatibilityResult, output_dir: Path) -> dict:
        if compatibility.status != "compatible" or not compatibility.cache_key:
            return {"status": "capability_unavailable", "message": "DiaMond preprocessing blocked by compatibility validation"}
        output_dir.mkdir(parents=True, exist_ok=True)
        return {"status": "ready", "cache_key": compatibility.cache_key, "output_dir": str(output_dir)}
