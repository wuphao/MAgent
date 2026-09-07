from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from multi_agent.domain.capabilities import AgentFinding
from multi_agent.domain.challenges import Challenge, ReviewOutcome


ReportStatus = Literal["completed", "completed_with_limitations", "needs_metadata", "failed"]


class ReportingModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReportCoverage(ReportingModel):
    task_count: int = Field(ge=0)
    succeeded_tasks: list[str] = Field(default_factory=list)
    failed_tasks: list[str] = Field(default_factory=list)
    skipped_tasks: list[str] = Field(default_factory=list)
    agent_names: list[str] = Field(default_factory=list)
    unread_evidence_count: int = Field(default=0, ge=0)


class ReportSnapshot(ReportingModel):
    schema_version: str = "stage06.report_snapshot/1"
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    snapshot_id: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: ReportStatus
    goal: str = Field(min_length=1)
    findings: list[AgentFinding] = Field(default_factory=list)
    withdrawn_finding_ids: list[str] = Field(default_factory=list)
    challenges: list[Challenge] = Field(default_factory=list)
    review_outcomes: list[ReviewOutcome] = Field(default_factory=list)
    coverage: ReportCoverage
    limitations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
