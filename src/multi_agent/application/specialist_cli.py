from __future__ import annotations

import argparse
import json
from pathlib import Path

from multi_agent.agents.assessment import AssessmentAgent
from multi_agent.agents.base import TaskContext
from multi_agent.agents.laboratory_genetics import LaboratoryGeneticsAgent
from multi_agent.agents.longitudinal import LongitudinalAgent
from multi_agent.capabilities.invoker import CapabilityInvoker
from multi_agent.registries.capabilities import CapabilityRegistry
from multi_agent.registries.instruments import InstrumentRegistry
from multi_agent.storage.sqlite import EvidenceRepository, SQLiteStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run stage04 specialists over stored v2 observations.")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--project-id", default="stage02")
    parser.add_argument("--goal", default="xx_v1_assessment")
    parser.add_argument("--instruments", type=Path, default=Path("configs/instruments"))
    parser.add_argument("--capabilities", type=Path, default=Path("configs/capabilities"))
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_specialists(args.db, args.project_id, args.goal, args.instruments, args.capabilities)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0


def run_specialists(
    db_path: Path,
    project_id: str,
    goal: str,
    instruments_path: Path,
    capabilities_path: Path,
) -> dict:
    observations = EvidenceRepository(SQLiteStore(db_path)).list_observations(project_id)
    context = TaskContext(project_id=project_id, goal=goal, observations=observations)
    instruments = InstrumentRegistry.from_directory(instruments_path)
    capability_specs = CapabilityRegistry.from_directory(capabilities_path)
    invoker = CapabilityInvoker({spec.capability_id: spec for spec in capability_specs.available_for_production()})
    agents = [
        AssessmentAgent(instruments),
        LongitudinalAgent(),
        LaboratoryGeneticsAgent(),
    ]
    results = [agent.execute(context, invoker).model_dump(mode="json") for agent in agents]
    return {"status": "success", "engine": "v2-stage04", "project_id": project_id, "agent_results": results}


if __name__ == "__main__":
    raise SystemExit(main())
