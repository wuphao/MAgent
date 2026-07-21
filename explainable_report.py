from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from llm_client import DeepSeekClient


REPORT_SCHEMA_VERSION = "2.0"


class ExplainableReportBuilder:
    """Build an auditable report; the LLM may explain but never alter evidence."""

    def __init__(self, llm_client: DeepSeekClient | None = None, use_llm: bool = True):
        self.llm_client = llm_client or DeepSeekClient()
        self.use_llm = use_llm

    def build(self, memory: dict[str, Any]) -> dict[str, Any]:
        case = memory["normalized_case"]
        outputs = memory["agent_outputs"]
        evidence_pack = self._evidence_pack(case, outputs)
        fallback = self._fallback_interpretation(memory, evidence_pack)
        interpretation, llm_status = self._llm_interpretation(evidence_pack, fallback)

        return {
            "report_schema_version": REPORT_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "report_type": "single_patient_longitudinal_rwe_explainable_report",
            "patient": evidence_pack["patient"],
            "executive_summary": interpretation["executive_summary"],
            "clinical_interpretation": {
                "phenotype": memory["final_report"]["phenotype_summary"],
                "stage_signal": memory["final_report"]["clinical_stage"],
                "etiology": memory["final_report"]["etiology"],
                "trajectory_explanation": interpretation["trajectory_explanation"],
                "function_explanation": interpretation["function_explanation"],
                "discordance_explanation": interpretation["discordance_explanation"],
            },
            "quantitative_results": evidence_pack["quantitative_results"],
            "five_agent_summary": evidence_pack["five_agent_summary"],
            "evidence": evidence_pack["evidence"],
            "data_quality": evidence_pack["data_quality"],
            "limitations": self._unique(
                evidence_pack["limitations"] + interpretation["additional_limitations"]
            ),
            "recommendations": interpretation["recommendations"],
            "explainability": {
                "method": "确定性评分/统计 + 受约束的大模型解释",
                "llm_status": llm_status,
                "llm_can_modify_source_data": False,
                "traceability": "每项关键发现通过evidence_id关联到form、record_id和date",
                "decision_basis": interpretation["decision_basis"],
                "uncertainty": interpretation["uncertainty"],
            },
            "disclaimer": "仅用于研究数据分析和数据质控，不替代临床诊断或治疗决策。",
        }

    def _evidence_pack(
        self,
        case: dict[str, Any],
        outputs: dict[str, Any],
    ) -> dict[str, Any]:
        cognition = outputs["认知量表Agent"]
        function = outputs["功能分期Agent"]
        longitudinal = outputs["纵向统计Agent"]
        quality = outputs["数据质控Agent"]
        biomarkers = outputs["生物标志物Agent"]
        imaging = outputs["影像Agent"]

        evidence = []
        source_evidence = (
            cognition["evidence"] + function["evidence"]
            + biomarkers["evidence"] + imaging["evidence"]
        )
        for index, item in enumerate(source_evidence, start=1):
            evidence.append({"evidence_id": f"E{index:03d}", **item})

        trajectories = longitudinal["trajectories"]
        for scale, result in trajectories.items():
            if result.get("status") != "analyzed":
                continue
            evidence.append({
                "evidence_id": f"E{len(evidence) + 1:03d}",
                "form": scale,
                "record_id": None,
                "date": result["latest_date"],
                "finding": (
                    f"{scale}: {result['baseline']}→{result['latest']}，"
                    f"变化={result['absolute_change']}，年斜率={result['annual_slope']}，"
                    f"模式={result['pattern']}"
                ),
            })

        patient = case.get("patient") or {}
        demographics = case.get("demographics") or {}
        return {
            "patient": {
                "patient_id": patient.get("patient_id"),
                "patient_number": patient.get("patient_number"),
                "sex": demographics.get("性别"),
                "age_recorded": demographics.get("年龄"),
                "source_condition_label": demographics.get("患病情况"),
                "observation_start": self._date_boundary(case, min),
                "observation_end": self._date_boundary(case, max),
            },
            "quantitative_results": {
                "overall_pattern": longitudinal["overall_pattern"],
                "trajectories": trajectories,
                "score_series": cognition["score_series"],
                "cdr_series": function["cdr_series"],
                "biomarkers": {
                    "plasma": biomarkers["plasma"],
                    "apoe": biomarkers["apoe"],
                    "csf_exploratory": biomarkers["csf_exploratory"],
                    "atn_assessment": biomarkers["atn_assessment"],
                },
                "imaging": {
                    "status": imaging["status"],
                    "mri": imaging["mri"],
                    "pet": imaging["pet"],
                    "diamond_prediction": imaging.get("diamond_prediction"),
                    "prediction_error": imaging.get("prediction_error"),
                },
            },
            # These are the five clinical analysis agents sent to DeepSeek.
            # Data-quality remains a separate guardrail and clinical synthesis
            # is produced only after these results have been interpreted.
            "five_agent_summary": {
                "cognitive": cognition,
                "functional_staging": function,
                "longitudinal": longitudinal,
                "biomarker": biomarkers,
                "imaging": imaging,
            },
            "evidence": evidence,
            "data_quality": {
                "status": quality["status"],
                "issue_count": quality["issue_count"],
                "high_severity_count": quality["high_severity_count"],
                "issues": quality["quality_issues"],
            },
            "functional_status": function["functional_status"],
            "stage_signal": function["clinical_stage_signal"],
            "limitations": self._unique(
                quality["limitations"]
                + cognition["limitations"]
                + function["limitations"]
                + longitudinal["limitations"]
                + biomarkers["limitations"]
                + imaging["limitations"]
            ),
        }

    def _llm_interpretation(
        self,
        evidence_pack: dict[str, Any],
        fallback: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        if not self.use_llm:
            return fallback, "disabled"
        messages = [
            {
                "role": "system",
                "content": (
                    "你是认知障碍真实世界数据报告助手。请综合 cognitive、functional_staging、"
                    "longitudinal、biomarker、imaging 五个Agent的结构化结果，生成一份连贯、"
                    "可解释的中文文本报告。只能解释提供的证据，不能创造数值、"
                    "诊断、日期、病史或生物标志物。不能将MCI-compatible写成确诊MCI；"
                    "不能把APOE风险写成诊断，也不能在A/T/N为indeterminate时推断AD病因。"
                    "引用证据时只能使用存在的evidence_id。输出合法JSON，严格使用指定键。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps({
                    "five_agent_results": evidence_pack["five_agent_summary"],
                    "traceable_evidence": evidence_pack["evidence"],
                    "quantitative_results": evidence_pack["quantitative_results"],
                    "patient_context": evidence_pack["patient"],
                    "data_quality_guardrail": evidence_pack["data_quality"],
                    "known_limitations": evidence_pack["limitations"],
                    "required_schema": {
                        "executive_summary": "string",
                        "trajectory_explanation": "string",
                        "function_explanation": "string",
                        "discordance_explanation": "string",
                        "decision_basis": ["string with evidence_id"],
                        "uncertainty": ["string"],
                        "additional_limitations": ["string"],
                        "recommendations": ["string"],
                    },
                }, ensure_ascii=False),
            },
        ]
        try:
            raw = self.llm_client.chat_json(
                messages,
                temperature=0.0,
                default=None,
                num_predict=1400,
            )
            validated = self._validate_interpretation(raw, evidence_pack, fallback)
            return validated, "success"
        except Exception as exc:
            fallback = dict(fallback)
            fallback["uncertainty"] = self._unique(
                fallback["uncertainty"] + [f"大模型解释不可用，已采用确定性模板：{type(exc).__name__}"]
            )
            return fallback, "fallback"

    def _validate_interpretation(
        self,
        value: Any,
        evidence_pack: dict[str, Any],
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("LLM output is not an object")
        string_fields = (
            "executive_summary", "trajectory_explanation",
            "function_explanation", "discordance_explanation",
        )
        list_fields = (
            "decision_basis", "uncertainty", "additional_limitations", "recommendations",
        )
        result = dict(fallback)
        for field in string_fields:
            if isinstance(value.get(field), str) and value[field].strip():
                result[field] = value[field].strip()
        for field in list_fields:
            if isinstance(value.get(field), list) and all(isinstance(x, str) for x in value[field]):
                result[field] = [x.strip() for x in value[field] if x.strip()]

        valid_ids = {item["evidence_id"] for item in evidence_pack["evidence"]}
        result["decision_basis"] = [
            item for item in result["decision_basis"]
            if not self._mentioned_evidence_ids(item) or self._mentioned_evidence_ids(item) <= valid_ids
        ] or fallback["decision_basis"]
        return result

    @staticmethod
    def _fallback_interpretation(
        memory: dict[str, Any],
        evidence_pack: dict[str, Any],
    ) -> dict[str, Any]:
        report = memory["final_report"]
        trajectories = evidence_pack["quantitative_results"]["trajectories"]
        mmse = trajectories.get("mmse") or {}
        adas = trajectories.get("adas13") or {}
        biomarker_data = evidence_pack["quantitative_results"]["biomarkers"]
        imaging_data = evidence_pack["quantitative_results"]["imaging"]
        by_form: dict[str, list[str]] = {}
        for item in evidence_pack["evidence"]:
            by_form.setdefault(item["form"], []).append(item["evidence_id"])
        decision_basis = []
        if by_form.get("mmse"):
            decision_basis.append("MMSE纵向变化与记忆条目：" + "、".join(by_form["mmse"]))
        if by_form.get("adas13"):
            decision_basis.append("ADAS-Cog 13纵向变化：" + "、".join(by_form["adas13"]))
        if by_form.get("faq"):
            decision_basis.append("FAQ功能条目：" + "、".join(by_form["faq"]))
        return {
            "executive_summary": (
                f"{report['phenotype_summary']}。纵向结果为{report['longitudinal_pattern']}；"
                f"生物标志物状态为{biomarker_data['atn_assessment']['amyloid']}/"
                f"{biomarker_data['atn_assessment']['tau']}/"
                f"{biomarker_data['atn_assessment']['neurodegeneration']}，"
                "当前仍不足以确定阿尔茨海默病病因。"
            ),
            "trajectory_explanation": (
                f"MMSE首末变化{mmse.get('absolute_change', '不可用')}分，"
                f"ADAS-Cog 13首末变化{adas.get('absolute_change', '不可用')}分；"
                "两者方向均提示恶化，但随访过程中存在波动。"
            ),
            "function_explanation": (
                f"功能状态为{evidence_pack['functional_status']}；CDR与FAQ应结合条目级记录解释。"
            ),
            "discordance_explanation": "认知量表下降信号与CDR长期为0并存，FAQ另有条目与总分冲突。",
            "decision_basis": decision_basis or ["当前没有可引用的结构化关键证据"],
            "uncertainty": [
                "缺少教育年限与部分访视年龄",
                biomarker_data["atn_assessment"]["reason"],
                f"影像状态：{imaging_data['status']}，尚无可解释的MRI/PET定量结果",
            ],
            "additional_limitations": [],
            "recommendations": report["recommendations"],
        }

    @staticmethod
    def _date_boundary(case: dict[str, Any], operation: Any) -> str | None:
        dates = [item.get("date") for item in case.get("timeline") or [] if item.get("date")]
        return operation(dates) if dates else None

    @staticmethod
    def _mentioned_evidence_ids(text: str) -> set[str]:
        import re
        return set(re.findall(r"\bE\d{3}\b", text))

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value))


