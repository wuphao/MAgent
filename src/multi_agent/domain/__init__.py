"""Boundary contracts shared by v2 agents, storage, and applications."""

from multi_agent.domain.assets import SourceAsset, SourceLocator
from multi_agent.domain.capabilities import AgentFinding, AgentResult, CapabilitySpec, ToolArtifact, ToolResult
from multi_agent.domain.evidence import Evidence, EvidenceRef, Finding
from multi_agent.domain.instruments import InstrumentSpec
from multi_agent.domain.observations import (
    Observation,
    ObservationRef,
    SubjectLink,
    TypedValue,
)
from multi_agent.domain.runs import Challenge, ReportSnapshot, RunContext, Task
from multi_agent.domain.requests import AnalysisRequest, BudgetLimit
from multi_agent.domain.tasks import Plan, TaskDependency, TaskRecord, TaskSpec

__all__ = [
    "Challenge",
    "AgentFinding",
    "AgentResult",
    "AnalysisRequest",
    "BudgetLimit",
    "CapabilitySpec",
    "Evidence",
    "EvidenceRef",
    "Finding",
    "InstrumentSpec",
    "Observation",
    "ObservationRef",
    "Plan",
    "ReportSnapshot",
    "RunContext",
    "SourceAsset",
    "SourceLocator",
    "SubjectLink",
    "Task",
    "TaskDependency",
    "TaskRecord",
    "TaskSpec",
    "TypedValue",
    "ToolArtifact",
    "ToolResult",
]

from multi_agent.domain.challenges import Challenge, FindingRef, ReviewOutcome, ReviewTask
from multi_agent.domain.reports import ReportCoverage, ReportSnapshot

