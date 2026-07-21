from __future__ import annotations

import re
from typing import Any

from agents.base_agent import BaseAgent


class BiomarkerAgent(BaseAgent):
    """Summarize plasma, APOE and exploratory CSF measurements without inventing cutoffs."""

    name = "生物标志物Agent"

    PLASMA_FIELDS = {
        "ptau217": "血浆磷酸化Tau217浓度(pg/mL)",
        "abeta42": "血浆β淀粉样蛋白42浓度",
        "abeta40": "血浆β淀粉样蛋白40浓度",
        "abeta42_40_ratio": "β淀粉样蛋白42/40比例",
        "ptau217_abeta42_ratio": "磷酸化Tau217 / Aβ42 比值",
        "nfl": "神经丝轻链定量值",
        "gfap": "胶质纤维酸性蛋白定量值",
    }
    CSF_FIELDS = {
        "wu_strem2_raw": "sTREM2 原始浓度",
        "wu_strem2_cv": "sTREM2 变异系数",
        "wu_strem2_corrected": "sTREM2 校正值",
        "msd_strem2_raw": "Haass/MSD sTREM2 原始浓度",
        "msd_strem2_cv": "Haass/MSD sTREM2 变异系数",
        "msd_strem2_corrected": "Haass/MSD sTREM2 校正值",
        "msd_pgrn_raw": "Haass/MSD PGRN 原始浓度",
        "msd_pgrn_cv": "Haass/MSD PGRN 变异系数",
        "msd_pgrn_corrected": "Haass/MSD PGRN 校正值",
    }

    def analyze(self, memory: dict[str, Any]) -> dict[str, Any]:
        forms = memory["normalized_case"].get("forms") or {}
        plasma_records = (forms.get("plasma_biomarkers") or {}).get("records") or []
        apoe_records = (forms.get("apoe_genotype") or {}).get("records") or []
        csf_records = (forms.get("csf_biomarkers") or {}).get("records") or []

        plasma = self._measurement_panel(plasma_records, self.PLASMA_FIELDS)
        csf = self._measurement_panel(csf_records, self.CSF_FIELDS)
        apoe = self._apoe_summary(apoe_records)
        evidence = self._evidence(plasma_records, apoe_records, csf_records)

        available = bool(plasma_records or apoe_records or csf_records)
        atn = {
            "amyloid": "indeterminate",
            "tau": "indeterminate",
            "neurodegeneration": "indeterminate",
            "reason": (
                "已有血浆检测值，但JSON未提供该批次/平台经验证的阳性阈值，不能据此自动判定A/T/N阳性。"
                if plasma_records else
                "没有可用于A/T/N判定的血浆、经典脑脊液或PET定量结果。"
            ),
        }
        return {
            "domain": "biomarkers_and_genetic_risk",
            "status": "available_requires_reference_ranges" if available else "unavailable",
            "plasma": {
                "record_count": len(plasma_records),
                "measurements": plasma,
                "interpretation": "保留原始检测值；未配置检测平台特异性参考范围，因此不自动标记阳性/阴性。",
            },
            "apoe": apoe,
            "csf_exploratory": {
                "record_count": len(csf_records),
                "measurements": csf,
                "interpretation": "sTREM2和PGRN属于探索性小胶质细胞/神经炎症相关指标，不等同于经典CSF Aβ42、p-tau或t-tau。",
            },
            "atn_assessment": atn,
            "etiology_signal": "undetermined",
            "evidence": evidence,
            "limitations": [
                "缺少检测批次对应的数据字典、单位、参考范围和阳性阈值",
                "APOE仅为风险修饰因素，不能单独诊断阿尔茨海默病",
                "当前脑脊液表不含经典Aβ42、p-tau和t-tau组合",
            ] if available else ["没有可用生物标志物记录"],
        }

    @staticmethod
    def _number(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return None

    def _measurement_panel(
        self,
        records: list[dict[str, Any]],
        fields: dict[str, str],
    ) -> dict[str, list[dict[str, Any]]]:
        panel: dict[str, list[dict[str, Any]]] = {key: [] for key in fields}
        for record in records:
            for key, source_field in fields.items():
                value = self._number(record.get(source_field))
                if value is not None:
                    panel[key].append({
                        "date": record.get("visit_date"),
                        "record_id": record.get("record_id"),
                        "value": value,
                        "source_field": source_field,
                    })
        return panel

    def _apoe_summary(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        values = []
        for record in records:
            genotype = str(record.get("APOE基因型") or "").strip()
            if not genotype:
                continue
            e4_count = len(re.findall(r"(?:ε|e)?4", genotype, flags=re.IGNORECASE))
            values.append({
                "date": record.get("visit_date"),
                "record_id": record.get("record_id"),
                "genotype": genotype,
                "epsilon4_allele_count": e4_count,
            })
        max_e4 = max((item["epsilon4_allele_count"] for item in values), default=None)
        return {
            "record_count": len(records),
            "results": values,
            "epsilon4_carrier": None if max_e4 is None else max_e4 > 0,
            "risk_modifier": (
                "APOE ε4风险修饰因素存在" if max_e4 and max_e4 > 0
                else "未检测到APOE ε4" if max_e4 == 0
                else "无法判断"
            ),
            "interpretation": "APOE基因型影响人群风险，但不能单独确定个体病因或诊断。",
        }

    def _evidence(
        self,
        plasma: list[dict[str, Any]],
        apoe: list[dict[str, Any]],
        csf: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []
        for record in plasma:
            present = [label for label in self.PLASMA_FIELDS.values() if self._number(record.get(label)) is not None]
            evidence.append(self.evidence("plasma_biomarkers", record, "血浆检测：" + "、".join(present)))
        for record in apoe:
            genotype = record.get("APOE基因型")
            if genotype:
                evidence.append(self.evidence("apoe_genotype", record, f"APOE基因型={genotype}"))
        for record in csf:
            present = [label for label in self.CSF_FIELDS.values() if self._number(record.get(label)) is not None]
            evidence.append(self.evidence("csf_biomarkers", record, "脑脊液探索性检测：" + "、".join(present)))
        return evidence
