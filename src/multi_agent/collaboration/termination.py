from __future__ import annotations

from multi_agent.domain.challenges import ReviewOutcome


class TerminationPolicy:
    def should_stop(self, round_index: int, outcomes: list[ReviewOutcome], max_rounds: int = 2) -> bool:
        if round_index >= max_rounds:
            return True
        if not outcomes:
            return True
        return all(outcome.status in {"unresolved", "skipped"} for outcome in outcomes)
