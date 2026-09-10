from __future__ import annotations

import json
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

import pytest

from multi_agent.application.rwe_service import RWEJobService, analyze_file
from multi_agent.application.web import make_handler
from multi_agent.ingestion.rwe_export import ExportFailure, export_patient, export_arguments, api_query_form
from multi_agent.ingestion.rwe_patient import ingest_patient
from multi_agent.orchestration.executor import TaskExecutor


def source(patient="TEST_001", records=None):
    return {"schema_version": "2.0", "project": {"id": 8},
        "patient": {"patient_number": patient, "patient_id": 1},
        "exported_at": "2026-01-01T00:00:00+00:00", "imaging": {},
        "forms": {"mmse": {"form_name": "MMSE量表", "fill_mode": "multiple", "records": records or [
            {"record_id": 1, "visit_date": "2024-01-01", "MMSE总分": 28},
            {"record_id": 2, "visit_date": "2025-01-01", "MMSE总分": 26},
        ]}}, "data_quality": {"warnings": [], "missing_forms": []}}


def write_source(tmp_path, document):
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "patient.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


def test_real_form_pipeline_and_evidence(tmp_path):
    path = write_source(tmp_path, source())
    result = analyze_file(path, tmp_path, "TEST_001")
    snapshot = result["report_snapshot"]
    assert snapshot["status"] == "completed_with_limitations"
    assert result["record_count"] == result["observation_count"] == 2
    assert any("数值差 -2" in f["proposition"] for f in snapshot["findings"])
    assert not any("XX-v1" in f["proposition"] for f in snapshot["findings"])
    refs = {e["observation_id"] for e in result["evidence"]}
    assert all(r["observation_id"] in refs for f in snapshot["findings"] for r in f["support_refs"])
    assert "rwe_modalities" in snapshot["coverage"]["failed_tasks"]
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8")) == snapshot


def test_wrong_patient_rejected(tmp_path):
    path = write_source(tmp_path, source())
    with pytest.raises(ValueError, match="患者编号"):
        ingest_patient(path, tmp_path, "project", "OTHER")


def test_conflicting_dates_excluded_from_longitudinal(tmp_path):
    doc = source(records=[{"visit_date": "2024-01-01", "MMSE总分": 28},
        {"visit_date": "2025-01-01", "MMSE总分": 26},
        {"visit_date": "2025-01-01", "MMSE总分": 24}])
    result = analyze_file(write_source(tmp_path, doc), tmp_path, "TEST_001")
    tasks = {t["spec"]["task_id"]: t["result"] for t in result["tasks"]}
    assert tasks["rwe_longitudinal"]["status"] == "insufficient_points"
    assert any(f["status"] == "unresolved" for f in tasks["rwe_quality"]["findings"])
    assert len(result["series"][0]["points"]) == 3


def test_no_date_and_no_total_are_not_invented(tmp_path):
    doc = source(records=[{"visit_date": "invalid", "MMSE总分": 28}])
    doc["forms"]["moca"] = {"form_name": "MOCA量表", "records": [{"连线测试": "正确"}]}
    result = analyze_file(write_source(tmp_path, doc), tmp_path, "TEST_001")
    assert len(result["series"]) == 1
    assert result["series"][0]["points"][0]["date"] is None
    assert any("没有可用的来源总分" in v for v in result["report_snapshot"]["limitations"])


def test_identical_ingestion_is_idempotent(tmp_path):
    path = write_source(tmp_path, source())
    first = ingest_patient(path, tmp_path, "test", "TEST_001")
    second = ingest_patient(path, tmp_path, "test", "TEST_001")
    assert first["observation_count"] == second["observation_count"] == 2
    assert first["asset"] == second["asset"]


def test_optional_exception_is_in_report_coverage(tmp_path):
    original = TaskExecutor.execute
    def execute(self, task, context, invoker):
        if task.task_id == "rwe_laboratory":
            raise RuntimeError("synthetic failure")
        return original(self, task, context, invoker)
    with patch.object(TaskExecutor, "execute", execute):
        result = analyze_file(write_source(tmp_path, source()), tmp_path, "TEST_001")
    assert "rwe_laboratory" in result["report_snapshot"]["coverage"]["failed_tasks"]
    assert any("rwe_laboratory" in text for text in result["report_snapshot"]["limitations"])


