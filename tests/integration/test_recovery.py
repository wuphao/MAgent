from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from multi_agent.domain.requests import AnalysisRequest
from multi_agent.domain.tasks import Plan, TaskSpec
from multi_agent.orchestration.incremental import IncrementalPlanner
from multi_agent.orchestration.recovery import RecoveryManager, StagingArtifactCommitter
from multi_agent.storage.dependencies import DependencyStore
from multi_agent.storage.leases import LeaseStore
from multi_agent.storage.outbox import OutboxStore
from multi_agent.storage.sqlite import SQLiteStore
from multi_agent.storage.tasks import TaskStore


def _task_store(tmp_path: Path) -> TaskStore:
    store = TaskStore(tmp_path / "tasks.sqlite3")
    request = AnalysisRequest(project_id="p1", goal="xx_v1_assessment", as_of=datetime.now(timezone.utc))
    plan = Plan(run_id="run_recovery", project_id="p1", goal="xx_v1_assessment", tasks=[TaskSpec(task_id="task_a", agent_name="QualityService")])
    store.create_run(request, plan)
    return store


def test_lease_fencing_rejects_late_result_after_reclaim(tmp_path: Path) -> None:
    store = _task_store(tmp_path)
    leases = LeaseStore(store)

    first = leases.claim("run_recovery", "task_a", owner="worker-a", lease_seconds=-1)
    second = leases.claim("run_recovery", "task_a", owner="worker-b", lease_seconds=60)

    assert first is not None
    assert second is not None
    assert second["fencing_token"] > first["fencing_token"]
    assert not leases.complete("run_recovery", "task_a", first["fencing_token"], json.dumps({"late": True}))
    assert leases.complete("run_recovery", "task_a", second["fencing_token"], json.dumps({"fresh": True}))
    task = store.get_tasks("run_recovery")[0]
    assert task.result == {"fresh": True}


def test_recovery_requeues_expired_running_task_and_preserves_outbox(tmp_path: Path) -> None:
    task_store = _task_store(tmp_path)
    leases = LeaseStore(task_store)
    leases.claim("run_recovery", "task_a", owner="worker-a", lease_seconds=-1)
    evidence_store = SQLiteStore(tmp_path / "evidence.sqlite3")
    outbox = OutboxStore(evidence_store)
    assert outbox.enqueue("event-1", "p1", "report.created", {"run_id": "run_recovery"})
    assert not outbox.enqueue("event-1", "p1", "report.created", {"run_id": "run_recovery"})

    result = RecoveryManager(task_store, evidence_store).recover()

    assert result["expired_leases_requeued"] == 1
    assert result["pending_outbox_events"] == 1
    assert task_store.get_tasks("run_recovery")[0].state == "ready"


def test_staging_artifact_repair_commits_once(tmp_path: Path) -> None:
    committer = StagingArtifactCommitter(tmp_path / "artifacts")
    staged = committer.stage("artifact-key", b"payload")

    repaired = committer.repair_staging()
    committed_again = committer.commit(staged)

    assert repaired == {"repaired": 1, "removed": 0}
    assert committed_again["status"] == "committed"
    assert len(list((tmp_path / "artifacts" / "objects").rglob("*"))) >= 1


def test_dependency_closure_drives_incremental_task_selection(tmp_path: Path) -> None:
    deps = DependencyStore(SQLiteStore(tmp_path / "deps.sqlite3"))
    deps.record_edge("p1", ("mapping", "xx_v1_csv_long", "1"), ("observation", "obs-1", "1"))
    deps.record_edge("p1", ("observation", "obs-1", "1"), ("finding", "finding-1", "1"))
    deps.record_edge("p1", ("finding", "finding-1", "1"), ("report", "report-1", "1"))

    plan = IncrementalPlanner(deps).plan_change("p1", ("mapping", "xx_v1_csv_long", "1"))

    assert [item["kind"] for item in plan.affected_refs] == ["observation", "finding", "report"]
    assert {"assessment_xx_v1", "longitudinal_xx_v1", "synthesis_report"} <= set(plan.task_ids)
    assert "diamond_compatibility" not in plan.task_ids


def test_create_run_is_idempotent_and_does_not_wipe_results(tmp_path: Path) -> None:
    store = _task_store(tmp_path)
    store.store_result("run_recovery", "task_a", {"value": 1})
    store.transition("run_recovery", "task_a", "pending", "ready")
    store.transition("run_recovery", "task_a", "ready", "running")
    store.transition("run_recovery", "task_a", "running", "succeeded")
    request = AnalysisRequest(project_id="p1", goal="xx_v1_assessment", as_of=datetime.now(timezone.utc))
    plan = Plan(run_id="run_recovery", project_id="p1", goal="xx_v1_assessment", tasks=[TaskSpec(task_id="task_a", agent_name="QualityService")])

    store.create_run(request, plan)

    task = store.get_tasks("run_recovery")[0]
    assert task.state == "succeeded"
    assert task.result == {"value": 1}
