from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from multi_agent.domain.capabilities import AgentFinding
from multi_agent.domain.evidence import EvidenceRef
from multi_agent.domain.observations import ObservationRef


ChallengeCategory = Literal[
    "mapping",
    "scoring",
    "identity",
    "time",
    "unit_platform",
    "imaging_input",
    "interpretation",
    "missing_evidence",
    "reference",
]

ChallengeStatus = Literal["open", "resolved", "partially_resolved", "unresolved", "withdrawn"]
ChallengeSeverity = Literal["low", "medium", "high", "blocking"]
ReviewStatus = Literal["resolved", "partially_resolved", "unresolved", "skipped"]


class CollaborationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FindingRef(CollaborationModel):
    finding_id: str = Field(min_length=1)
    revision: int = Field(default=1, ge=1)


class Challenge(CollaborationModel):
    challenge_id: str = Field(min_length=1)
    target_finding_ref: FindingRef
    category: ChallengeCategory
    evidence_refs: list[ObservationRef | EvidenceRef] = Field(default_factory=list)
    question: str = Field(min_length=1)
    requested_capability: str | None = None
    expected_resolution: str = Field(min_length=1)
    severity: ChallengeSeverity = "medium"
    status: ChallengeStatus = "open"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_actionable_missing_evidence(self) -> "Challenge":
        if not self.evidence_refs and self.category != "missing_evidence":
            raise ValueError("challenges without evidence refs must use missing_evidence category")
        if self.category == "missing_evidence" and "获取" not in self.expected_resolution and "collect" not in self.expected_resolution.lower():
            raise ValueError("missing_evidence challenges must describe what to collect")
        return self


class ReviewTask(CollaborationModel):
    review_task_id: str = Field(min_length=1)
    challenge_id: str = Field(min_length=1)
    requested_capability: str | None = None
    input_snapshot: dict[str, Any] = Field(default_factory=dict)
    completion_conditions: list[str] = Field(default_factory=list)
    dedupe_key: str = Field(min_length=1)
    priority: int = Field(default=100, ge=0)


class ReviewOutcome(CollaborationModel):
    review_task_id: str = Field(min_length=1)
    challenge_id: str = Field(min_length=1)
    status: ReviewStatus
    rationale: str = Field(min_length=1)
    revised_findings: list[AgentFinding] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
