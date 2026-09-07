from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from multi_agent.domain.requests import AnalysisRequest, BudgetLimit
from multi_agent.orchestration.plan_validator import PlanValidator
from multi_agent.orchestration.planner import TemplatePlanner
from multi_agent.orchestration.scheduler import Scheduler
from multi_agent.registries.capabilities import CapabilityRegistry
from multi_agent.storage.sqlite import EvidenceRepository, SQLiteStore
from multi_agent.storage.tasks import TaskStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan and run stage05 goal-driven tasks.")
    parser.add_argument("--evidence-db", type=Path, required=True)
    parser.add_argument("--task-db", type=Path, default=Path("data/v2/tasks.sqlite3"))
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--goal", choices=["source_inventory", "xx_v1_assessment", "longitudinal_xx_v1", "multi_source_summary", "multimodal_summary"], required=True)
    parser.add_argument("--capabilities", type=Path, default=Path("configs/capabilities"))
    parser.add_argument("--instruments", type=Path, default=Path("configs/instruments"))
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--parallel", action="store_true")
    parser.add_argument("--max-calls", type=int, default=0)
    parser.add_argument("--max-tokens", type=int, default=0)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    capabilities = CapabilityRegistry.from_directory(args.capabilities)
    observations = EvidenceRepository(SQLiteStore(args.evidence_db)).list_observations(args.project_id)
    request = AnalysisRequest(
        project_id=args.project_id,
        goal=args.goal,
        as_of=datetime.now(timezone.utc),
        budget=BudgetLimit(max_calls=args.max_calls, max_tokens=args.max_tokens),
    )
    plan = TemplatePlanner().plan(
        request,
        available_capabilities={spec.capability_id for spec in capabilities.available_for_production()},
        present_concepts={item.concept_id for item in observations},
    )
    validation = PlanValidator(capabilities).validate(request, plan)
    if args.plan_only:
        result = {
            "status": "plan",
            "request": request.model_dump(mode="json"),
            "plan": plan.model_dump(mode="json"),
            "validation": validation.model_dump(mode="json"),
        }
    else:
        scheduler = Scheduler(TaskStore(args.task_db), args.evidence_db, capabilities, args.instruments)
        result = scheduler.run(request, plan, parallel=args.parallel)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

