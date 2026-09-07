from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from multi_agent.application.adapt_cli import run_adaptation
from multi_agent.domain.requests import AnalysisRequest, BudgetLimit
from multi_agent.orchestration.planner import TemplatePlanner
from multi_agent.orchestration.scheduler import Scheduler
from multi_agent.registries.capabilities import CapabilityRegistry
from multi_agent.storage.sqlite import EvidenceRepository, SQLiteStore
from multi_agent.storage.tasks import TaskStore


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class APIPrincipal(APIModel):
    principal_id: str
    project_ids: list[str] = Field(default_factory=list)
    subject_scope: list[str] = Field(default_factory=list)


class APIResponse(APIModel):
    status: str
    data: dict[str, Any] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list)


@dataclass(frozen=True)
class APIConfig:
    data_dir: Path = Path("data/v2")
    task_db: Path = Path("data/v2/tasks.sqlite3")
    capabilities_dir: Path = Path("configs/capabilities")
    mappings_dir: Path = Path("configs/mappings")


class IdempotencyLedger:
    def __init__(self):
        self._entries: dict[tuple[str, str], str] = {}

    def check(self, principal_id: str, idempotency_key: str, body: dict[str, Any]) -> APIResponse | None:
        digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()
        key = (principal_id, idempotency_key)
        existing = self._entries.get(key)
        if existing and existing != digest:
            return APIResponse(status="conflict", errors=[{"code": "IDEMPOTENCY_CONFLICT", "message": "same idempotency_key with different request body"}])
        self._entries[key] = digest
        return None


class ApplicationAPI:
    def __init__(self, config: APIConfig | None = None):
        self.config = config or APIConfig()
        self.idempotency = IdempotencyLedger()

    def profile_dataset(self, principal: APIPrincipal, *, project_id: str, input_path: Path, mapping_id: str, source_namespace: str, idempotency_key: str) -> APIResponse:
        denied = self._authorize(principal, project_id)
        if denied:
            return denied
        body = {"project_id": project_id, "input_path": str(input_path), "mapping_id": mapping_id, "source_namespace": source_namespace}
        conflict = self.idempotency.check(principal.principal_id, idempotency_key, body)
        if conflict:
            return conflict
        mapping_path = self.config.mappings_dir / f"{mapping_id}.json"
        if not mapping_path.exists():
            return APIResponse(status="failed", errors=[{"code": "VALIDATION_FAILED", "field_path": "mapping_id", "message": "mapping is not registered"}])
        result = run_adaptation(input_path, mapping_path, project_id, source_namespace, self.config.data_dir)
        return APIResponse(status="success", data=result)

    def create_analysis_run(self, principal: APIPrincipal, *, project_id: str, goal: str, idempotency_key: str, max_calls: int = 0, max_tokens: int = 0) -> APIResponse:
        denied = self._authorize(principal, project_id)
        if denied:
            return denied
        body = {"project_id": project_id, "goal": goal, "max_calls": max_calls, "max_tokens": max_tokens}
        conflict = self.idempotency.check(principal.principal_id, idempotency_key, body)
        if conflict:
            return conflict
        capabilities = CapabilityRegistry.from_directory(self.config.capabilities_dir)
        evidence_db = self.config.data_dir / "stage02.sqlite3"
        observations = EvidenceRepository(SQLiteStore(evidence_db)).list_observations(project_id)
        try:
            request = AnalysisRequest(project_id=project_id, goal=goal, as_of=datetime.now(timezone.utc), budget=BudgetLimit(max_calls=max_calls, max_tokens=max_tokens))
        except ValidationError as exc:
            return APIResponse(status="failed", errors=[{"code": "VALIDATION_FAILED", "message": str(exc)}])
        plan = TemplatePlanner().plan(request, {spec.capability_id for spec in capabilities.available_for_production()}, {item.concept_id for item in observations})
        result = Scheduler(TaskStore(self.config.task_db), evidence_db, capabilities).run(request, plan)
        return APIResponse(status=result["status"], data=result)

    def cancel_run(self, principal: APIPrincipal, *, project_id: str, run_id: str) -> APIResponse:
        task_store = TaskStore(self.config.task_db)
        denied = self._authorize_run(principal, project_id, run_id, task_store)
        if denied:
            return denied
        task_store.set_cancel_requested(run_id)
        return APIResponse(status="success", data={"run_id": run_id, "cancel_requested": True})

    def get_report(self, principal: APIPrincipal, *, project_id: str, run_id: str) -> APIResponse:
        task_store = TaskStore(self.config.task_db)
        denied = self._authorize_run(principal, project_id, run_id, task_store)
        if denied:
            return denied
        task_results = {record.spec.task_id: record.result for record in task_store.get_tasks(run_id) if record.result}
        synthesis = task_results.get("synthesis_report")
        if synthesis and isinstance(synthesis.get("output"), dict) and synthesis["output"].get("report_snapshot"):
            return APIResponse(status="success", data={"report_snapshot": synthesis["output"]["report_snapshot"]})
        return APIResponse(status="failed", errors=[{"code": "NOT_FOUND", "message": "report is not available for this run"}])

    def list_challenges(self, principal: APIPrincipal, *, project_id: str, run_id: str) -> APIResponse:
        report = self.get_report(principal, project_id=project_id, run_id=run_id)
        if report.status != "success":
            return report
        snapshot = report.data["report_snapshot"]
        return APIResponse(status="success", data={"challenges": snapshot.get("challenges", [])})

    def get_evidence(self, principal: APIPrincipal, *, project_id: str, observation_id: str, revision: int) -> APIResponse:
        denied = self._authorize(principal, project_id)
        if denied:
            return denied
        try:
            observation = EvidenceRepository(SQLiteStore(self.config.data_dir / "stage02.sqlite3")).get_observation(project_id, observation_id, revision)
            if principal.subject_scope and observation.subject_ref not in principal.subject_scope:
                return APIResponse(status="not_found", errors=[{"code": "NOT_FOUND", "message": "object not found"}])
            return APIResponse(status="success", data={"observation": observation.model_dump(mode="json")})
        except KeyError:
            return APIResponse(status="not_found", errors=[{"code": "NOT_FOUND", "message": "object not found"}])


    def _authorize_run(self, principal: APIPrincipal, project_id: str, run_id: str, task_store: TaskStore) -> APIResponse | None:
        denied = self._authorize(principal, project_id)
        if denied:
            return denied
        run = task_store.get_run(run_id)
        if run is None or run["project_id"] != project_id:
            return APIResponse(status="not_found", errors=[{"code": "NOT_FOUND", "message": "object not found"}])
        return None

    def _authorize(self, principal: APIPrincipal, project_id: str) -> APIResponse | None:
        if project_id not in principal.project_ids:
            return APIResponse(status="not_found", errors=[{"code": "NOT_FOUND", "message": "object not found"}])
        return None


