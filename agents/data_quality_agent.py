from __future__ import annotations

from copy import deepcopy
from typing import Any

from agents.base_agent import BaseAgent


class DataQualityAgent(BaseAgent):
    name = "数据质控Agent"

    REQUIRED_FORMS = ("moca", "mmse", "faq", "cdr", "adas")

    def analyze(self, memory: dict[str, Any]) -> dict[str, Any]:
        raw = memory["raw_case"]
        normalized = deepcopy(raw)
        forms = normalized.get("forms") or {}
        issues = []
        for source_warning in (normalized.get("data_quality") or {}).get("warnings") or []:
            issue = dict(source_warning)
            issue.setdefault("code", "SOURCE_WARNING")
            issue.setdefault("severity", "low")
            issue.setdefault("form", "unknown")
            issue.setdefault("record_id", None)
            issue.setdefault("visit_date", issue.get("date"))
            issue.setdefault("message", "来源数据警告")
            issues.append(issue)

        for form in self.REQUIRED_FORMS:
            if not (forms.get(form) or {}).get("records"):
                issues.append(self._issue("MISSING_FORM", "high", form, "量表无记录"))

        self._check_dates(forms, issues)
        self._check_moca(forms, issues)
        self._check_faq(forms, issues)
        self._check_demographics(normalized.get("demographics") or {}, issues)

        seen = set()
        deduplicated = []
        for issue in issues:
            key = (issue.get("code"), issue.get("form"), issue.get("record_id"), issue.get("message"))
            if key not in seen:
                seen.add(key)
                deduplicated.append(issue)

        normalized.setdefault("data_quality", {})["warnings"] = deduplicated
        memory["normalized_case"] = normalized
        high = sum(item.get("severity") == "high" for item in deduplicated)
        return {
            "status": "fail" if high >= 3 else "warning" if deduplicated else "pass",
            "issue_count": len(deduplicated),
            "high_severity_count": high,
            "quality_issues": deduplicated,
            "limitations": [item["message"] for item in deduplicated if item.get("severity") in {"high", "medium"}],
        }

    def _check_dates(self, forms: dict[str, Any], issues: list[dict[str, Any]]) -> None:
        for form, payload in forms.items():
            if form == "dicom_basic_info" or not payload.get("source_date_field"):
                continue
            seen = set()
            for record in payload.get("records") or []:
                date = record.get("visit_date")
                if not date:
                    severity = "low" if form in {"apoe_genotype", "plasma_biomarkers", "csf_biomarkers"} else "high"
                    issues.append(self._issue("MISSING_VISIT_DATE", severity, form, "记录缺少日期，无法进入统一时间线", record))
                signature = (date, tuple(sorted((k, str(v)) for k, v in record.items() if k != "record_id")))
                if signature in seen:
                    issues.append(self._issue("DUPLICATE_RECORD", "medium", form, "发现内容完全相同的重复记录", record))
                seen.add(signature)

    def _check_moca(self, forms: dict[str, Any], issues: list[dict[str, Any]]) -> None:
        for record in (forms.get("moca") or {}).get("records") or []:
            if not isinstance(record.get("MoCA 汇总得分"), (int, float)):
                issues.append(self._issue(
                    "MISSING_MOCA_TOTAL", "high", "moca",
                    "MoCA缺少汇总分；当前仅分析条目，不自动猜测教育校正后的总分", record,
                ))

    def _check_faq(self, forms: dict[str, Any], issues: list[dict[str, Any]]) -> None:
        normal = "能正常、独立完成"
        for record in (forms.get("faq") or {}).get("records") or []:
            items = [
                value for key, value in record.items()
                if key not in {"record_id", "visit_date", "总分"} and value is not None
            ]
            if record.get("总分") == 0 and any(value != normal for value in items):
                issues.append(self._issue(
                    "FAQ_TOTAL_ITEM_CONFLICT", "high", "faq",
                    "FAQ总分为0，但至少一个条目记录了功能困难", record,
                ))

    def _check_demographics(self, demographics: dict[str, Any], issues: list[dict[str, Any]]) -> None:
        if demographics.get("出生日期") is None and demographics.get("年龄") is not None:
            issues.append(self._issue(
                "AGE_REFERENCE_DATE_UNKNOWN", "medium", "demographics",
                "仅有年龄而无出生日期或年龄参考日期，不能计算各访视时年龄",
            ))

    @staticmethod
    def _issue(
        code: str,
        severity: str,
        form: str,
        message: str,
        record: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = record or {}
        return {
            "code": code,
            "severity": severity,
            "form": form,
            "record_id": record.get("record_id"),
            "visit_date": record.get("visit_date"),
            "message": message,
        }
