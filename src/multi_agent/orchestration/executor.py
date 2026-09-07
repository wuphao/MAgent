from __future__ import annotations

from pathlib import Path

from multi_agent.agents.assessment import AssessmentAgent
from multi_agent.agents.base import TaskContext
from multi_agent.agents.imaging import ImagingAgent
from multi_agent.agents.knowledge import KnowledgeAgent
from multi_agent.agents.laboratory_genetics import LaboratoryGeneticsAgent
from multi_agent.agents.text import TextAgent
from multi_agent.agents.longitudinal import LongitudinalAgent
from multi_agent.agents.synthesis import SynthesisAgent
from multi_agent.capabilities.invoker import CapabilityInvoker
from multi_agent.capabilities.quality import QualityService
from multi_agent.domain.capabilities import AgentResult
from multi_agent.domain.tasks import TaskSpec
from multi_agent.registries.instruments import InstrumentRegistry


class TaskExecutor:
    def __init__(self, instruments_path: Path = Path("configs/instruments")):
        self.instruments = InstrumentRegistry.from_directory(instruments_path)

    def execute(self, task: TaskSpec, context: TaskContext, invoker: CapabilityInvoker) -> AgentResult | dict:
        if task.resource_class == "none":
            return {"status": "skipped", "reason": task.parameters.get("status", "not runnable")}
        if task.agent_name == "QualityService":
            goal = str(task.parameters.get("goal") or context.goal)
            return QualityService().check_goal(goal, context.observations)
        if task.agent_name == "AssessmentAgent":
            return AssessmentAgent(self.instruments).execute(context, invoker)
        if task.agent_name == "LongitudinalAgent":
            return LongitudinalAgent().execute(context, invoker)
        if task.agent_name == "TextAgent":
            return TextAgent().execute(context, invoker)
        if task.agent_name == "KnowledgeAgent":
            return KnowledgeAgent().execute(context, invoker)
        if task.agent_name == "ImagingAgent":
            return ImagingAgent().execute(context, invoker)
        if task.agent_name == "LaboratoryGeneticsAgent":
            return LaboratoryGeneticsAgent().execute(context, invoker)
        if task.agent_name == "SynthesisAgent":
            return SynthesisAgent().execute(context, invoker)
        raise ValueError(f"unknown task executor: {task.agent_name or task.capability_id}")

