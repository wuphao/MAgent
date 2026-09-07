from __future__ import annotations

from pathlib import Path

from multi_agent.agents.base import TaskContext
from multi_agent.capabilities.imaging import DiamondAdapter
from multi_agent.capabilities.invoker import CapabilityInvoker
from multi_agent.domain.capabilities import AgentResult


class ImagingAgent:
    name = "ImagingAgent"

    def execute(self, context: TaskContext, capability_invoker: CapabilityInvoker) -> AgentResult:
        config = {**context.task_results.get("imaging_config", {}), **context.task_parameters}
        mri_path = Path(config["mri_path"]) if config.get("mri_path") else None
        pet_path = Path(config["pet_path"]) if config.get("pet_path") else None
        result = DiamondAdapter().validate_only(
            mri_path=mri_path,
            pet_path=pet_path,
            checkpoint_hash=config.get("checkpoint_hash"),
            tracer=config.get("tracer"),
        )
        return AgentResult(
            agent_name=self.name,
            status="success" if result["status"] == "compatible" else "capability_unavailable",
            output=result,
            limitations=result.get("limitations") or [],
        )

