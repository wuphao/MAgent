from __future__ import annotations

from typing import Any

from multi_agent.domain.reports import ReportSnapshot
from multi_agent.reporting.publisher import ReportPublisher


def build_report_snapshot(*, run_id: str, project_id: str, goal: str, task_results: dict[str, dict[str, Any]], snapshot_id: str | None = None) -> ReportSnapshot:
    return ReportPublisher().build_snapshot(
        run_id=run_id,
        project_id=project_id,
        goal=goal,
        task_results=task_results,
        snapshot_id=snapshot_id,
    )
