from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


COMMON_FIELDS = ("status", "engine", "project_id")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare deterministic public fields between two run outputs.")
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    args = parser.parse_args()
    left = json.loads(args.left.read_text(encoding="utf-8"))
    right = json.loads(args.right.read_text(encoding="utf-8"))
    print(json.dumps(compare(left, right), ensure_ascii=False, indent=2))
    return 0


def compare(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    differences = []
    for field in COMMON_FIELDS:
        if left.get(field) != right.get(field):
            differences.append(
                {
                    "field": field,
                    "left": left.get(field),
                    "right": right.get(field),
                    "classification": "unknown",
                }
            )
    return {
        "status": "success",
        "comparison_scope": "deterministic_public_fields",
        "differences": differences,
        "note": "Natural-language report text is intentionally excluded.",
    }


if __name__ == "__main__":
    raise SystemExit(main())
