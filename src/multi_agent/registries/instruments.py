from __future__ import annotations

import json
from pathlib import Path

from multi_agent.domain.instruments import InstrumentSpec


class InstrumentRegistry:
    def __init__(self, specs: dict[str, InstrumentSpec]):
        self._specs = specs

    @classmethod
    def from_directory(cls, path: Path) -> "InstrumentRegistry":
        specs: dict[str, InstrumentSpec] = {}
        for config in sorted(path.glob("*.json")):
            spec = InstrumentSpec.model_validate(json.loads(config.read_text(encoding="utf-8")))
            specs[spec.instrument_id] = spec
        return cls(specs)

    def get(self, instrument_id: str) -> InstrumentSpec:
        try:
            return self._specs[instrument_id]
        except KeyError as exc:
            raise KeyError(f"instrument not registered: {instrument_id}") from exc

    def concepts(self) -> set[str]:
        values: set[str] = set()
        for spec in self._specs.values():
            values.update(spec.concepts)
        return values

    def active_concepts(self) -> set[str]:
        values: set[str] = set()
        for spec in self._specs.values():
            if spec.status == "active":
                values.update(spec.concepts)
        return values

    def all(self) -> list[InstrumentSpec]:
        return list(self._specs.values())
