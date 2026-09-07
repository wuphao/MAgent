from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from multi_agent.capabilities.invoker import CapabilityInvoker
from multi_agent.domain.capabilities import AgentResult
from multi_agent.domain.observations import Observation


class TaskContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    observations: list[Observation]
    run_id: str | None = None
    snapshot_id: str | None = None
    task_results: dict[str, dict] = Field(default_factory=dict)
    task_parameters: dict[str, Any] = Field(default_factory=dict)


class Agent(Protocol):
    name: str

    def execute(self, context: TaskContext, capability_invoker: CapabilityInvoker) -> AgentResult:
        ...




