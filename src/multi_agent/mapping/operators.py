from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from multi_agent.domain.observations import TypedValue


MISSING_MARKERS = {"", "na", "n/a", "null", "none", "未测", "缺失"}


@dataclass(frozen=True)
class TransformResult:
    value: TypedValue | None
    error_code: str | None = None
    message: str | None = None


def parse_number(raw: Any) -> TransformResult:
    if raw is None:
        return TransformResult(TypedValue(value_type="missing", missing_reason="source_null"))
    if isinstance(raw, str) and raw.strip().lower() in MISSING_MARKERS:
        return TransformResult(TypedValue(value_type="missing", missing_reason=f"source_marker:{raw.strip()}"))
    if isinstance(raw, (int, float)):
        return TransformResult(TypedValue(value_type="number", value=raw, comparator="="))
    text = str(raw).strip()
    match = re.fullmatch(r"(<|<=|=|>=|>)?\s*(-?\d+(?:\.\d+)?)", text)
    if not match:
        return TransformResult(None, "CONVERSION_FAILED", "value is not a number")
    comparator = match.group(1) or "="
    number_text = match.group(2)
    number: int | float = int(number_text) if "." not in number_text else float(number_text)
    return TransformResult(TypedValue(value_type="number", value=number, comparator=comparator))


def parse_string(raw: Any) -> TransformResult:
    if raw is None:
        return TransformResult(TypedValue(value_type="missing", missing_reason="source_null"))
    text = str(raw).strip()
    if text.lower() in MISSING_MARKERS:
        return TransformResult(TypedValue(value_type="missing", missing_reason=f"source_marker:{text}"))
    return TransformResult(TypedValue(value_type="string", value=text))


def validate_join_cardinality(
    left_rows: list[dict[str, Any]],
    right_rows: list[dict[str, Any]],
    left_key: str,
    right_key: str,
    expected: str,
) -> list[dict[str, Any]]:
    left_counts = Counter(row.get(left_key) for row in left_rows)
    right_counts = Counter(row.get(right_key) for row in right_rows)
    failures: list[dict[str, Any]] = []
    for key, count in left_counts.items():
        if key in (None, ""):
            failures.append({"code": "JOIN_EMPTY_KEY", "side": "left", "key": key})
        if expected in {"one_to_one", "one_to_many"} and count > 1:
            failures.append({"code": "JOIN_CARDINALITY_VIOLATION", "side": "left", "key": key})
    for key, count in right_counts.items():
        if key in (None, ""):
            failures.append({"code": "JOIN_EMPTY_KEY", "side": "right", "key": key})
        if expected in {"one_to_one", "many_to_one"} and count > 1:
            failures.append({"code": "JOIN_CARDINALITY_VIOLATION", "side": "right", "key": key})
    return failures
