from __future__ import annotations

from pathlib import Path

from multi_agent.capabilities.imaging import DiaMondCompatibilityValidator, DiamondAdapter, ImagingInspector


def test_imaging_missing_or_unknown_inputs_are_rejected(tmp_path: Path) -> None:
    missing = tmp_path / "missing.nii.gz"
    result = DiamondAdapter().validate_only(mri_path=missing, pet_path=None, checkpoint_hash=None)

    assert result["status"] == "incompatible"
    assert "MRI asset is missing" in result["compatibility"]["reasons"]
    assert "PET asset is missing" in result["compatibility"]["reasons"]
    assert result["limitations"] == ["real DiaMond prediction is not executed until compatibility is proven"]


def test_cache_key_changes_when_file_content_changes(tmp_path: Path) -> None:
    mri = tmp_path / "mri.nii"
    pet = tmp_path / "pet.nii"
    mri.write_bytes(b"mri-v1")
    pet.write_bytes(b"pet-v1")
    inspector = ImagingInspector()
    first = DiaMondCompatibilityValidator().validate(
        inspector.inspect(mri, "MRI", sequence_identity="T1"),
        inspector.inspect(pet, "PET", tracer="FDG"),
        checkpoint_hash="checkpoint-v1",
    )
    mri.write_bytes(b"mri-v2")
    second = DiaMondCompatibilityValidator().validate(
        inspector.inspect(mri, "MRI", sequence_identity="T1"),
        inspector.inspect(pet, "PET", tracer="FDG"),
        checkpoint_hash="checkpoint-v1",
    )

    assert first.status == "compatible"
    assert second.status == "compatible"
    assert first.cache_key != second.cache_key


def test_path_exists_is_not_enough_for_diamond_compatibility(tmp_path: Path) -> None:
    mri = tmp_path / "mri.nii"
    pet = tmp_path / "pet.nii"
    mri.write_bytes(b"mri")
    pet.write_bytes(b"pet")
    inspector = ImagingInspector()

    result = DiaMondCompatibilityValidator().validate(
        inspector.inspect(mri, "MRI"),
        inspector.inspect(pet, "PET"),
        checkpoint_hash="checkpoint-v1",
    )

    assert result.status == "incompatible"
    assert "PET tracer is missing or not confirmed as FDG" in result.reasons
    assert "MRI sequence identity is not confirmed" in result.unknown_requirements
