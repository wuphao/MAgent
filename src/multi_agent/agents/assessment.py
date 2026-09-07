from __future__ import annotations

import hashlib

from multi_agent.agents.base import TaskContext
from multi_agent.capabilities.assessments import AssessmentCapabilities
from multi_agent.capabilities.invoker import CapabilityInvoker
from multi_agent.capabilities.quality import QualityService
from multi_agent.domain.capabilities import AgentFinding, AgentResult
from multi_agent.domain.observations import ObservationRef
from multi_agent.registries.instruments import InstrumentRegistry


class AssessmentAgent:
    name = "AssessmentAgent"

    def __init__(self, instruments: InstrumentRegistry):
        self.instruments = instruments

    def execute(self, context: TaskContext, capability_invoker: CapabilityInvoker) -> AgentResult:
        quality = QualityService().check_goal("xx_v1_assessment", context.observations)
        if quality["status"] != "pass":
            return AgentResult(
                agent_name=self.name,
                status="no_data",
                requested_checks=quality["missing_concepts"],
                limitations=["required assessment observations are missing"],
                output={"quality": quality},
            )
        tool = AssessmentCapabilities(capability_invoker).score_xx_v1(
            context.observations,
            self.instruments.get("xx-v1"),
        )
        if tool.status != "success" or tool.artifact is None:
            return AgentResult(
                agent_name=self.name,
                status="capability_unavailable",
                limitations=[tool.message or tool.error_code or "capability failed"],
            )
        findings = []
        for result in tool.artifact.output["results"]:
            support_refs = [
                ObservationRef(observation_id=ref["observation_id"], revision=ref["revision"])
                for ref in result["item_refs"].values()
            ]
            if result["status"] != "scored":
                findings.append(
                    AgentFinding(
                        finding_id=_finding_id(result["record_locator"], "insufficient"),
                        proposition="XX-v1 total cannot be recomputed because registered items are incomplete.",
                        status="unresolved",
                        support_refs=support_refs,
                        artifact_refs=[tool.artifact.artifact_id],
                        limitations=result["limitations"],
                    )
                )
                continue
            if result["difference"] == 0:
                proposition = f"XX-v1 computed total matches reported total {result['reported_total']} on {result['event_time']}."
                status = "active"
            else:
                proposition = (
                    f"XX-v1 computed total {result['computed_total']} differs from reported total "
                    f"{result['reported_total']} on {result['event_time']}."
                )
                status = "unresolved"
            findings.append(
                AgentFinding(
                    finding_id=_finding_id(proposition),
                    proposition=proposition,
                    status=status,
                    support_refs=support_refs,
                    artifact_refs=[tool.artifact.artifact_id],
                    limitations=result["limitations"],
                )
            )
        return AgentResult(
            agent_name=self.name,
            status="success",
            findings=findings,
            artifact_refs=[tool.artifact.artifact_id],
            output={"artifact": tool.artifact.model_dump(mode="json"), "quality": quality},
        )


def _finding_id(*parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"finding_{digest}"
