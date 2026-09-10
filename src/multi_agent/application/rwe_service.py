"""Local RWE export → observation store → existing scheduler → report snapshot."""
from __future__ import annotations

import json
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from multi_agent.domain.requests import AnalysisRequest
from multi_agent.ingestion.rwe_export import ExportFailure, export_arguments, export_patient
from multi_agent.ingestion.rwe_patient import ingest_patient
from multi_agent.orchestration.planner import TemplatePlanner
from multi_agent.orchestration.scheduler import Scheduler
from multi_agent.registries.capabilities import CapabilityRegistry
from multi_agent.storage.sqlite import EvidenceRepository, SQLiteStore
from multi_agent.storage.tasks import TaskStore


ROOT = Path(__file__).resolve().parents[3]
PATIENT_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
JOB_PATTERN = re.compile(r"[a-f0-9]{32}\Z")


def write_json(path: Path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def analyze_file(path: Path, run_dir: Path, patient: str, notify=None) -> dict:
    notify = notify or (lambda **kwargs: None)
    # Every export has its own store; earlier patient observations never leak into a run.
    project_id = "rwe_" + run_dir.name
    notify(stage="ingest", message="标准化字段与登记来源证据")
    adapted = ingest_patient(path, run_dir, project_id, patient)
    document = adapted["document"]
    warnings = list(adapted["warnings"])
    quality = document.get("data_quality") or {}
    warnings += [str(w.get("message", "")) for w in quality.get("warnings", []) if isinstance(w, dict)]
    warnings += ["缺少表单：" + str(name) for name in quality.get("missing_forms", [])]
    request = AnalysisRequest(project_id=project_id, goal="rwe_patient_summary", as_of=datetime.now(timezone.utc))
    capabilities = CapabilityRegistry.from_directory(ROOT / "configs/capabilities")
    plan = TemplatePlanner().plan(request, {s.capability_id for s in capabilities.available_for_production()})
    plan = plan.model_copy(update={"tasks": [task.model_copy(update={"parameters":
        {"warnings": warnings} if task.task_id == "rwe_quality" else
        {"imaging": document.get("imaging", {})} if task.task_id == "rwe_modalities" else task.parameters
    }) for task in plan.tasks]})
    task_store = TaskStore(run_dir / "tasks.sqlite3")
    notify(stage="analysis", message="运行患者分析任务", run_id=plan.run_id,
        patient=document["patient"], exported_at=document.get("exported_at"),
        record_count=sum(adapted["record_counts"].values()))
    result = Scheduler(task_store, run_dir / "evidence.sqlite3", capabilities, ROOT / "configs/instruments").run(request, plan)
    if result["status"] != "success":
        raise ValueError("分析任务规划未通过验证")
    tasks = result["tasks"]
    report_task = next((t for t in tasks if t["spec"]["task_id"] == "synthesis_report"), None)
    report = (report_task or {}).get("result") or {}
    snapshot = report.get("output", {}).get("report_snapshot")
    if not snapshot:
        raise ValueError("综合报告生成失败；请检查本次任务记录")
    # Preserve original snapshot status; task execution success is not report completeness.
    observations = EvidenceRepository(SQLiteStore(run_dir / "evidence.sqlite3")).list_observations(project_id)
    evidence = [{"observation_id": o.observation_id, "revision": o.revision,
        "form": o.metadata["form_name"], "field": o.metadata["field"],
        "date": o.event_time, "value": o.value.value, "value_type": o.value.value_type,
        "record_id": o.metadata["record_id"], "source": o.source.model_dump(mode="json")} for o in observations]
    series = next((t["result"]["output"].get("series", []) for t in tasks
        if t["spec"]["task_id"] == "rwe_assessment" and t.get("result")), [])
    output = {"patient": document["patient"], "exported_at": document.get("exported_at"),
        "source": "rwe", "record_count": sum(adapted["record_counts"].values()),
        "forms": [{"key": key, "name": form.get("form_name", key), "count": len(form["records"])}
            for key, form in document["forms"].items()],
        "observation_count": len(observations), "report_snapshot": snapshot,
        "tasks": tasks, "evidence": evidence, "series": series}
    write_json(run_dir / "report.json", snapshot)
    write_json(run_dir / "analysis.json", output)
    return output


class RWEJobService:
    def __init__(self, root: Path | None = None, exporter=export_patient):
        self.root = root or ROOT / "output/rwe/runs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.exporter = exporter
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rwe")
        self.jobs = {}
        for path in self.root.glob("*/job.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if value.get("status") in {"queued", "running"}:
                    value.update(status="failed", message="服务已重启，本次任务中断，请重新分析。")
                    write_json(path, value)
            except (ValueError, OSError):
                continue

    def close(self):
        self.pool.shutdown(wait=True)

    def directory(self, job_id):
        if not JOB_PATTERN.fullmatch(job_id):
            raise KeyError("任务不存在")
        return self.root / job_id

    def create(self, patient: str):
        if not isinstance(patient, str) or not PATIENT_PATTERN.fullmatch(patient):
            raise ValueError("患者编号仅支持 1–64 位字母、数字、下划线和短横线")
        with self.lock:
            active = [j for j in self.jobs.values() if j["status"] in {"running", "queued"}]
            if any(j["patient_number"] == patient for j in active):
                return dict(next(j for j in active if j["patient_number"] == patient))
            if len(active) >= 8:
                raise ValueError("待分析任务较多，请稍后重试")
            job_id = uuid.uuid4().hex
            directory = self.directory(job_id)
            directory.mkdir()
            job = {"job_id": job_id, "patient_number": patient, "status": "queued", "stage": "export",
                "message": "等待导出", "created_at": datetime.now(timezone.utc).isoformat()}
            self.jobs[job_id] = job
            write_json(directory / "job.json", job)
            self.pool.submit(self._run, job_id, patient)
            return dict(job)

    def update(self, job_id, **values):
        with self.lock:
            self.jobs[job_id].update(values)
            write_json(self.directory(job_id) / "job.json", self.jobs[job_id])

    def _run(self, job_id, patient):
        directory = self.directory(job_id)
        try:
            self.update(job_id, status="running", stage="export", message="解析患者编号")
            path = directory / "patient.json"
            self.exporter(export_arguments(patient, path), on_form=lambda name:
                self.update(job_id, message="导出 " + name))
            output = analyze_file(path, directory, patient, lambda **values: self.update(job_id, **values))
            self.update(job_id, status=output["report_snapshot"]["status"], stage="done", message="分析完成")
        except (ExportFailure, ValueError) as exc:
            self.update(job_id, status="failed", message=str(exc))
        except Exception as exc:
            # Do not return raw DB/network exceptions, which may contain connection details.
            self.update(job_id, status="failed", message=f"运行失败（{type(exc).__name__}），请检查 RWE 与本机数据库连接。")

    def get(self, job_id):
        directory = self.directory(job_id)
        with self.lock:
            try:
                job = json.loads((directory / "job.json").read_text(encoding="utf-8"))
            except FileNotFoundError:
                raise KeyError("任务不存在") from None
        if job.get("run_id") and (directory / "tasks.sqlite3").exists():
            job["tasks"] = [t.model_dump(mode="json") for t in TaskStore(directory / "tasks.sqlite3").get_tasks(job["run_id"])]
        if job["status"] not in {"queued", "running"} and (directory / "analysis.json").exists():
            job["analysis"] = json.loads((directory / "analysis.json").read_text(encoding="utf-8"))
        return job
