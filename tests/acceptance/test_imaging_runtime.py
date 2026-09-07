from __future__ import annotations

import os
from pathlib import Path

import pytest

from multi_agent.capabilities.imaging import DiamondAdapter


pytestmark = pytest.mark.real_imaging


def test_real_diamond_runtime_requires_external_verified_inputs() -> None:
    mri = os.environ.get("STAGE07_REAL_MRI")
    pet = os.environ.get("STAGE07_REAL_PET")
    checkpoint_hash = os.environ.get("STAGE07_DIAMOND_CHECKPOINT_HASH")
    if not (mri and pet and checkpoint_hash):
        pytest.skip("real DiaMond runtime not verified: set STAGE07_REAL_MRI, STAGE07_REAL_PET, and STAGE07_DIAMOND_CHECKPOINT_HASH")
    result = DiamondAdapter().validate_only(Path(mri), Path(pet), checkpoint_hash=checkpoint_hash, tracer="FDG")
    assert result["status"] == "compatible"
