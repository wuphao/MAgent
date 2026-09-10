from __future__ import annotations

from pathlib import Path

from evaluation.rag.run_a0_baseline import evaluate_case, load_cases, load_documents, summarize
from multi_agent.knowledge import ExactRetriever, KnowledgeIndex


def test_rag_a0_probe_dataset_runs_against_exact_retriever() -> None:
    root = Path(__file__).resolve().parents[2]
    cases = load_cases(root / "evaluation/rag/dataset.jsonl")
    documents = load_documents(root / "configs/knowledge/documents.json")
    retriever = ExactRetriever(KnowledgeIndex.from_documents(documents))

    results = [evaluate_case(case, retriever.search(case.question, limit=10)) for case in cases]
    summary = summarize(results)

    assert summary["case_count"] == 12
    assert summary["answerable_count"] == 9
    assert summary["no_answer_count"] == 3
    assert summary["hit_at_10"]["hits"] >= 1
    assert summary["status_counts"]["miss"] >= 1
    assert summary["status_counts"]["false_positive"] >= 1


def test_rag_a1_formal_dataset_has_split_and_answerability_coverage() -> None:
    root = Path(__file__).resolve().parents[2]
    cases = load_cases(root / "evaluation/rag/dataset_a1.jsonl")

    assert len(cases) == 40
    assert sum(1 for case in cases if case.expected_answerable) >= 20
    assert sum(1 for case in cases if not case.expected_answerable) >= 10
    assert {tag for case in cases for tag in case.tags} >= {
        "answerable",
        "conflict",
        "missing",
        "no-answer",
        "scoring",
        "wrong-version",
    }
