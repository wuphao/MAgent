from __future__ import annotations

from typing import Any

from agents.base_agent import BaseAgent


class FunctionalStagingAgent(BaseAgent):
    name = "功能分期Agent"

    CDR_SCORES = {
        "正常": 0.0,
        "可疑或极轻度损害": 0.5,
        "轻度损害": 1.0,
        "中度损害": 2.0,
        "重度损害": 3.0,
    }

    def analyze(self, memory: dict[str, Any]) -> dict[str, Any]:
        forms = memory["normalized_case"].get("forms") or {}
        faq_records = (forms.get("faq") or {}).get("records") or []
        cdr_records = (forms.get("cdr") or {}).get("records") or []
        evidence = []
        conflicts = []

        for record in faq_records:
            impaired = [
                key for key, value in record.items()
                if key not in {"record_id", "visit_date", "总分"}
                and value not in {None, "能正常、独立完成"}
            ]
            if impaired:
                evidence.append(self.evidence("faq", record, "功能困难条目：" + "、".join(impaired)))
                if record.get("总分") == 0:
                    conflicts.append(self.evidence("faq", record, "条目存在困难但FAQ总分为0"))

        cdr_series = []
        for record in cdr_records:
            global_raw = record.get("总体评分")
            global_score = self.CDR_SCORES.get(str(global_raw).strip(), global_raw)
            cdrsb = record.get("CDRSB总分")
            if isinstance(global_score, (int, float)):
                cdr_series.append({
                    "date": record.get("visit_date"),
                    "record_id": record.get("record_id"),
                    "global": global_score,
                    "cdr_sb": cdrsb,
                })

        latest_cdr = cdr_series[-1]["global"] if cdr_series else None
        independent = latest_cdr in {0, 0.5}
        if latest_cdr == 0.5 and evidence:
            stage = "MCI-compatible"
        elif latest_cdr == 0:
            stage = "function_preserved"
        elif isinstance(latest_cdr, (int, float)) and latest_cdr >= 1:
            stage = "dementia_range_functional_signal"
        else:
            stage = "indeterminate"
        return {
            "domain": "function_and_stage",
            "functional_status": "基本独立或仅轻微受损" if independent else "存在明显功能受损信号" if stage == "dementia_range_functional_signal" else "无法确定",
            "clinical_stage_signal": stage,
            "cdr_series": cdr_series,
            "evidence": evidence,
            "conflicts": conflicts,
            "limitations": ["临床分期信号不是病因诊断，且FAQ总分冲突需回查源数据"] if conflicts else [],
        }
