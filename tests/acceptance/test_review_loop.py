from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from multi_agent.application.adapt_cli import run_adaptation
from multi_agent.domain.capabilities import AgentFinding
from multi_agent.domain.challenges import Challenge, FindingRef
from multi_agent.orchestration.planner import TemplatePlanner
from multi_agent.orchestration.scheduler import Scheduler
from multi_agent.registries.capabilities import CapabilityRegistry
from multi_agent.domain.requests import AnalysisRequest
from multi_agent.storage.tasks import TaskStore


FIXTURES = Path("tests/fixtures/stage06")
MAPPINGS = Path("configs/mappings")


def _capabilities() -> CapabilityRegistry:
    return CapabilityRegistry.from_directory(Path("configs/capabilities"))


def _evidence_db(tmp_path: Path, project_id: str = "stage06") -> Path:
    data_dir = tmp_path / "evidence"
    run_adaptation(
        input_path=FIXTURES / "xx_v1_scoring_conflict.csv",
        mapping_path=MAPPINGS / "xx_v1_csv_long.json",
        project_id=project_id,
        source_namespace="csv-long",
        data_dir=data_dir,
    )
    return data_dir / "stage02.sqlite3"


def test_review_loop_creates_targeted_challenge_and_unresolved_outcome(tmp_path) -> None:
    request = AnalysisRequest(project_id="stage06", goal="multi_source_summary", as_of=datetime.now(timezone.utc))
    plan = TemplatePlanner().plan(request, {"xx_v1_score", "longitudinal_describe"}, {"xx_v1.total"})
    result = Scheduler(TaskStore(tmp_path / "tasks.sqlite3"), _evidence_db(tmp_path), _capabilities()).run(request, plan)
    synthesis = next(task for task in result["tasks"] if task["spec"]["task_id"] == "synthesis_report")
    snapshot = synthesis["result"]["output"]["report_snapshot"]

    assert synthesis["state"] == "succeeded"
    assert snapshot["schema_version"] == "stage06.report_snapshot/1"
    assert snapshot["status"] == "completed_with_limitations"
    assert any(challenge["category"] == "scoring" for challenge in snapshot["challenges"])
    assert any(outcome["status"] == "unresolved" for outcome in snapshot["review_outcomes"])
    assert any("保留两个值" in outcome["rationale"] for outcome in snapshot["review_outcomes"])
    published_ids = {finding["finding_id"] for finding in snapshot["findings"]}
    withdrawn_ids = set(snapshot["withdrawn_finding_ids"])
    assert published_ids.isdisjoint(withdrawn_ids)
    assert any(finding_id.endswith("_reviewed") for finding_id in published_ids)


def test_unresolved_missing_evidence_must_describe_collection_path() -> None:
    challenge = Challenge(
        challenge_id="challenge_missing_metadata",
        target_finding_ref=FindingRef(finding_id="finding_without_source"),
        category="missing_evidence",
        question="缺少来源字段定义，无法判断总分字段语义。",
        expected_resolution="获取来源字段字典或人工确认记录后再复核。",
        severity="medium",
    )

    assert challenge.status == "open"
    assert challenge.evidence_refs == []


def test_more_than_twenty_findings_are_not_truncated() -> None:
    from multi_agent.collaboration.synthesis import EvidenceCatalog

    task_results = {
        "bulk": {
            "agent_name": "BulkAgent",
            "status": "success",
            "findings": [
                AgentFinding(
                    finding_id=f"finding_{index:02d}",
                    proposition=f"synthetic proposition {index}",
                    status="active",
                ).model_dump(mode="json")
                for index in range(25)
            ],
            "output": {},
        }
    }

    catalog = EvidenceCatalog(task_results)

    assert len(catalog.findings) == 25
    assert catalog.findings[-1].finding_id == "finding_24"


