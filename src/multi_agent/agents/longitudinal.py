from __future__ import annotations

from multi_agent.agents.base import TaskContext
from multi_agent.capabilities.invoker import CapabilityInvoker
from multi_agent.capabilities.longitudinal import LongitudinalCapabilities
from multi_agent.domain.capabilities import AgentFinding, AgentResult


class LongitudinalAgent:
    name = "LongitudinalAgent"

    def execute(self, context: TaskContext, capability_invoker: CapabilityInvoker) -> AgentResult:
        tool = LongitudinalCapabilities(capability_invoker).describe(context.observations, "xx_v1.total")
        if tool.status != "success" or tool.artifact is None:
            return AgentResult(agent_name=self.name, status="capability_unavailable", limitations=[tool.message or "capability failed"])
        groups = tool.artifact.output.get("groups", [])
        if not groups:
            return AgentResult(
                agent_name=self.name,
                status="no_data",
                artifact_refs=[tool.artifact.artifact_id],
                output={"artifact": tool.artifact.model_dump(mode="json")},
            )
        findings = []
        result_status = "success"
        for group in groups:
            if group["status"] != "analyzed":
                result_status = "insufficient_points"
                findings.append(
                    AgentFinding(
                        finding_id=f"finding_longitudinal_{group['subject_ref']}_insufficient",
                        proposition="XX-v1 total has insufficient distinct dates for longitudinal comparison.",
                        status="unresolved",
                        artifact_refs=[tool.artifact.artifact_id],
                    )
                )
                continue
            findings.append(
                AgentFinding(
                    finding_id=f"finding_longitudinal_{group['subject_ref']}_{group['concept_id']}",
                    proposition=(
                        f"XX-v1 total changed by {group['delta']} from {group['first']['date']} "
                        f"to {group['last']['date']} using {group['n_distinct_dates']} distinct dates."
                    ),
                    status="active",
                    artifact_refs=[tool.artifact.artifact_id],
                    limitations=["two time points support descriptive change only"],
                )
            )
        return AgentResult(
            agent_name=self.name,
            status=result_status,
            findings=findings,
            artifact_refs=[tool.artifact.artifact_id],
            output={"artifact": tool.artifact.model_dump(mode="json")},
        )
