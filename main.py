import json
import json
from pathlib import Path

from case_memory import init_case_memory
from orchestrator import Orchestrator


def main():
    case_path = Path("data/case_001.json")
    with case_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    memory = init_case_memory(raw)
    memory = Orchestrator().run(memory)

    print(json.dumps(memory["final_report"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
