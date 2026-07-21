from __future__ import annotations

from typing import Any

from agents.base_agent import BaseAgent


class CognitiveAgent(BaseAgent):
    name = "认知量表Agent"

    SCORE_FIELDS = {
        "mmse": ("MMSE总分", "higher_better"),
        "moca": ("MoCA 汇总得分", "higher_better"),
        "adas13": ("ADAS-Cog 13 项总分", "lower_better"),
        "adas11": ("ADAS-Cog 11 项总分", "lower_better"),
    }

    def analyze(self, memory: dict[str, Any]) -> dict[str, Any]:
        forms = memory["normalized_case"].get("forms") or {}
        series = {
            "mmse": self._series(forms, "mmse", "MMSE总分"),
            "moca": self._series(forms, "moca", "MoCA 汇总得分"),
            "adas13": self._series(forms, "adas", "ADAS-Cog 13 项总分"),
            "adas11": self._series(forms, "adas", "ADAS-Cog 11 项总分"),
        }
        evidence = []
        mmse_records = (forms.get("mmse") or {}).get("records") or []
        for record in mmse_records:
            failed = sum(record.get(f"延迟回忆第{i}个词是否正确") == "否" for i in ("一", "二", "三"))
            if failed >= 2:
                evidence.append(self.evidence("mmse", record, f"3个延迟回忆项目中{failed}个失败"))

        moca_records = (forms.get("moca") or {}).get("records") or []
        for record in moca_records:
            failures = sum(
                record.get(f"无提示回想起{word}") == "没有无提示回忆出来"
                for word in ("face", "velvet", "church", "daisy", "red")
            )
            if failures >= 3:
                evidence.append(self.evidence("moca", record, f"5个无提示回忆项目中{failures}个未回忆"))

        abnormal = self._has_abnormal_signal(series, evidence)
        return {
            "domain": "cognition",
            "status": "abnormal_signal" if abnormal else "no_clear_abnormal_signal",
            "severity": "mild" if abnormal else "none",
            "score_series": series,
            "domain_findings": {"memory": evidence},
            "evidence": evidence,
            "limitations": ["量表分数必须结合教育程度、语言文化背景及临床状态解释"],
        }

    @staticmethod
    def _series(forms: dict[str, Any], form: str, field: str) -> list[dict[str, Any]]:
        result = []
        for record in (forms.get(form) or {}).get("records") or []:
            value = record.get(field)
            if isinstance(value, (int, float)):
                result.append({
                    "date": record.get("visit_date"),
                    "record_id": record.get("record_id"),
                    "score": value,
                })
        return result

    @staticmethod
    def _has_abnormal_signal(series: dict[str, list[dict[str, Any]]], evidence: list[dict[str, Any]]) -> bool:
        mmse = series["mmse"]
        adas = series["adas13"]
        mmse_decline = len(mmse) >= 2 and mmse[-1]["score"] <= mmse[0]["score"] - 2
        adas_worse = len(adas) >= 2 and adas[-1]["score"] >= adas[0]["score"] + 4
        return bool(evidence or mmse_decline or adas_worse)
