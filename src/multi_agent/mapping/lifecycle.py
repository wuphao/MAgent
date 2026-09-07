from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from multi_agent.mapping.candidate import MappingCandidate
from multi_agent.mapping.semantic_validation import SemanticValidationReport


@dataclass(frozen=True)
class ActivationPolicy:
    name: str = "stage03-default"
    require_structural_valid: bool = True
    require_semantic_valid: bool = True
    require_candidate_spec: bool = True


@dataclass
class MappingLifecycleRecord:
    candidate: MappingCandidate
    state: Literal["proposed", "validated", "active", "needs_metadata", "suspended", "rejected"]
    semantic_report: SemanticValidationReport | None = None
    activation_policy: str | None = None
    events: list[dict[str, str]] = field(default_factory=list)


class MappingLifecycleService:
    def __init__(self, policy: ActivationPolicy | None = None):
        self.policy = policy or ActivationPolicy()

    def submit(self, candidate: MappingCandidate) -> MappingLifecycleRecord:
        state = "proposed" if candidate.status == "proposed" else candidate.status
        if state == "invalid":
            state = "rejected"
        return MappingLifecycleRecord(
            candidate=candidate,
            state=state,
            events=[{"event": "submitted", "state": state}],
        )

    def validate(
        self,
        record: MappingLifecycleRecord,
        semantic_report: SemanticValidationReport,
    ) -> MappingLifecycleRecord:
        record.semantic_report = semantic_report
        if semantic_report.status == "valid":
            record.state = "validated"
        elif semantic_report.status == "needs_metadata":
            record.state = "needs_metadata"
        else:
            record.state = "rejected"
        record.events.append({"event": "semantic_validated", "state": record.state})
        return record

    def activate(self, record: MappingLifecycleRecord) -> MappingLifecycleRecord:
        if not self._can_activate(record):
            record.events.append({"event": "activation_blocked", "state": record.state})
            return record
        record.state = "active"
        record.activation_policy = self.policy.name
        record.events.append({"event": "activated", "state": "active", "policy": self.policy.name})
        return record

    def suspend(self, record: MappingLifecycleRecord, reason: str) -> MappingLifecycleRecord:
        record.state = "suspended"
        record.events.append({"event": "suspended", "state": "suspended", "reason": reason})
        return record

    def _can_activate(self, record: MappingLifecycleRecord) -> bool:
        if self.policy.require_candidate_spec and record.candidate.spec is None:
            return False
        if self.policy.require_semantic_valid and (
            record.semantic_report is None or record.semantic_report.status != "valid"
        ):
            return False
        return record.state == "validated"
