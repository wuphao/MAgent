from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from multi_agent.mapping.spec import MappingSpec


class CandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MetadataQuestion(CandidateModel):
    question_id: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    candidate_meaning: str = Field(min_length=1)
    required_material: str = Field(min_length=1)
    impact: str = Field(min_length=1)


class BindingRationale(CandidateModel):
    concept_id: str = Field(min_length=1)
    source_field: str | None = None
    rationale: str = Field(min_length=1)
    alternatives: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)


class MappingCandidate(CandidateModel):
    candidate_id: str = Field(min_length=1)
    status: Literal["proposed", "invalid", "needs_metadata"] = "proposed"
    spec: MappingSpec | None = None
    rationales: list[BindingRationale] = Field(default_factory=list)
    questions: list[MetadataQuestion] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    model_name: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
