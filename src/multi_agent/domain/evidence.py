from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from multi_agent.domain.assets import SCHEMA_VERSION
from multi_agent.domain.observations import ObservationRef


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceRef(ContractModel):
    evidence_id: str = Field(min_length=1)
    revision: int = Field(ge=1)


class Evidence(ContractModel):
    schema_version: str = SCHEMA_VERSION
    project_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    revision: int = Field(default=1, ge=1)
    kind: Literal["observation", "tool_artifact", "source_inventory", "capability_unavailable"]
    observation_refs: list[ObservationRef] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    scope: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[EvidenceRef] = Field(default_factory=list)
    status: Literal["active", "withdrawn", "superseded"] = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_references(self) -> "Evidence":
        if self.kind == "observation" and not self.observation_refs:
            raise ValueError("observation evidence must reference observations")
        return self


class Finding(ContractModel):
    schema_version: str = SCHEMA_VERSION
    project_id: str = Field(min_length=1)
    finding_id: str = Field(min_length=1)
    revision: int = Field(default=1, ge=1)
    proposition: str = Field(min_length=1)
    supports: list[EvidenceRef] = Field(default_factory=list)
    opposes: list[EvidenceRef] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    status: Literal["draft", "active", "unresolved", "withdrawn"] = "draft"
