from __future__ import annotations

from typing import Iterable

from multi_agent.domain.observations import Observation


class QualityService:
    REQUIRED_BY_GOAL = {
        "xx_v1_assessment": {"xx_v1.item_1", "xx_v1.item_2", "xx_v1.item_3", "xx_v1.item_4", "xx_v1.total"},
        "longitudinal_xx_v1": {"xx_v1.total"},
    }

    def check_goal(self, goal: str, observations: Iterable[Observation]) -> dict:
        present = {item.concept_id for item in observations}
        required = self.REQUIRED_BY_GOAL.get(goal, set())
        missing = sorted(required - present)
        status = "pass" if not missing else "needs_data"
        return {
            "goal": goal,
            "status": status,
            "missing_concepts": missing,
            "present_required": sorted(required & present),
            "note": "missing unrelated modalities do not fail this goal",
        }
