from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from multi_agent.collaboration.conflict_rules import CriticAgent
from multi_agent.collaboration.review_policy import ReviewPolicy
from multi_agent.collaboration.review_router import ReviewRouter
from multi_agent.collaboration.synthesis import EvidenceCatalog
from multi_agent.domain.capabilities import AgentFinding, AgentResult
from multi_agent.domain.reports import ReportCoverage, ReportSnapshot
from multi_agent.reporting.validators import PublicationGate


class ReportPublisher:
    def __init__(self, max_review_rounds: int = 2, max_actions_per_round: int = 3):
        self.max_review_rounds = max_review_rounds
        self.max_actions_per_round = max_actions_per_round

    def build_snapshot(self, *, run_id: str, project_id: str, goal: str, task_results: dict[str, dict[str, Any]], snapshot_id: str | None = None) -> ReportSnapshot:
        catalog = EvidenceCatalog(task_results)
        findings = list(catalog.findings)
        challenges = CriticAgent().review(findings, catalog.artifacts)
        review_tasks = ReviewPolicy(self.max_review_rounds, self.max_actions_per_round).select(challenges)
        router = ReviewRouter()
        outcomes = []
        for task in review_tasks:
            challenge = next(item for item in challenges if item.challenge_id == task.challenge_id)
            outcomes.append(router.review(task, challenge, findings))

        withdrawn_ids: list[str] = []
        revised_findings: list[AgentFinding] = []
        for outcome in outcomes:
            original_id = outcome.metadata.get("original_finding_id")
            if isinstance(original_id, str):
                withdrawn_ids.append(original_id)
            revised_findings.extend(outcome.revised_findings)
        if revised_findings:
            withdrawn = set(withdrawn_ids)
            findings = [item for item in findings if item.finding_id not in withdrawn] + revised_findings

        task_count = len(task_results)
        unavailable = {"no_data", "capability_unavailable", "failed", "needs_data", "insufficient_points", "not_comparable"}
        succeeded = sorted(task_id for task_id, result in task_results.items() if result.get("status") not in unavailable | {"skipped"})
        failed = sorted(task_id for task_id, result in task_results.items() if result.get("status") in unavailable)
        skipped = sorted(task_id for task_id, result in task_results.items() if result.get("status") == "skipped")
        limitations = self._limitations(task_results, challenges, outcomes)
        report = ReportSnapshot(
            report_id=_stable_id("report", run_id, project_id, goal),
            run_id=run_id,
            project_id=project_id,
            snapshot_id=snapshot_id,
            generated_at=datetime.now(timezone.utc),
            status="completed_with_limitations" if limitations or challenges else "completed",
            goal=goal,
            findings=findings,
            withdrawn_finding_ids=sorted(set(withdrawn_ids)),
            challenges=challenges,
            review_outcomes=outcomes,
            coverage=ReportCoverage(
                task_count=task_count,
                succeeded_tasks=succeeded,
                failed_tasks=failed,
                skipped_tasks=skipped,
                agent_names=catalog.coverage()["agent_names"],
                unread_evidence_count=catalog.coverage()["unread_evidence_count"],
            ),
            limitations=limitations,
            recommendations=self._recommendations(challenges, outcomes),
            provenance={
                "rules_version": "stage06.rules/1",
                "publisher": "ReportPublisher",
                "rendering": "json_markdown_txt_from_report_snapshot",
            },
        )
        gate = PublicationGate().validate(report, catalog.artifacts)
        if gate["blocking_errors"]:
            report = report.model_copy(update={"status": "failed", "limitations": report.limitations + gate["blocking_errors"]})
        return report

    def _limitations(self, task_results: dict[str, dict[str, Any]], challenges, outcomes) -> list[str]:
        values: list[str] = []
        for result in task_results.values():
            values.extend(result.get("limitations") or [])
        values.extend(outcome.rationale for outcome in outcomes if outcome.status in {"unresolved", "partially_resolved"})
        if challenges:
            values.append(f"发现 {len(challenges)} 个待质询或已质询问题，报告结论按限制发布。")
        return list(dict.fromkeys(item for item in values if item))

    def _recommendations(self, challenges, outcomes) -> list[str]:
        values = ["保留每个命题的证据引用、工具产物版本和复核状态，避免只发布自然语言结论。"]
        if any(challenge.category == "scoring" for challenge in challenges):
            values.append("对计分冲突补充来源字段定义或人工复核记录，再重新运行受影响分支。")
        if any(outcome.status == "unresolved" for outcome in outcomes):
            values.append("未决复核项应进入报告限制区，不能被渲染器改写成已解决。")
        return list(dict.fromkeys(values))


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"

