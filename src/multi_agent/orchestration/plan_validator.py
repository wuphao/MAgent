from __future__ import annotations

from multi_agent.domain.requests import AnalysisRequest
from multi_agent.domain.tasks import Plan, PlanValidationResult
from multi_agent.registries.capabilities import CapabilityRegistry


class PlanValidator:
    def __init__(self, capabilities: CapabilityRegistry):
        self.capabilities = capabilities

    def validate(self, request: AnalysisRequest, plan: Plan) -> PlanValidationResult:
        errors: list[dict] = []
        task_ids = [task.task_id for task in plan.tasks]
        task_id_set = set(task_ids)
        if len(task_ids) != len(task_id_set):
            errors.append({"code": "DUPLICATE_TASK_ID", "field_path": "tasks"})
        if plan.project_id != request.project_id:
            errors.append({"code": "PROJECT_MISMATCH", "field_path": "project_id"})
        for index, task in enumerate(plan.tasks):
            if task.capability_id and task.resource_class != "none":
                try:
                    spec = self.capabilities.get(task.capability_id)
                except KeyError:
                    errors.append({"code": "UNKNOWN_CAPABILITY", "field_path": f"tasks[{index}].capability_id"})
                    continue
                if spec.availability != "active":
                    errors.append({"code": "CAPABILITY_NOT_ACTIVE", "field_path": f"tasks[{index}].capability_id"})
                if task.capability_version and task.capability_version != spec.version:
                    errors.append({"code": "CAPABILITY_VERSION_MISMATCH", "field_path": f"tasks[{index}].capability_version"})
            for dep in task.depends_on:
                if dep.task_id not in task_id_set:
                    errors.append({"code": "MISSING_DEPENDENCY", "field_path": f"tasks[{index}].depends_on"})
        for cycle in _cycles(plan):
            errors.append({"code": "CYCLE_DETECTED", "field_path": "tasks", "cycle": cycle})
        call_budget = sum(int(task.budget.get("calls", 0) or 0) for task in plan.tasks)
        token_budget = sum(int(task.budget.get("tokens", 0) or 0) for task in plan.tasks)
        if request.budget.max_calls and call_budget > request.budget.max_calls:
            errors.append({"code": "BUDGET_CALLS_EXCEEDED", "field_path": "budget.max_calls"})
        if request.budget.max_tokens and token_budget > request.budget.max_tokens:
            errors.append({"code": "BUDGET_TOKENS_EXCEEDED", "field_path": "budget.max_tokens"})
        return PlanValidationResult(valid=not errors, errors=errors)


def _cycles(plan: Plan) -> list[list[str]]:
    graph = {task.task_id: [dep.task_id for dep in task.depends_on] for task in plan.tasks}
    cycles: list[list[str]] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, stack: list[str]) -> None:
        if node in visiting:
            cycles.append(stack[stack.index(node):] + [node])
            return
        if node in visited:
            return
        visiting.add(node)
        for parent in graph.get(node, []):
            visit(parent, stack + [parent])
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node, [node])
    return cycles
