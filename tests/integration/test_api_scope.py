from __future__ import annotations

from pathlib import Path

from multi_agent.application.api import APIConfig, APIPrincipal, ApplicationAPI


FIXTURES = Path("tests/fixtures/stage06")
MAPPING_ID = "xx_v1_csv_long"


def test_api_rejects_cross_project_without_leaking_existence(tmp_path: Path) -> None:
    api = ApplicationAPI(APIConfig(data_dir=tmp_path / "data", task_db=tmp_path / "tasks.sqlite3"))
    principal = APIPrincipal(principal_id="u1", project_ids=["allowed"])

    response = api.profile_dataset(
        principal,
        project_id="denied",
        input_path=FIXTURES / "xx_v1_scoring_conflict.csv",
        mapping_id=MAPPING_ID,
        source_namespace="api-test",
        idempotency_key="idem-1",
    )

    assert response.status == "not_found"
    assert response.errors[0]["code"] == "NOT_FOUND"


def test_api_idempotency_conflict_for_same_key_different_body(tmp_path: Path) -> None:
    api = ApplicationAPI(APIConfig(data_dir=tmp_path / "data", task_db=tmp_path / "tasks.sqlite3"))
    principal = APIPrincipal(principal_id="u1", project_ids=["p1"])

    first = api.profile_dataset(
        principal,
        project_id="p1",
        input_path=FIXTURES / "xx_v1_scoring_conflict.csv",
        mapping_id=MAPPING_ID,
        source_namespace="api-test",
        idempotency_key="same-key",
    )
    second = api.profile_dataset(
        principal,
        project_id="p1",
        input_path=Path("tests/fixtures/schema_variants/xx_v1_csv_long.csv"),
        mapping_id=MAPPING_ID,
        source_namespace="api-test",
        idempotency_key="same-key",
    )

    assert first.status == "success"
    assert second.status == "conflict"
    assert second.errors[0]["code"] == "IDEMPOTENCY_CONFLICT"


def test_api_creates_run_exposes_challenges_and_scoped_evidence(tmp_path: Path) -> None:
    api = ApplicationAPI(APIConfig(data_dir=tmp_path / "data", task_db=tmp_path / "tasks.sqlite3"))
    principal = APIPrincipal(principal_id="u1", project_ids=["p1"])
    api.profile_dataset(
        principal,
        project_id="p1",
        input_path=FIXTURES / "xx_v1_scoring_conflict.csv",
        mapping_id=MAPPING_ID,
        source_namespace="api-test",
        idempotency_key="dataset-1",
    )

    run = api.create_analysis_run(principal, project_id="p1", goal="multi_source_summary", idempotency_key="run-1")
    run_id = run.data["run_id"]
    challenges = api.list_challenges(principal, project_id="p1", run_id=run_id)
    report = api.get_report(principal, project_id="p1", run_id=run_id)
    first_ref = report.data["report_snapshot"]["findings"][0]["support_refs"][0]
    evidence = api.get_evidence(principal, project_id="p1", observation_id=first_ref["observation_id"], revision=first_ref["revision"])

    assert run.status == "success"
    assert challenges.status == "success"
    assert challenges.data["challenges"]
    assert report.data["report_snapshot"]["status"] == "completed_with_limitations"
    assert evidence.status == "success"

    denied = APIPrincipal(principal_id="u2", project_ids=["other"])
    assert api.get_report(denied, project_id="p1", run_id=run_id).status == "not_found"


def test_api_does_not_allow_run_id_project_confusion(tmp_path: Path) -> None:
    api = ApplicationAPI(APIConfig(data_dir=tmp_path / "data", task_db=tmp_path / "tasks.sqlite3"))
    owner = APIPrincipal(principal_id="owner", project_ids=["p1"])
    other = APIPrincipal(principal_id="other", project_ids=["p2"])
    api.profile_dataset(
        owner,
        project_id="p1",
        input_path=FIXTURES / "xx_v1_scoring_conflict.csv",
        mapping_id=MAPPING_ID,
        source_namespace="api-test",
        idempotency_key="dataset-owner",
    )
    run = api.create_analysis_run(owner, project_id="p1", goal="multi_source_summary", idempotency_key="run-owner")
    run_id = run.data["run_id"]

    assert api.get_report(other, project_id="p2", run_id=run_id).status == "not_found"
    assert api.cancel_run(other, project_id="p2", run_id=run_id).status == "not_found"


def test_api_invalid_goal_returns_validation_error(tmp_path: Path) -> None:
    api = ApplicationAPI(APIConfig(data_dir=tmp_path / "data", task_db=tmp_path / "tasks.sqlite3"))
    principal = APIPrincipal(principal_id="u1", project_ids=["p1"])

    response = api.create_analysis_run(principal, project_id="p1", goal="bad_goal", idempotency_key="bad-run")

    assert response.status == "failed"
    assert response.errors[0]["code"] == "VALIDATION_FAILED"
