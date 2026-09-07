from __future__ import annotations

import hashlib
import re
from typing import Any

from multi_agent.domain.capabilities import AgentFinding
from multi_agent.domain.challenges import Challenge, FindingRef
from multi_agent.domain.observations import ObservationRef


_DIFF_RE = re.compile(r"computed total (?P<computed>-?\d+(?:\.\d+)?) differs from reported total (?P<reported>-?\d+(?:\.\d+)?)")


class ConflictRuleEngine:
    def inspect(self, findings: list[AgentFinding], artifacts: dict[str, dict[str, Any]]) -> list[Challenge]:
        challenges: list[Challenge] = []
        challenges.extend(self._score_conflicts(findings))
        challenges.extend(self._missing_artifact_refs(findings, artifacts))
        return _dedupe_challenges(challenges)

    def _score_conflicts(self, findings: list[AgentFinding]) -> list[Challenge]:
        challenges: list[Challenge] = []
        for finding in findings:
            match = _DIFF_RE.search(finding.proposition)
            if not match:
                continue
            computed = match.group("computed")
            reported = match.group("reported")
            refs = finding.support_refs or []
            question = (
                f"该发现中工具重算总分 {computed} 与来源报告总分 {reported} 不一致；"
                "需要复核计分定义、条目完整性以及来源字段是否真的是总分。"
            )
            challenges.append(
                Challenge(
                    challenge_id=_stable_id("challenge", finding.finding_id, "scoring", computed, reported),
                    target_finding_ref=FindingRef(finding_id=finding.finding_id),
                    category="scoring",
                    evidence_refs=refs,
                    question=question,
                    requested_capability="xx_v1_score",
                    expected_resolution="复核条目计算、报告字段语义和记录定位；若无法回查，保留冲突并发布限制。",
                    severity="high",
                    metadata={"computed_total": float(computed), "reported_total": float(reported)},
                )
            )
        return challenges

    def _missing_artifact_refs(self, findings: list[AgentFinding], artifacts: dict[str, dict[str, Any]]) -> list[Challenge]:
        challenges: list[Challenge] = []
        for finding in findings:
            missing = [artifact_id for artifact_id in finding.artifact_refs if artifact_id not in artifacts]
            if not missing:
                continue
            challenges.append(
                Challenge(
                    challenge_id=_stable_id("challenge", finding.finding_id, "reference", *missing),
                    target_finding_ref=FindingRef(finding_id=finding.finding_id),
                    category="reference",
                    evidence_refs=finding.support_refs,
                    question=f"该发现引用了不存在的工具产物：{', '.join(missing)}。",
                    expected_resolution="检查任务结果中的 artifact_id 并重新生成可追溯引用。",
                    severity="blocking",
                    metadata={"missing_artifacts": missing},
                )
            )
        return challenges


class CriticAgent:
    name = "CriticAgent"

    def review(self, findings: list[AgentFinding], artifacts: dict[str, dict[str, Any]]) -> list[Challenge]:
        return ConflictRuleEngine().inspect(findings, artifacts)


def _dedupe_challenges(challenges: list[Challenge]) -> list[Challenge]:
    seen: set[str] = set()
    unique: list[Challenge] = []
    for challenge in challenges:
        if challenge.challenge_id in seen:
            continue
        seen.add(challenge.challenge_id)
        unique.append(challenge)
    return unique


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"
