from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InstrumentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InstrumentSpec(InstrumentModel):
    instrument_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    status: Literal["candidate", "active", "suspended"] = "candidate"
    title: str = Field(min_length=1)
    source: dict[str, str]
    item_roles: dict[str, str] = Field(default_factory=dict)
    response_encoding: dict[str, Any] = Field(default_factory=dict)
    scoring: dict[str, Any] = Field(default_factory=dict)
    score_direction: str = Field(min_length=1)
    applicability: dict[str, Any] = Field(default_factory=dict)
    concepts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def active_specs_need_scoring_and_concepts(self) -> "InstrumentSpec":
        if self.status == "active":
            if not self.concepts:
                raise ValueError("active instrument specs must register concepts")
            if self.scoring.get("rule") in (None, "", "rules_missing"):
                raise ValueError("active instrument specs must include verified scoring")
        return self

    @property
    def definition_version(self) -> str:
        return f"{self.instrument_id}:{self.version}"
