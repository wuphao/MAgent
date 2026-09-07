from __future__ import annotations

from dataclasses import dataclass

from multi_agent.storage.dependencies import DependencyStore


AFFECTED_TASKS_BY_KIND = {
    "mapping": {"assessment_xx_v1", "longitudinal_xx_v1", "synthesis_report"},
    "instrument": {"assessment_xx_v1", "synthesis_report"},
    "knowledge": {"knowledge_candidates", "synthesis_report"},
    "model_weight": {"diamond_compatibility", "synthesis_report"},
    "prompt": {"synthesis_report"},
}


@dataclass(frozen=True)
class IncrementalPlan:
    changed_ref: tuple[str, str, str]
    affected_refs: list[dict[str, str]]
    task_ids: list[str]


class IncrementalPlanner:
    def __init__(self, dependencies: DependencyStore):
        self.dependencies = dependencies

    def plan_change(self, project_id: str, changed_ref: tuple[str, str, str]) -> IncrementalPlan:
        affected_refs = self.dependencies.affected_closure(project_id, changed_ref)
        task_ids = set(AFFECTED_TASKS_BY_KIND.get(changed_ref[0], set()))
        for ref in affected_refs:
            task_ids.update(AFFECTED_TASKS_BY_KIND.get(ref["kind"], set()))
        return IncrementalPlan(changed_ref=changed_ref, affected_refs=affected_refs, task_ids=sorted(task_ids))
