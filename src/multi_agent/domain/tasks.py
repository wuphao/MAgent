from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from multi_agent.domain.observations import ObservationRef


TaskState = Literal[
    "pending",
    "ready",
    "running",
    "succeeded",
    "retry_wait",
    "failed",
    "needs_metadata",
    "skipped",
]

DependencyMode = Literal["required_success", "terminal"]


class TaskModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RetryPolicy(TaskModel):
    max_attempts: int = Field(default=1, ge=1)
    retryable_errors: list[str] = Field(default_factory=list)


class TaskDependency(TaskModel):
    task_id: str = Field(min_length=1)
    mode: DependencyMode = "required_success"


class TaskSpec(TaskModel):
    task_id: str = Field(min_length=1)
    capability_id: str | None = None
    capability_version: str | None = None
    agent_name: str | None = None
    input_refs: list[ObservationRef] = Field(default_factory=list)
    depends_on: list[TaskDependency] = Field(default_factory=list)
    required: bool = True
    parameters: dict[str, Any] = Field(default_factory=dict)
    resource_class: Literal["cpu", "io", "model", "none"] = "cpu"
    timeout_seconds: int | None = Field(default=None, ge=1)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    budget: dict[str, int | float | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def runnable_tasks_need_capability_or_agent(self) -> "TaskSpec":
        if self.resource_class != "none" and not (self.capability_id or self.agent_name):
            raise ValueError("runnable tasks require capability_id or agent_name")
        return self


class TaskRecord(TaskModel):
    run_id: str = Field(min_length=1)
    spec: TaskSpec
    state: TaskState = "pending"
    attempts: int = 0
    result: dict[str, Any] | None = None
    error_code: str | None = None
    message: str | None = None


class Plan(TaskModel):
    run_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    tasks: list[TaskSpec]
    notes: list[str] = Field(default_factory=list)


class PlanValidationResult(TaskModel):
    valid: bool
    errors: list[dict[str, Any]] = Field(default_factory=list)
