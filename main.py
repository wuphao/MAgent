from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path



DEFAULT_CASE = Path("output/patient_041_S_4060_analysis.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze one exported RWE patient file.")
    parser.add_argument(
        "--engine",
        choices=("v2", "legacy"),
        default="v2",
        help="Select the traceable v2 engine or the legacy agent pipeline. Default: v2.",
    )
    parser.add_argument("case", nargs="?", type=Path, default=DEFAULT_CASE)
    parser.add_argument(
        "--use-llm", action="store_true",
        help="Legacy engine only: use DeepSeek in every Agent while preserving deterministic values.",
    )
    parser.add_argument("--full", action="store_true", help="Legacy engine only: print all agent outputs instead of the final report.")
    parser.add_argument("--output", type=Path, help="Optionally save the analysis JSON.")
    parser.add_argument("--project-id", default="stage08", help="v2 project namespace.")
    parser.add_argument("--source-namespace", default="default-source", help="v2 source namespace.")
    parser.add_argument("--data-dir", type=Path, default=Path("data/v2"), help="v2 storage directory.")
    parser.add_argument("--mapping", type=Path, help="v2 mapping config. When omitted, v2 runs source inventory only.")
    parser.add_argument(
        "--v2-goal",
        choices=["source_inventory", "xx_v1_assessment", "longitudinal_xx_v1", "multi_source_summary", "multimodal_summary", "rwe_patient_summary"],
        default="source_inventory",
        help="v2 analysis goal after deterministic adaptation. Requires --mapping except for source_inventory.",
    )
    parser.add_argument("--task-db", type=Path, default=Path("data/v2/tasks.sqlite3"), help="v2 task database path.")
    parser.add_argument("--parallel", action="store_true", help="v2: run ready tasks in parallel when possible.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.engine == "v2":
        result = _run_v2(args)
        rendered = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        print(rendered)
        return 0

    result = _run_legacy(args)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0



def _run_legacy(args: argparse.Namespace) -> dict:
    from archive.legacy_main_chain.case_memory import init_case_memory
    from archive.legacy_main_chain.orchestrator import Orchestrator

    with args.case.open("r", encoding="utf-8") as stream:
        raw = json.load(stream)

    memory = Orchestrator(use_llm=args.use_llm).run(init_case_memory(raw))
    return memory if args.full else memory["final_report"]

def _run_v2(args: argparse.Namespace) -> dict:
    src_path = Path(__file__).resolve().parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    if args.v2_goal == "rwe_patient_summary":
        from uuid import uuid4
        from multi_agent.application.rwe_service import analyze_file

        document = json.loads(args.case.read_text(encoding="utf-8-sig"))
        patient_number = (document.get("patient") or {}).get("patient_number")
        if not patient_number:
            raise SystemExit("RWE JSON 缺少 patient.patient_number")
        run_dir = args.data_dir / "rwe" / uuid4().hex
        run_dir.mkdir(parents=True)
        return analyze_file(args.case, run_dir, patient_number)
    if args.v2_goal == "source_inventory" and args.mapping is None:
        from multi_agent.application.cli import run_inventory

        return run_inventory(
            case_path=args.case,
            project_id=args.project_id,
            source_namespace=args.source_namespace,
            data_dir=args.data_dir,
        )
    if args.mapping is None:
        raise SystemExit("v2 goals other than source_inventory require --mapping")

    from multi_agent.application.adapt_cli import run_adaptation
    from multi_agent.domain.requests import AnalysisRequest
    from multi_agent.orchestration.planner import TemplatePlanner
    from multi_agent.orchestration.scheduler import Scheduler
    from multi_agent.registries.capabilities import CapabilityRegistry
    from multi_agent.storage.sqlite import EvidenceRepository, SQLiteStore
    from multi_agent.storage.tasks import TaskStore

    adaptation = run_adaptation(
        input_path=args.case,
        mapping_path=args.mapping,
        project_id=args.project_id,
        source_namespace=args.source_namespace,
        data_dir=args.data_dir,
    )
    capabilities = CapabilityRegistry.from_directory(Path("configs/capabilities"))
    evidence_db = args.data_dir / "stage02.sqlite3"
    observations = EvidenceRepository(SQLiteStore(evidence_db)).list_observations(args.project_id)
    request = AnalysisRequest(project_id=args.project_id, goal=args.v2_goal, as_of=datetime.now(timezone.utc))
    plan = TemplatePlanner().plan(
        request,
        {spec.capability_id for spec in capabilities.available_for_production()},
        {item.concept_id for item in observations},
    )
    run = Scheduler(TaskStore(args.task_db), evidence_db, capabilities).run(request, plan, parallel=args.parallel)
    return {"status": run["status"], "engine": "v2-stage08", "adaptation": adaptation, "analysis_run": run}


if __name__ == "__main__":
    raise SystemExit(main())
