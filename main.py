from __future__ import annotations

import argparse
import json
from pathlib import Path

from case_memory import init_case_memory
from orchestrator import Orchestrator


DEFAULT_CASE = Path("output/patient_041_S_4060_analysis.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze one exported RWE patient JSON.")
    parser.add_argument("case", nargs="?", type=Path, default=DEFAULT_CASE)
    parser.add_argument(
        "--use-llm", action="store_true",
        help="Use DeepSeek in every Agent while preserving deterministic values.",
    )
    parser.add_argument("--full", action="store_true", help="Print all agent outputs instead of the final report.")
    parser.add_argument("--output", type=Path, help="Optionally save the analysis JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with args.case.open("r", encoding="utf-8") as stream:
        raw = json.load(stream)

    memory = Orchestrator(use_llm=args.use_llm).run(init_case_memory(raw))
    result = memory if args.full else memory["final_report"]
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
