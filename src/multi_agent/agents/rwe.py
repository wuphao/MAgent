"""Source-grounded descriptions of real RWE forms, separate from XX-v1 scoring."""
from __future__ import annotations

from collections import defaultdict

from multi_agent.agents.base import TaskContext
from multi_agent.domain.capabilities import AgentFinding, AgentResult
from multi_agent.domain.observations import ObservationRef
from multi_agent.ingestion.rwe_patient import SCORE_FIELDS, stable_id


def ref(obs):
    return ObservationRef(observation_id=obs.observation_id, revision=obs.revision)


def finding(name, text, items, *, unresolved=False, limitations=None):
    return AgentFinding(finding_id=stable_id("finding", name, text, *[o.observation_id for o in items]),
        proposition=text, status="unresolved" if unresolved else "active",
        support_refs=[ref(o) for o in items], limitations=limitations or [])


class RWEPatientAgent:
    def __init__(self, name: str):
        self.name = name

    def execute(self, context: TaskContext, invoker) -> AgentResult:
        return getattr(self, self.name.removeprefix("RWE").removesuffix("Agent").lower())(context)

    def quality(self, context):
        observations = context.observations
        missing = [o for o in observations if o.value.value_type in {"missing", "unknown"}]
        findings = [finding(self.name, f"接入 {len(observations)} 个字段观测，其中 {len(missing)} 个缺失或无法识别。", observations)]
        groups = defaultdict(list)
        for obs in observations:
            if obs.metadata.get("reported_score") and obs.event_time and obs.value.value_type == "number":
                groups[(obs.concept_id, obs.event_time)].append(obs)
        for (_, event_time), items in groups.items():
            if len({o.value.value for o in items}) > 1:
                findings.append(finding(self.name, f"{items[0].metadata['form_name']} · {items[0].metadata['field']} 在 {event_time} 存在不同来源值，保留全部记录。", items,
                    unresolved=True, limitations=["同日来源值冲突，需回查 RWE 原始记录。"] ))
        warnings = context.task_parameters.get("warnings", [])
        return AgentResult(agent_name=self.name, status="success", findings=findings,
            limitations=list(dict.fromkeys(warnings + [v for f in findings for v in f.limitations])),
            output={"missing_count": len(missing), "observation_count": len(observations)})

    def assessment(self, context):
        groups = defaultdict(list)
        for obs in context.observations:
            if obs.metadata.get("reported_score") and obs.value.value_type == "number":
                groups[obs.concept_id].append(obs)
        findings, series = [], []
        for concept, items in sorted(groups.items()):
            dated = sorted([o for o in items if o.event_time], key=lambda o: o.event_time)
            latest = [o for o in dated if o.event_time == dated[-1].event_time] if dated else []
            title = f"{items[0].metadata['form_name']} · {items[0].metadata['field']}"
            if latest:
                values = sorted(set(o.value.value for o in latest))
                text = f"{title}：最近有日期记录（{dated[-1].event_time}）为 {' / '.join(f'{v:g}' for v in values)}。"
                findings.append(finding(self.name, text, latest, unresolved=len(values) > 1))
            else:
                findings.append(finding(self.name, f"{title}：{len(items)} 条来源分数缺少日期，无法判断最近记录。", items, unresolved=True))
            series.append({"concept_id": concept, "label": title, "points": [
                {"date": o.event_time, "value": o.value.value, "observation_id": o.observation_id}
                for o in sorted(items, key=lambda o: o.event_time or "9999") ]})
        limitations = ["量表仅展示 RWE 来源分数，未进行条目重计分或诊断分级。"]
        for key in SCORE_FIELDS:
            form = [o for o in context.observations if o.metadata.get("form_key") == key]
            if form and not any(o.metadata.get("reported_score") and o.value.value_type == "number" for o in form):
                limitations.append(f"{form[0].metadata['form_name']} 有条目记录，但没有可用的来源总分。")
        return AgentResult(agent_name=self.name, status="success" if findings else "no_data",
            findings=findings, limitations=limitations, output={"series": series})

    def longitudinal(self, context):
        groups = defaultdict(list)
        for obs in context.observations:
            if obs.metadata.get("reported_score") and obs.event_time and obs.value.value_type == "number":
                groups[obs.concept_id].append(obs)
        findings = []
        for items in groups.values():
            dates = defaultdict(list)
            for item in items:
                dates[item.event_time].append(item)
            # Conflicting same-day observations are excluded rather than selected arbitrarily.
            valid = sorted([v[0] for v in dates.values() if len({o.value.value for o in v}) == 1], key=lambda o: o.event_time)
            if len(valid) < 2:
                continue
            first, last = valid[0], valid[-1]
            delta = last.value.value - first.value.value
            text = (f"{last.metadata['form_name']} · {last.metadata['field']}："
                f"{first.event_time} 的 {first.value.value:g} → {last.event_time} 的 {last.value.value:g}，数值差 {delta:+g}。")
            findings.append(finding(self.name, text, [first, last], limitations=["未提供量表版本，数值差不代表临床变化判定。"] ))
        return AgentResult(agent_name=self.name, status="success" if findings else "insufficient_points",
            findings=findings, limitations=["纵向仅计算同字段来源数值差；缺少量表版本，未判断临床改善或恶化。"] if findings else ["没有两个无同日冲突的有效日期分数，未生成纵向变化。"])

    def laboratory(self, context):
        groups = defaultdict(list)
        for obs in context.observations:
            if obs.metadata.get("form_key") in {"plasma_biomarkers", "csf_biomarkers", "apoe_genotype"} and obs.value.value_type not in {"missing", "unknown"}:
                groups[obs.concept_id].append(obs)
        findings = []
        for items in groups.values():
            dated = [o for o in items if o.event_time]
            selected = [o for o in dated if o.event_time == max(v.event_time for v in dated)] if dated else items
            first = selected[0]
            values = list(dict.fromkeys(str(o.value.value) for o in selected))
            text = f"{first.metadata['form_name']} · {first.metadata['field']}：{' / '.join(values)}（{first.event_time or '日期缺失'}）。"
            findings.append(finding(self.name, text, selected, unresolved=len(values) > 1))
        return AgentResult(agent_name=self.name, status="success" if findings else "no_data", findings=findings,
            limitations=["实验室及遗传结果按来源展示；未补造单位、参考范围或风险阈值。"] if findings else ["未提供有效实验室或遗传记录。"])

    def modalities(self, context):
        imaging = context.task_parameters.get("imaging", {})
        present = [key.upper() for key in ("mri", "pet") if isinstance(imaging.get(key), dict) and imaging[key].get("path")]
        limitations = ["当前 RWE 表单导出不含临床原文，本次未运行文本分析或知识检索。"]
        limitations.append("已提供影像路径，但本次表单分析未验证或运行影像模型。" if present else "未提供 MRI / PET 文件，本次未运行影像推理。")
        return AgentResult(agent_name=self.name, status="capability_unavailable", limitations=limitations,
            output={"imaging_paths_present": present, "inference_executed": False})
