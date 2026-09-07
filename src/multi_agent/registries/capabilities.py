from __future__ import annotations

import json
from pathlib import Path

from multi_agent.domain.capabilities import CapabilitySpec


class CapabilityRegistry:
    def __init__(self, specs: dict[str, CapabilitySpec]):
        self._specs = specs

    @classmethod
    def from_directory(cls, path: Path) -> "CapabilityRegistry":
        specs = {}
        for config in sorted(path.glob("*.json")):
            spec = CapabilitySpec.model_validate(json.loads(config.read_text(encoding="utf-8")))
            specs[spec.capability_id] = spec
        return cls(specs)

    def get(self, capability_id: str) -> CapabilitySpec:
        try:
            return self._specs[capability_id]
        except KeyError as exc:
            raise KeyError(f"capability not registered: {capability_id}") from exc

    def available_for_production(self) -> list[CapabilitySpec]:
        return [spec for spec in self._specs.values() if spec.availability == "active"]