def test_isolated_patients(tmp_path):
    first = analyze_file(write_source(tmp_path / "first", source()), tmp_path / "first", "TEST_001")
    second = analyze_file(write_source(tmp_path / "second", source("TEST_002")), tmp_path / "second", "TEST_002")
    assert first["report_snapshot"]["project_id"] != second["report_snapshot"]["project_id"]
    assert not ({e["observation_id"] for e in first["evidence"]} & {e["observation_id"] for e in second["evidence"]})


def test_expired_auth_is_clear(tmp_path):
    import requests
    args = export_arguments("TEST_001", tmp_path / "patient.json", {"RWE_API_TOKEN": "expired"})
    response = requests.Response(); response.status_code = 401
    with patch.object(requests, "post", return_value=response):
        with pytest.raises(ExportFailure, match="登录已失效"):
            api_query_form(requests, args, 55, 1)


def test_missing_token_does_not_touch_database(tmp_path):
    args = export_arguments("TEST_001", tmp_path / "patient.json", {})
    with patch("multi_agent.ingestion.rwe_export.dependencies") as dependencies:
        with pytest.raises(ExportFailure, match="Token"):
            export_patient(args)
        dependencies.assert_not_called()


@pytest.fixture
def server(tmp_path):
    def exporter(args, on_form):
        on_form("MMSE量表")
        if args.patient_number == "MISSING":
            raise ExportFailure("找不到患者编号")
        write_source(args.output.parent, source(args.patient_number))
    service = RWEJobService(tmp_path / "runs", exporter)
    http = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
    worker = threading.Thread(target=http.serve_forever, daemon=True); worker.start()
    yield f"http://127.0.0.1:{http.server_port}", service
    http.shutdown(); http.server_close(); worker.join(); service.close()


def test_http_export_analyze_download(server):
    url, service = server
    request = Request(url + "/api/runs", data=b'{"patient_number":"TEST_001"}', headers={"Content-Type": "application/json"})
    with urlopen(request) as response:
        assert response.status == 202
        job = json.load(response)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with urlopen(url + "/api/runs/" + job["job_id"]) as response:
            current = json.load(response)
        if current["status"] not in {"running", "queued"}: break
        time.sleep(.05)
    assert current["status"] == "completed_with_limitations"
    for suffix, key in (("source", "patient"), ("report", "findings")):
        with urlopen(url + "/api/runs/" + job["job_id"] + "/" + suffix) as response:
            assert "attachment" in response.headers["Content-Disposition"]
            assert key in json.load(response)


@pytest.mark.parametrize("path", ["/.env.rwe.local", "/output/", "/api/runs/../source", "/ui/../../.env"])
def test_http_never_serves_repository(server, path):
    url, _ = server
    with pytest.raises(HTTPError) as error:
        urlopen(url + path)
    assert error.value.code == 404


def test_http_rejects_cross_origin_and_invalid_patient(server):
    url, _ = server
    request = Request(url + "/api/runs", data=b'{"patient_number":"TEST_001"}',
        headers={"Origin": "https://other.example", "Content-Type": "application/json"})
    with pytest.raises(HTTPError) as error: urlopen(request)
    assert error.value.code == 403
    request = Request(url + "/api/runs", data=b'{"patient_number":"../../x"}', headers={"Content-Type": "application/json"})
    with pytest.raises(HTTPError) as error: urlopen(request)
    assert error.value.code == 400


def test_export_failure_never_returns_previous_report(server):
    _, service = server
    job = service.create("MISSING")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        current = service.get(job["job_id"])
        if current["status"] == "failed": break
        time.sleep(.05)
    assert current["status"] == "failed"
    assert "analysis" not in current
    assert not (service.directory(job["job_id"]) / "patient.json").exists()


def test_restart_marks_incomplete_job_failed(tmp_path):
    job_id = "a" * 32
    folder = tmp_path / job_id; folder.mkdir()
    (folder / "job.json").write_text(json.dumps({"job_id": job_id, "status": "running"}))
    service = RWEJobService(tmp_path)
    try:
        assert service.get(job_id)["status"] == "failed"
    finally:
        service.close()
