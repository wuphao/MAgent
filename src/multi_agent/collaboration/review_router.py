from __future__ import annotations

import re

from multi_agent.domain.capabilities import AgentFinding
from multi_agent.domain.challenges import Challenge, ReviewOutcome, ReviewTask


class ReviewRouter:
    def review(self, task: ReviewTask, challenge: Challenge, findings: list[AgentFinding]) -> ReviewOutcome:
        if challenge.category == "reference":
            return ReviewOutcome(
                review_task_id=task.review_task_id,
                challenge_id=challenge.challenge_id,
                status="unresolved",
                rationale="发现引用缺失产物，当前运行内没有可替换的稳定产物引用；该命题不得无门禁发布。",
                limitations=["引用缺失，需要重新生成上游任务结果。"],
            )
        if challenge.category == "scoring":
            return self._review_scoring(task, challenge, findings)
        return ReviewOutcome(
            review_task_id=task.review_task_id,
            challenge_id=challenge.challenge_id,
            status="unresolved",
            rationale="阶段06仅对计分和引用错误提供确定性复核，其他语义质询保留为未决限制。",
            limitations=["需要后续能力或人工元数据复核。"],
        )

    def _review_scoring(self, task: ReviewTask, challenge: Challenge, findings: list[AgentFinding]) -> ReviewOutcome:
        target = next((item for item in findings if item.finding_id == challenge.target_finding_ref.finding_id), None)
        if target is None:
            return ReviewOutcome(
                review_task_id=task.review_task_id,
                challenge_id=challenge.challenge_id,
                status="unresolved",
                rationale="目标发现已不存在，无法在当前快照中复核。",
                limitations=["复核目标缺失。"],
            )
        computed = challenge.metadata.get("computed_total")
        reported = challenge.metadata.get("reported_total")
        if computed is None or reported is None:
            return ReviewOutcome(
                review_task_id=task.review_task_id,
                challenge_id=challenge.challenge_id,
                status="unresolved",
                rationale="质询缺少结构化 computed_total/reported_total，不能判断差异来源。",
                limitations=["计分冲突缺少结构化复核输入。"],
            )
        revised = target.model_copy(
            update={
                "finding_id": f"{target.finding_id}_reviewed",
                "status": "unresolved",
                "proposition": (
                    f"XX-v1 total remains disputed: recomputed total {computed:g} differs from "
                    f"source reported total {reported:g}; no source amendment is available in this run."
                ),
                "limitations": list(dict.fromkeys(target.limitations + ["reported and recomputed totals conflict; both values are retained"])) ,
            }
        )
        return ReviewOutcome(
            review_task_id=task.review_task_id,
            challenge_id=challenge.challenge_id,
            status="unresolved",
            rationale="重算结果与来源报告值冲突，但当前没有原始字段定义修订或回查材料；按阶段06规则保留两个值，不任意替换。",
            revised_findings=[revised],
            limitations=["缺少来源字段定义或人工确认，不能断言哪一个总分正确。"],
            metadata={"computed_total": computed, "reported_total": reported, "original_finding_id": target.finding_id},
        )

