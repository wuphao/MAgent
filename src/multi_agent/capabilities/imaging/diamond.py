from __future__ import annotations

from pathlib import Path

from multi_agent.capabilities.imaging.inspect import ImagingInspector
from multi_agent.capabilities.imaging.validate import DiaMondCompatibilityValidator


class DiamondAdapter:
    version = "stage07-diamond-adapter/1"

    def validate_only(self, mri_path: Path | None, pet_path: Path | None, checkpoint_hash: str | None = None, tracer: str | None = None) -> dict:
        inspector = ImagingInspector()
        mri = inspector.inspect(mri_path, "MRI") if mri_path else None
        pet = inspector.inspect(pet_path, "PET", tracer=tracer) if pet_path else None
        result = DiaMondCompatibilityValidator().validate(mri, pet, checkpoint_hash=checkpoint_hash)
        return {
            "status": result.status,
            "mri": mri.model_dump(mode="json") if mri else None,
            "pet": pet.model_dump(mode="json") if pet else None,
            "compatibility": result.model_dump(mode="json"),
            "limitations": [] if result.status == "compatible" else ["real DiaMond prediction is not executed until compatibility is proven"],
        }
