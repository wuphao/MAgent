from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from multi_agent.domain.assets import SCHEMA_VERSION
from multi_agent.domain.evidence import EvidenceRef
from multi_agent.domain.observations import ObservationRef


@runtime_checkable
class EvidenceQuery(Protocol):
    def get(self, ref: EvidenceRef, project_scope: str) -> Any:
        ...


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)


class Task(ContractModel):
    schema_version: str = SCHEMA_VERSION
    task_id: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    required_capability: str | None = None
    input_refs: list[EvidenceRef | ObservationRef] = Field(default_factory=list)
    status: Literal["pending", "ready", "succeeded", "failed", "capability_unavailable"] = "pending"


class Challenge(ContractModel):
    schema_version: str = SCHEMA_VERSION
    challenge_id: str = Field(min_length=1)
    target_ref: EvidenceRef
    category: Literal["conflict", "missing_source", "cross_subject", "semantic_review"]
    question: str = Field(min_length=1)
    status: Literal["open", "resolved", "unresolved"] = "open"


class ReportSnapshot(ContractModel):
    schema_version: str = SCHEMA_VERSION
    project_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    member_refs: list[EvidenceRef | ObservationRef]
    versions: dict[str, str] = Field(default_factory=dict)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone aware")
        return value


class RunContext(ContractModel):
    schema_version: str = SCHEMA_VERSION
    project_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    as_of: datetime
    config_versions: dict[str, str] = Field(default_factory=dict)
    evidence_query: EvidenceQuery = Field(exclude=True)

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must be timezone aware")
        return value
