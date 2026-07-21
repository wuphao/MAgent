from __future__ import annotations

from typing import Any

from agents.base_agent import BaseAgent


class ClinicalSynthesisAgent(BaseAgent):
    name = "临床整合Agent"

    def analyze(self, memory: dict[str, Any]) -> dict[str, Any]:
        outputs = memory["agent_outputs"]
        quality = outputs["数据质控Agent"]
        cognition = outputs["认知量表Agent"]
        function = outputs["功能分期Agent"]
        longitudinal = outputs["纵向统计Agent"]
        biomarkers = outputs["生物标志物Agent"]
        imaging = outputs["影像Agent"]

        abnormal = cognition["status"] == "abnormal_signal"
        function_preserved = function["functional_status"] == "基本独立或仅轻微受损"
        if abnormal and function_preserved:
            phenotype = "长期认知下降信号，日常功能总体保存或仅轻微受损"
            stage = "MCI-compatible"
            confidence = "medium" if quality["high_severity_count"] else "high"
        elif abnormal:
            phenotype = "存在认知异常信号，并可能伴随功能受损"
            stage = function["clinical_stage_signal"]
            confidence = "low" if quality["high_severity_count"] else "medium"
        else:
            phenotype = "当前结构化数据未显示明确认知下降信号"
            stage = "indeterminate"
            confidence = "low"

        apoe = biomarkers["apoe"]
        has_biomarkers = biomarkers["status"] != "unavailable"
        prediction_completed = imaging["status"] == "prediction_completed"
        etiology_reasons = []
        if has_biomarkers:
            etiology_reasons.append("已获得血浆/APOE/探索性脑脊液数据")
        if apoe.get("epsilon4_carrier") is True:
            etiology_reasons.append("存在APOE ε4风险修饰因素")
        elif apoe.get("epsilon4_carrier") is False:
            etiology_reasons.append("未检测到APOE ε4，但这不能排除AD病理")
        if biomarkers["atn_assessment"]["amyloid"] == "indeterminate":
            etiology_reasons.append("缺少平台特异性阈值，无法自动判定A/T/N状态")
        if prediction_completed:
            prediction = imaging.get("diamond_prediction") or {}
            etiology_reasons.append(
                f"DiaMond研究模型预测={prediction.get('pred_label')}，置信度={prediction.get('confidence')}"
            )
        elif imaging["status"] == "prediction_failed":
            etiology_reasons.append("MRI/PET路径已提供，但DiaMond预测执行失败")
        else:
            etiology_reasons.append("MRI/PET路径不完整或尚未提供")

        key_evidence = (
            cognition["evidence"]
            + function["evidence"]
            + biomarkers["evidence"]
            + imaging["evidence"]
        )[:20]
        recommendations = self._recommendations(quality, biomarkers, imaging)
        deterministic = {
            "phenotype_summary": phenotype,
            "clinical_stage": {
                "label": stage,
                "confidence": confidence,
                "note": "这是数据驱动的临床表型信号，不是正式诊断",
            },
            "etiology": {
                "label": "undetermined",
                "ad_biology_status": biomarkers["atn_assessment"],
                "apoe_risk_modifier": apoe.get("risk_modifier"),
                "reason": "；".join(etiology_reasons),
            },
            "longitudinal_pattern": longitudinal["overall_pattern"],
            "biomarker_summary": {
                "status": biomarkers["status"],
                "plasma_record_count": biomarkers["plasma"]["record_count"],
                "apoe": apoe,
                "csf_record_count": biomarkers["csf_exploratory"]["record_count"],
            },
            "imaging_summary": {
                "status": imaging["status"],
                "mri": imaging["mri"],
                "pet": imaging["pet"],
            },
            "key_evidence": key_evidence,
            "conflicting_evidence": function["conflicts"],
            "data_quality": {
                "status": quality["status"],
                "issue_count": quality["issue_count"],
                "important_limitations": quality["limitations"],
            },
            "recommendations": recommendations,
            "disclaimer": "仅用于研究数据分析和质控，不替代临床诊断。",
        }
        return deterministic

    @staticmethod
    def _recommendations(
        quality: dict[str, Any],
        biomarkers: dict[str, Any],
        imaging: dict[str, Any],
    ) -> list[str]:
        recommendations = []
        if quality["issue_count"]:
            recommendations.append("回查并修正量表缺失总分、条目-总分冲突及缺失日期")
        if biomarkers["status"] == "available_requires_reference_ranges":
            recommendations.append("补充Fujirebio/Quanterix检测批次的数据字典、单位和验证阈值后再判断A/T/N状态")
        if imaging["status"] == "awaiting_manual_paths":
            recommendations.append("在JSON的imaging.mri.path与imaging.pet.path中填写影像路径")
        elif imaging["status"] == "prediction_failed":
            recommendations.append("检查MRI/PET路径、DICOM序列、DiaMond环境与checkpoint后重新运行预测")
        elif imaging["status"] == "prediction_completed":
            recommendations.append("人工复核DiaMond输入序列、预处理一致性和预测概率，不将模型输出直接作为诊断")
        else:
            recommendations.append("补齐有效MRI和PET路径后运行DiaMond多模态预测")
        recommendations.append("结合教育年限、合并症、用药、临床诊断来源和随访背景进行人工复核")
        return recommendations