def render_markdown(report: dict[str, Any]) -> str:
    patient = report["patient"]
    clinical = report["clinical_interpretation"]
    lines = [
        "# 单患者纵向RWE可解释性报告",
        "",
        f"- 患者编号：{patient.get('patient_number')}",
        f"- 性别：{patient.get('sex')}；记录年龄：{patient.get('age_recorded')}",
        f"- 观察期：{patient.get('observation_start')} 至 {patient.get('observation_end')}",
        "",
        "## 摘要",
        "",
        report["executive_summary"],
        "",
        "## 临床表型解释",
        "",
        f"- 表型：{clinical['phenotype']}",
        f"- 分期信号：{clinical['stage_signal']['label']}（置信度：{clinical['stage_signal']['confidence']}）",
        f"- 病因：{clinical['etiology']['label']}；{clinical['etiology']['reason']}",
        f"- 纵向解释：{clinical['trajectory_explanation']}",
        f"- 功能解释：{clinical['function_explanation']}",
        f"- 不一致性：{clinical['discordance_explanation']}",
        "",
        "## 量表纵向结果",
        "",
        "| 量表 | 基线 | 末次 | 绝对变化 | 年斜率 | 随访年数 | 模式 |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for scale, item in report["quantitative_results"]["trajectories"].items():
        if item.get("status") == "analyzed":
            lines.append(
                f"| {scale} | {item['baseline']:g} | {item['latest']:g} | "
                f"{item['absolute_change']:g} | {item['annual_slope']:g} | "
                f"{item['followup_years']:g} | {item['pattern']} |"
            )

    biomarkers = report["quantitative_results"]["biomarkers"]
    apoe = biomarkers["apoe"]
    atn = biomarkers["atn_assessment"]
    lines.extend([
        "", "## 生物标志物与遗传风险", "",
        f"- APOE风险修饰：{apoe.get('risk_modifier')}（ε4携带：{apoe.get('epsilon4_carrier')}）",
        f"- A/T/N：A={atn.get('amyloid')}，T={atn.get('tau')}，N={atn.get('neurodegeneration')}",
        f"- 判定限制：{atn.get('reason')}",
        f"- 血浆记录数：{biomarkers['plasma'].get('record_count')}；"
        f"探索性脑脊液记录数：{biomarkers['csf_exploratory'].get('record_count')}",
    ])

    imaging = report["quantitative_results"]["imaging"]
    lines.extend([
        "", "## 影像路径与处理状态", "",
        f"- MRI：{imaging['mri'].get('analysis_status')}；路径：{imaging['mri'].get('path') or '未填写'}",
        f"- PET：{imaging['pet'].get('analysis_status')}；路径：{imaging['pet'].get('path') or '未填写'}",
        f"- DiaMond预测：{(imaging.get('diamond_prediction') or {}).get('pred_label', '尚无结果')}",
        "- DiaMond为研究模型预测；当前报告不生成未经专门定量流程支持的SUVR、Centiloid或分区萎缩结论。",
    ])

    lines.extend(["", "## 可追溯证据", ""])
    for item in report["evidence"]:
        lines.append(
            f"- **{item['evidence_id']}**：{item['finding']} "
            f"（{item.get('form')}，{item.get('date') or '日期不适用'}，"
            f"record_id={item.get('record_id') if item.get('record_id') is not None else '汇总'}）"
        )

    lines.extend(["", "## 数据质量", ""])
    quality = report["data_quality"]
    lines.append(
        f"状态：{quality['status']}；问题数：{quality['issue_count']}；"
        f"高严重度问题：{quality['high_severity_count']}。"
    )
    for item in quality["issues"]:
        lines.append(
            f"- [{item.get('severity')}] {item.get('code', 'SOURCE_WARNING')}：{item['message']} "
            f"（{item.get('visit_date') or '全局'}，record_id={item.get('record_id') or '无'}）"
        )

    lines.extend(["", "## 局限性", ""] + [f"- {x}" for x in report["limitations"]])
    lines.extend(["", "## 建议", ""] + [f"- {x}" for x in report["recommendations"]])
    lines.extend([
        "", "## 生成与解释性说明", "",
        f"- 方法：{report['explainability']['method']}",
        f"- 大模型状态：{report['explainability']['llm_status']}",
        f"- 可追溯性：{report['explainability']['traceability']}",
        "", f"> {report['disclaimer']}", "",
    ])
    return "\n".join(lines)
