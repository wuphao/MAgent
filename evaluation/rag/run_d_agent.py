from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from multi_agent.agents.base import TaskContext  # noqa: E402
from multi_agent.agents.knowledge import KnowledgeAgent  # noqa: E402
from multi_agent.capabilities.invoker import CapabilityInvoker  # noqa: E402


def run_case(case_id: str, question: str, instrument_versions: list[str] | None = None) -> dict:
    task_parameters = {"question": question}
    if instrument_versions is not None:
        task_parameters["instrument_versions"] = instrument_versions
    context = TaskContext(
        project_id="stage_d",
        goal="knowledge_agent_contract",
        observations=[],
        task_parameters=task_parameters,
    )
    result = KnowledgeAgent().execute(context, CapabilityInvoker({}))
    return {"case_id": case_id, "result": result.model_dump(mode="json")}


def main() -> int:
    payload = {
        "schema_version": "rag_d_agent_eval/1",
        "cases": [
            run_case("scoring_definition", "XX-v1 total 是怎么计算的？", ["xx-v1"]),
            run_case("missing_rule", "缺失条目能不能按 0 自动填补？", ["xx-v1"]),
            run_case("wrong_version", "XX-v2 total 怎么算？"),
            {"case_id": "missing_question", "result": KnowledgeAgent().execute(
                TaskContext(project_id="stage_d", goal="knowledge_agent_contract", observations=[]),
                CapabilityInvoker({}),
            ).model_dump(mode="json")},
        ],
    }
    out = ROOT / "evaluation/rag/knowledge_agent_d.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"case_count": len(payload["cases"]), "out": str(out.relative_to(ROOT))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
