from __future__ import annotations

import json

from multi_agent.domain.reports import ReportSnapshot


def render_json(snapshot: ReportSnapshot) -> str:
    return snapshot.model_dump_json(indent=2)


def render_markdown(snapshot: ReportSnapshot) -> str:
    lines = [
        "# 多智能体协作分析报告",
        "",
        f"- 报告ID：{snapshot.report_id}",
        f"- Run ID：{snapshot.run_id}",
        f"- 项目：{snapshot.project_id}",
        f"- 目标：{snapshot.goal}",
        f"- 状态：{snapshot.status}",
        "",
        "## 覆盖情况",
        "",
        f"- 任务数：{snapshot.coverage.task_count}",
        f"- 成功任务：{', '.join(snapshot.coverage.succeeded_tasks) or '无'}",
        f"- 失败任务：{', '.join(snapshot.coverage.failed_tasks) or '无'}",
        f"- Agent：{', '.join(snapshot.coverage.agent_names) or '无'}",
        f"- 未读证据数：{snapshot.coverage.unread_evidence_count}",
        "",
        "## 发现",
        "",
    ]
    if not snapshot.findings:
        lines.append("暂无可发布发现。")
    for finding in snapshot.findings:
        refs = len(finding.support_refs) + len(finding.artifact_refs)
        lines.append(f"- **{finding.finding_id}**（{finding.status}，引用数 {refs}）：{finding.proposition}")
        for limitation in finding.limitations:
            lines.append(f"  - 限制：{limitation}")
    lines.extend(["", "## 质询与复核", ""])
    if not snapshot.challenges:
        lines.append("未发现需要质询的问题。")
    for challenge in snapshot.challenges:
        lines.append(f"- **{challenge.challenge_id}** [{challenge.severity}/{challenge.category}]：{challenge.question}")
        related = [outcome for outcome in snapshot.review_outcomes if outcome.challenge_id == challenge.challenge_id]
        for outcome in related:
            lines.append(f"  - 复核：{outcome.status}；{outcome.rationale}")
    lines.extend(["", "## 局限性", ""])
    if not snapshot.limitations:
        lines.append("未记录额外局限性。")
    else:
        lines.extend(f"- {item}" for item in snapshot.limitations)
    lines.extend(["", "## 建议", ""])
    lines.extend(f"- {item}" for item in snapshot.recommendations)
    return "\n".join(lines) + "\n"


def render_text(snapshot: ReportSnapshot) -> str:
    parts = [
        f"多智能体协作分析报告 {snapshot.report_id}，状态为{snapshot.status}。",
        f"本次运行包含{snapshot.coverage.task_count}个任务，形成{len(snapshot.findings)}条发现。",
    ]
    if snapshot.challenges:
        parts.append(f"系统提出{len(snapshot.challenges)}个质询，并完成{len(snapshot.review_outcomes)}个定向复核；未决问题已保留为报告限制。")
    if snapshot.limitations:
        parts.append("主要限制：" + "；".join(snapshot.limitations[:3]) + "。")
    return "".join(parts) + "\n"
