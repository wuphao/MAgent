from __future__ import annotations

import argparse
import json
from pathlib import Path

from case_memory import init_case_memory
from explainable_report import ExplainableReportBuilder, render_markdown
from orchestrator import Orchestrator


DEFAULT_CASE = Path("output/patient_041_S_4060_analysis.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an explainable RWE report in JSON and Markdown.")
    parser.add_argument("case", nargs="?", type=Path, default=DEFAULT_CASE)
    parser.add_argument("--output-dir", type=Path, default=Path("output/reports"))
    parser.add_argument("--no-llm", action="store_true", help="Use deterministic explanations only.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw = json.loads(args.case.read_text(encoding="utf-8"))
    memory = Orchestrator(use_llm=False).run(init_case_memory(raw))
    report = ExplainableReportBuilder(use_llm=not args.no_llm).build(memory)

    patient_number = (raw.get("patient") or {}).get("patient_number") or args.case.stem
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{patient_number}_explainable_report.json"
    markdown_path = args.output_dir / f"{patient_number}_explainable_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({
        "status": "success",
        "llm_status": report["explainability"]["llm_status"],
        "json_report": str(json_path.resolve()),
        "markdown_report": str(markdown_path.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
