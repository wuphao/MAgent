from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from multi_agent.domain.assets import SCHEMA_VERSION
from multi_agent.domain.evidence import EvidenceRef
from multi_agent.domain.observations import ObservationRef


class CapabilityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CapabilitySpec(CapabilityModel):
    capability_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    availability: Literal["active", "demo", "unavailable"] = "active"
    input_schema: str = Field(min_length=1)
    output_schema: str = Field(min_length=1)
    applicability: dict[str, Any] = Field(default_factory=dict)
    resources: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int | None = Field(default=None, ge=1)
    retryable_errors: list[str] = Field(default_factory=list)


class ToolArtifact(CapabilityModel):
    artifact_id: str = Field(min_length=1)
    capability_id: str = Field(min_length=1)
    capability_version: str = Field(min_length=1)
    status: Literal["success", "unavailable", "not_applicable", "technical_failure"]
    input_refs: list[ObservationRef | EvidenceRef] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    finished_at: datetime
    duration_ms: int = Field(ge=0)
    limitations: list[str] = Field(default_factory=list)


class ToolResult(CapabilityModel):
    status: Literal["success", "unavailable", "not_applicable", "technical_failure"]
    artifact: ToolArtifact | None = None
    error_code: str | None = None
    message: str | None = None


class AgentFinding(CapabilityModel):
    finding_id: str = Field(min_length=1)
    proposition: str = Field(min_length=1)
    status: Literal["active", "unresolved", "not_applicable"]
    support_refs: list[ObservationRef | EvidenceRef] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class AgentResult(CapabilityModel):
    schema_version: str = SCHEMA_VERSION
    agent_name: str = Field(min_length=1)
    status: Literal["success", "no_data", "insufficient_points", "not_comparable", "capability_unavailable"]
    findings: list[AgentFinding] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    requested_checks: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)
