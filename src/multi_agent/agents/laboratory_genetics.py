from __future__ import annotations

from multi_agent.agents.base import TaskContext
from multi_agent.capabilities.invoker import CapabilityInvoker
from multi_agent.capabilities.laboratory import LaboratoryGeneticsCapabilities
from multi_agent.domain.capabilities import AgentResult


class LaboratoryGeneticsAgent:
    name = "LaboratoryGeneticsAgent"

    def execute(self, context: TaskContext, capability_invoker: CapabilityInvoker) -> AgentResult:
        output = LaboratoryGeneticsCapabilities().summarize_measurements(context.observations)
        return AgentResult(
            agent_name=self.name,
            status="no_data" if output["status"] == "no_data" else "success",
            limitations=output["limitations"],
            output=output,
        )
