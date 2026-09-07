from __future__ import annotations

import hashlib

from multi_agent.domain.challenges import Challenge, ReviewTask


_SEVERITY_PRIORITY = {"blocking": 0, "high": 10, "medium": 40, "low": 80}
_CATEGORY_PRIORITY = {"reference": 0, "scoring": 5, "mapping": 10, "time": 15, "missing_evidence": 30}


class ReviewPolicy:
    def __init__(self, max_rounds: int = 2, max_actions_per_round: int = 3):
        self.max_rounds = max_rounds
        self.max_actions_per_round = max_actions_per_round

    def select(self, challenges: list[Challenge], previous_dedupe_keys: set[str] | None = None) -> list[ReviewTask]:
        previous_dedupe_keys = previous_dedupe_keys or set()
        open_challenges = [challenge for challenge in challenges if challenge.status == "open"]
        tasks = [self._task_for(challenge) for challenge in open_challenges]
        tasks = [task for task in tasks if task.dedupe_key not in previous_dedupe_keys]
        tasks.sort(key=lambda item: item.priority)
        return tasks[: self.max_actions_per_round]

    def _task_for(self, challenge: Challenge) -> ReviewTask:
        priority = _SEVERITY_PRIORITY.get(challenge.severity, 100) + _CATEGORY_PRIORITY.get(challenge.category, 50)
        evidence_versions = ",".join(sorted(ref.model_dump_json() for ref in challenge.evidence_refs))
        dedupe_key = _stable_id(
            "review_key",
            challenge.category,
            challenge.target_finding_ref.finding_id,
            evidence_versions,
            challenge.requested_capability or "none",
        )
        return ReviewTask(
            review_task_id=_stable_id("review", challenge.challenge_id, challenge.requested_capability or "none"),
            challenge_id=challenge.challenge_id,
            requested_capability=challenge.requested_capability,
            input_snapshot={"challenge": challenge.model_dump(mode="json")},
            completion_conditions=[challenge.expected_resolution],
            dedupe_key=dedupe_key,
            priority=priority,
        )


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"
