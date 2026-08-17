from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class EvaluationSummary:
    questions: int
    recall_at_k: float
    mean_reciprocal_rank: float
    keyword_recall: float


def evaluate_retrieval(
    search: Callable[[str], list[dict[str, object]]],
    dataset_path: Path,
) -> EvaluationSummary:
    """Evaluate JSONL cases with question, expected_sources and expected_keywords."""
    cases = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if not cases:
        raise ValueError("Evaluation dataset is empty.")
    hits = reciprocal_sum = keyword_sum = 0.0
    for case in cases:
        results = search(str(case["question"]))
        expected_sources = {Path(value).name.lower() for value in case.get("expected_sources", [])}
        rank = 0
        for index, result in enumerate(results, start=1):
            metadata = result.get("metadata", {})
            actual = Path(str(metadata.get("file_name") or metadata.get("source", ""))).name.lower()
            if actual in expected_sources:
                rank = index
                break
        if rank:
            hits += 1
            reciprocal_sum += 1 / rank
        combined = "\n".join(str(result.get("content", "")) for result in results).lower()
        keywords = [str(value).lower() for value in case.get("expected_keywords", [])]
        keyword_sum += sum(value in combined for value in keywords) / len(keywords) if keywords else 1.0
    total = len(cases)
    return EvaluationSummary(total, hits / total, reciprocal_sum / total, keyword_sum / total)
