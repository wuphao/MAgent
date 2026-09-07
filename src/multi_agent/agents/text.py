from __future__ import annotations

from multi_agent.agents.base import TaskContext
from multi_agent.capabilities.invoker import CapabilityInvoker
from multi_agent.domain.capabilities import AgentFinding, AgentResult
from multi_agent.domain.observations import ObservationRef


class TextAgent:
    name = "TextAgent"

    def execute(self, context: TaskContext, capability_invoker: CapabilityInvoker) -> AgentResult:
        text_observations = [item for item in context.observations if item.concept_id.startswith("text.")]
        if not text_observations:
            return AgentResult(agent_name=self.name, status="no_data", limitations=["no text observations are available"])
        findings: list[AgentFinding] = []
        for item in text_observations:
            source_text = str(item.metadata.get("source_text") or "")
            finding_status = "unresolved" if item.validation_status != "valid" else "active"
            findings.append(
                AgentFinding(
                    finding_id=f"finding_{item.observation_id}",
                    proposition=(
                        f"Text extraction for {item.concept_id} is {item.value.value}; "
                        f"experiencer={item.metadata.get('experiencer')}, negated={item.metadata.get('negated')}."
                    ),
                    status=finding_status,
                    support_refs=[ObservationRef(observation_id=item.observation_id, revision=item.revision)],
                    limitations=["text semantics require review"] if finding_status == "unresolved" else [],
                )
            )
        return AgentResult(agent_name=self.name, status="success", findings=findings)

