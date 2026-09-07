from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from multi_agent.application.adapt_cli import run_adaptation
from multi_agent.domain.requests import AnalysisRequest
from multi_agent.domain.tasks import Plan, RetryPolicy, TaskDependency, TaskSpec
from multi_agent.orchestration.plan_validator import PlanValidator
from multi_agent.orchestration.planner import TemplatePlanner
from multi_agent.orchestration.scheduler import Scheduler
from multi_agent.registries.capabilities import CapabilityRegistry
from multi_agent.storage.tasks import TaskStore


FIXTURES = Path("tests/fixtures/schema_variants")
MAPPINGS = Path("configs/mappings")


def _capabilities() -> CapabilityRegistry:
    return CapabilityRegistry.from_directory(Path("configs/capabilities"))


def _request(goal: str = "multi_source_summary", project_id: str = "stage05") -> AnalysisRequest:
    return AnalysisRequest(project_id=project_id, goal=goal, as_of=datetime.now(timezone.utc))


def _evidence_db(tmp_path: Path, project_id: str = "stage05") -> Path:
    data_dir = tmp_path / "evidence"
    run_adaptation(
        input_path=FIXTURES / "xx_v1_csv_long.csv",
        mapping_path=MAPPINGS / "xx_v1_csv_long.json",
        project_id=project_id,
        source_namespace="csv-long",
        data_dir=data_dir,
    )
    return data_dir / "stage02.sqlite3"


def test_plan_only_produces_valid_goal_dag(tmp_path) -> None:
    request = _request("multi_source_summary")
    plan = TemplatePlanner().plan(request, {"xx_v1_score", "longitudinal_describe"}, {"xx_v1.total"})

    result = PlanValidator(_capabilities()).validate(request, plan)

    assert result.valid
    assert {task.task_id for task in plan.tasks} >= {"assessment_xx_v1", "longitudinal_xx_v1", "laboratory_optional"}


def test_scheduler_runs_goal_and_records_states(tmp_path) -> None:
    evidence_db = _evidence_db(tmp_path)
    request = _request("multi_source_summary")
    plan = TemplatePlanner().plan(request, {"xx_v1_score", "longitudinal_describe"}, {"xx_v1.total"})
    scheduler = Scheduler(TaskStore(tmp_path / "tasks.sqlite3"), evidence_db, _capabilities())

    result = scheduler.run(request, plan, parallel=False)
    states = {task["spec"]["task_id"]: task["state"] for task in result["tasks"]}

    assert result["status"] == "success"
    assert states["assessment_xx_v1"] == "succeeded"
    assert states["longitudinal_xx_v1"] == "succeeded"
    assert states["laboratory_optional"] == "succeeded"
    assert states["synthesis_report"] == "succeeded"


def test_parallel_and_serial_have_same_terminal_states(tmp_path) -> None:
    evidence_db = _evidence_db(tmp_path)
    request = _request("multi_source_summary")
    plan = TemplatePlanner().plan(request, {"xx_v1_score", "longitudinal_describe"}, {"xx_v1.total"})
    serial = Scheduler(TaskStore(tmp_path / "serial.sqlite3"), evidence_db, _capabilities()).run(request, plan, parallel=False)
    parallel = Scheduler(TaskStore(tmp_path / "parallel.sqlite3"), evidence_db, _capabilities()).run(request, plan, parallel=True)

    serial_states = {task["spec"]["task_id"]: task["state"] for task in serial["tasks"]}
    parallel_states = {task["spec"]["task_id"]: task["state"] for task in parallel["tasks"]}

    assert parallel_states == serial_states


def test_invalid_plan_executes_zero_tasks(tmp_path) -> None:
    request = _request("xx_v1_assessment")
    bad_plan = Plan(
        run_id="bad",
        project_id="stage05",
        goal="xx_v1_assessment",
        tasks=[
            TaskSpec(task_id="bad", capability_id="missing_capability", capability_version="missing/1", resource_class="cpu")
        ],
    )
    scheduler = Scheduler(TaskStore(tmp_path / "tasks.sqlite3"), tmp_path / "missing.sqlite3", _capabilities())

    result = scheduler.run(request, bad_plan)

    assert result["status"] == "invalid_plan"
    assert result["executed"] == 0
    assert result["errors"][0]["code"] == "UNKNOWN_CAPABILITY"


def test_cycle_is_rejected() -> None:
    request = _request("xx_v1_assessment")
    plan = Plan(
        run_id="cycle",
        project_id="stage05",
        goal="xx_v1_assessment",
        tasks=[
            TaskSpec(task_id="a", agent_name="QualityService", depends_on=[TaskDependency(task_id="b")]),
            TaskSpec(task_id="b", agent_name="QualityService", depends_on=[TaskDependency(task_id="a")]),
        ],
    )

    result = PlanValidator(_capabilities()).validate(request, plan)

    assert not result.valid
    assert any(error["code"] == "CYCLE_DETECTED" for error in result.errors)


def test_required_missing_data_blocks_dependent_task(tmp_path) -> None:
    evidence_db = _evidence_db(tmp_path, project_id="stage05_missing")
    request = _request("xx_v1_assessment", project_id="empty_project")
    plan = TemplatePlanner().plan(request, {"xx_v1_score", "longitudinal_describe"}, set())
    scheduler = Scheduler(TaskStore(tmp_path / "tasks.sqlite3"), evidence_db, _capabilities())

    result = scheduler.run(request, plan)
    states = {task["spec"]["task_id"]: task["state"] for task in result["tasks"]}

    assert states["quality_xx_v1"] == "failed"
    assert states["assessment_xx_v1"] == "skipped"


def test_cancel_requested_skips_pending_tasks(tmp_path) -> None:
    evidence_db = _evidence_db(tmp_path)
    request = _request("xx_v1_assessment").model_copy(update={"cancel_requested": True})
    plan = TemplatePlanner().plan(request, {"xx_v1_score", "longitudinal_describe"}, {"xx_v1.total"})
    scheduler = Scheduler(TaskStore(tmp_path / "tasks.sqlite3"), evidence_db, _capabilities())

    result = scheduler.run(request, plan)

    assert result["executed"] == 0
    assert {task["state"] for task in result["tasks"]} == {"skipped"}


def test_retry_wait_is_bounded(tmp_path) -> None:
    evidence_db = _evidence_db(tmp_path)
    request = _request("xx_v1_assessment")
    plan = Plan(
        run_id="retry",
        project_id="stage05",
        goal="xx_v1_assessment",
        tasks=[
            TaskSpec(
                task_id="unknown_executor",
                agent_name="UnknownAgent",
                retry_policy=RetryPolicy(max_attempts=2, retryable_errors=["ValueError"]),
            )
        ],
    )
    scheduler = Scheduler(TaskStore(tmp_path / "tasks.sqlite3"), evidence_db, _capabilities())

    result = scheduler.run(request, plan)
    task = result["tasks"][0]

    assert task["state"] == "failed"
    assert task["attempts"] == 2

