from __future__ import annotations

from collections import Counter
from typing import Any

from multi_agent.domain.capabilities import AgentFinding, AgentResult


class EvidenceCatalog:
    """Index task outputs without truncating late evidence."""

    def __init__(self, task_results: dict[str, dict[str, Any]]):
        self.task_results = task_results
        self.artifacts = self._collect_artifacts(task_results)
        self.findings = self._collect_findings(task_results)

    def coverage(self) -> dict[str, Any]:
        agents = sorted({result.get("agent_name") for result in self.task_results.values() if result.get("agent_name")})
        return {
            "task_result_count": len(self.task_results),
            "artifact_count": len(self.artifacts),
            "finding_count": len(self.findings),
            "agent_names": agents,
            "unread_evidence_count": 0,
        }

    def artifact(self, artifact_id: str) -> dict[str, Any] | None:
        return self.artifacts.get(artifact_id)

    def _collect_artifacts(self, task_results: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        artifacts: dict[str, dict[str, Any]] = {}
        for result in task_results.values():
            output = result.get("output") or {}
            artifact = output.get("artifact")
            if isinstance(artifact, dict) and artifact.get("artifact_id"):
                artifacts[artifact["artifact_id"]] = artifact
        return artifacts

    def _collect_findings(self, task_results: dict[str, dict[str, Any]]) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        for result in task_results.values():
            for item in result.get("findings") or []:
                findings.append(AgentFinding.model_validate(item))
        return findings


def collect_agent_results(task_results: dict[str, dict[str, Any]]) -> list[AgentResult]:
    values: list[AgentResult] = []
    for result in task_results.values():
        if isinstance(result, dict) and result.get("agent_name"):
            values.append(AgentResult.model_validate(result))
    return values


def independent_support_counts(findings: list[AgentFinding]) -> dict[str, int]:
    """Count shared ancestors once; repeated role citation should not inflate support."""

    counts: dict[str, int] = {}
    for finding in findings:
        keys = Counter(f"{type(ref).__name__}:{ref.model_dump_json()}" for ref in finding.support_refs)
        counts[finding.finding_id] = len(keys)
    return counts
