from __future__ import annotations

import hashlib

from multi_agent.domain.requests import AnalysisRequest
from multi_agent.domain.tasks import Plan, TaskSpec
from multi_agent.orchestration import goal_templates


class TemplatePlanner:
    def plan(self, request: AnalysisRequest, available_capabilities: set[str], present_concepts: set[str] | None = None) -> Plan:
        present_concepts = present_concepts or set()
        if request.goal == "rwe_patient_summary":
            tasks = goal_templates.rwe_patient_tasks()
        elif request.goal == "source_inventory":
            tasks = goal_templates.source_inventory_tasks()
        elif request.goal == "xx_v1_assessment":
            tasks = goal_templates.xx_v1_assessment_tasks()
        elif request.goal == "longitudinal_xx_v1":
            tasks = goal_templates.longitudinal_tasks()
        elif request.goal == "multi_source_summary":
            tasks = goal_templates.multi_source_summary_tasks()
        else:
            tasks = goal_templates.multimodal_summary_tasks()
        notes: list[str] = []
        planned: list[TaskSpec] = []
        allowed = set(request.allowed_capabilities) if request.allowed_capabilities else available_capabilities
        for task in tasks:
            if task.capability_id and task.capability_id not in available_capabilities:
                notes.append(f"{task.task_id} skipped: capability {task.capability_id} is not registered")
                planned.append(task.model_copy(update={"resource_class": "none", "required": False}))
                continue
            if task.capability_id and task.capability_id not in allowed:
                notes.append(f"{task.task_id} skipped: capability {task.capability_id} is not allowed")
                planned.append(task.model_copy(update={"resource_class": "none", "required": False}))
                continue
            planned.append(task)
        if request.goal == "xx_v1_assessment":
            missing = {"xx_v1.item_1", "xx_v1.item_2", "xx_v1.item_3", "xx_v1.item_4", "xx_v1.total"} - present_concepts
            if missing:
                notes.append("xx_v1_assessment has missing concepts: " + ",".join(sorted(missing)))
        run_id = _stable_id("run", request.project_id, request.goal, request.as_of.isoformat(), request.snapshot_id or "")
        return Plan(run_id=run_id, project_id=request.project_id, goal=request.goal, tasks=planned, notes=notes)


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"

