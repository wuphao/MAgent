from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, wait
from pathlib import Path
from typing import Any

from multi_agent.agents.base import TaskContext
from multi_agent.capabilities.invoker import CapabilityInvoker
from multi_agent.domain.capabilities import AgentResult
from multi_agent.domain.requests import AnalysisRequest
from multi_agent.domain.tasks import Plan, TaskRecord, TaskSpec
from multi_agent.orchestration.executor import TaskExecutor
from multi_agent.orchestration.plan_validator import PlanValidator
from multi_agent.orchestration.resources import make_executor
from multi_agent.registries.capabilities import CapabilityRegistry
from multi_agent.storage.sqlite import EvidenceRepository, SQLiteStore
from multi_agent.storage.tasks import BudgetLedger, TaskStore


TERMINAL_STATES = {"succeeded", "failed", "skipped", "needs_metadata"}


class Scheduler:
    def __init__(
        self,
        task_store: TaskStore,
        evidence_db: Path,
        capabilities: CapabilityRegistry,
        instruments_path: Path = Path("configs/instruments"),
    ):
        self.task_store = task_store
        self.evidence_db = evidence_db
        self.capabilities = capabilities
        self.executor = TaskExecutor(instruments_path)

    def run(self, request: AnalysisRequest, plan: Plan, parallel: bool = False) -> dict[str, Any]:
        validation = PlanValidator(self.capabilities).validate(request, plan)
        if not validation.valid:
            return {"status": "invalid_plan", "run_id": plan.run_id, "errors": validation.errors, "executed": 0}
        self.task_store.create_run(request, plan)
        observations = EvidenceRepository(SQLiteStore(self.evidence_db)).list_observations(request.project_id)
        context = TaskContext(project_id=request.project_id, goal=request.goal, observations=observations, run_id=plan.run_id, snapshot_id=request.snapshot_id)
        capability_specs = {spec.capability_id: spec for spec in self.capabilities.available_for_production()}
        invoker = CapabilityInvoker(capability_specs)
        ledger = BudgetLedger(
            self.task_store,
            plan.run_id,
            max_calls=request.budget.max_calls,
            max_tokens=request.budget.max_tokens,
        )
        if request.cancel_requested:
            self.task_store.set_cancel_requested(plan.run_id)
        executed = self._run_parallel(plan, context, invoker, ledger) if parallel else self._run_serial(plan, context, invoker, ledger)
        return {
            "status": "success",
            "run_id": plan.run_id,
            "executed": executed,
            "tasks": [record.model_dump(mode="json") for record in self.task_store.get_tasks(plan.run_id)],
            "budget_ledger": ledger.entries(),
        }

    def _run_serial(self, plan: Plan, context: TaskContext, invoker: CapabilityInvoker, ledger: BudgetLedger) -> int:
        executed = 0
        while True:
            ready = self._ready_tasks(plan.run_id)
            if not ready:
                break
            for record in ready:
                executed += self._execute_record(record, context, invoker, ledger)
        self._skip_blocked(plan.run_id)
        return executed

    def _run_parallel(self, plan: Plan, context: TaskContext, invoker: CapabilityInvoker, ledger: BudgetLedger) -> int:
        executed = 0
        with make_executor() as pool:
            futures: dict[Future[int], str] = {}
            while True:
                if not self.task_store.cancel_requested(plan.run_id):
                    for record in self._ready_tasks(plan.run_id):
                        if record.spec.task_id in futures.values():
                            continue
                        if record.state == "pending":
                            self.task_store.transition(plan.run_id, record.spec.task_id, "pending", "ready")
                        if self.task_store.transition(plan.run_id, record.spec.task_id, "ready", "running"):
                            futures[pool.submit(self._run_running_record, record, self._context_for_task(context, record.run_id, record.spec), invoker, ledger)] = record.spec.task_id
                if not futures:
                    break
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    futures.pop(future)
                    executed += future.result()
            self._skip_blocked(plan.run_id)
        return executed

    def _ready_tasks(self, run_id: str) -> list[TaskRecord]:
        if self.task_store.cancel_requested(run_id):
            return []
        records = self.task_store.get_tasks(run_id)
        by_id = {record.spec.task_id: record for record in records}
        ready: list[TaskRecord] = []
        for record in records:
            if record.state not in {"pending", "ready"}:
                continue
            deps_ready = True
            for dep in record.spec.depends_on:
                parent = by_id[dep.task_id]
                if dep.mode == "required_success" and parent.state != "succeeded":
                    deps_ready = False
                if dep.mode == "terminal" and parent.state not in TERMINAL_STATES:
                    deps_ready = False
            if deps_ready:
                ready.append(record)
        return ready

    def _execute_record(self, record: TaskRecord, context: TaskContext, invoker: CapabilityInvoker, ledger: BudgetLedger) -> int:
        if record.state == "pending" and not self.task_store.transition(record.run_id, record.spec.task_id, "pending", "ready"):
            return 0
        if not self.task_store.transition(record.run_id, record.spec.task_id, "ready", "running"):
            return 0
        return self._run_running_record(record, self._context_for_task(context, record.run_id, record.spec), invoker, ledger)

    def _context_for_task(self, context: TaskContext, run_id: str, task: TaskSpec) -> TaskContext:
        task_results = {
            record.spec.task_id: record.result
            for record in self.task_store.get_tasks(run_id)
            if record.result is not None
        }
        return context.model_copy(update={"task_results": task_results, "task_parameters": task.parameters})

    def _run_running_record(self, record: TaskRecord, context: TaskContext, invoker: CapabilityInvoker, ledger: BudgetLedger) -> int:
        task = record.spec
        attempt = record.attempts + 1
        reserve_calls = int(task.budget.get("calls", 0) or 0)
        reserve_tokens = int(task.budget.get("tokens", 0) or 0)
        if (reserve_calls or reserve_tokens) and not ledger.reserve(f"reserve-{task.task_id}-{attempt}", task.task_id, reserve_calls, reserve_tokens):
            self.task_store.record_attempt(record.run_id, task.task_id, attempt, "failed", "BUDGET_EXCEEDED", "budget reservation failed")
            self.task_store.transition(record.run_id, task.task_id, "running", "failed")
            return 0
        try:
            result = self.executor.execute(task, context, invoker)
        except Exception as exc:
            retryable = type(exc).__name__ in task.retry_policy.retryable_errors and attempt < task.retry_policy.max_attempts
            self.task_store.record_attempt(record.run_id, task.task_id, attempt, "retry_wait" if retryable else "failed", type(exc).__name__, str(exc))
            self.task_store.transition(record.run_id, task.task_id, "running", "retry_wait" if retryable else "failed")
            if retryable:
                self.task_store.transition(record.run_id, task.task_id, "retry_wait", "ready")
            return 1
        payload = result.model_dump(mode="json") if isinstance(result, AgentResult) else result
        self.task_store.store_result(record.run_id, task.task_id, payload)
        status = payload.get("status")
        if status in {"needs_data", "no_data"} and task.required:
            self.task_store.record_attempt(record.run_id, task.task_id, attempt, "failed", status, "required task did not have enough data")
            self.task_store.transition(record.run_id, task.task_id, "running", "failed")
        else:
            self.task_store.record_attempt(record.run_id, task.task_id, attempt, "succeeded")
            self.task_store.transition(record.run_id, task.task_id, "running", "succeeded")
        ledger.settle(f"settle-{task.task_id}-{attempt}", task.task_id, 0, 0, cost=None, usage_unknown=False)
        return 1

    def _skip_blocked(self, run_id: str) -> None:
        records = self.task_store.get_tasks(run_id)
        terminal = {record.spec.task_id: record.state for record in records if record.state in TERMINAL_STATES}
        for record in records:
            if record.state != "pending":
                continue
            if self.task_store.cancel_requested(run_id):
                self.task_store.transition(run_id, record.spec.task_id, "pending", "skipped")
                continue
            if any(dep.task_id in terminal for dep in record.spec.depends_on):
                self.task_store.transition(run_id, record.spec.task_id, "pending", "skipped")



