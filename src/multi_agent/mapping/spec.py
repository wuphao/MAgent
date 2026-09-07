from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SpecModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceSelector(SpecModel):
    kind: Literal["legacy_json_list", "rows", "nested_json_records"]
    path: str | None = None
    subject_list_path: str | None = None
    records_field: str | None = None


class Binding(SpecModel):
    concept_id: str = Field(min_length=1)
    source_field: str | None = None
    concept_field: str | None = None
    value_field: str | None = None
    transform: str = "parse_number"
    required: bool = True


class MappingSpec(SpecModel):
    mapping_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    source_selector: SourceSelector
    identity_field: str = Field(min_length=1)
    event_time_field: str = Field(min_length=1)
    record_id_field: str = Field(min_length=1)
    bindings: list[Binding] = Field(min_length=1)
    constraints: dict[str, str] = Field(default_factory=dict)
    applicability: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_path(cls, path: Path) -> "MappingSpec":
        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))
