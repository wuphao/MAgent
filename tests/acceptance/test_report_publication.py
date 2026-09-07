from __future__ import annotations

from multi_agent.domain.capabilities import AgentFinding
from multi_agent.domain.reports import ReportCoverage, ReportSnapshot
from multi_agent.reporting.renderers import render_json, render_markdown, render_text
from multi_agent.reporting.validators import PublicationGate


def _snapshot() -> ReportSnapshot:
    return ReportSnapshot(
        report_id="report_demo",
        run_id="run_demo",
        project_id="project_demo",
        status="completed_with_limitations",
        goal="multi_source_summary",
        findings=[
            AgentFinding(
                finding_id="finding_demo",
                proposition="XX-v1 total remains disputed: recomputed total 4 differs from source reported total 0.",
                status="unresolved",
                artifact_refs=["artifact_score"],
                limitations=["reported and recomputed totals conflict; both values are retained"],
            )
        ],
        coverage=ReportCoverage(task_count=3, succeeded_tasks=["assessment_xx_v1"], agent_names=["AssessmentAgent"]),
        limitations=["未决复核项应进入报告限制区。"],
        recommendations=["补充来源字段定义。"],
    )


def test_three_report_formats_render_same_snapshot_identity() -> None:
    snapshot = _snapshot()

    json_report = render_json(snapshot)
    markdown_report = render_markdown(snapshot)
    text_report = render_text(snapshot)

    assert "report_demo" in json_report
    assert "report_demo" in markdown_report
    assert "report_demo" in text_report
    assert "finding_demo" in json_report
    assert "finding_demo" in markdown_report
    assert "多智能体协作分析报告" in text_report


def test_publication_gate_blocks_missing_artifact_reference() -> None:
    snapshot = _snapshot()

    gate = PublicationGate().validate(snapshot, artifacts={})

    assert gate["blocking_errors"]
    assert "missing artifacts" in gate["blocking_errors"][0]
