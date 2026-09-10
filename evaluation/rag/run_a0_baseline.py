from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from multi_agent.knowledge import ExactRetriever, KnowledgeDocumentLoader, KnowledgeIndex  # noqa: E402


@dataclass(frozen=True)
class ProbeCase:
    case_id: str
    question: str
    expected_answerable: bool
    gold_evidence: list[dict[str, Any]]
    tags: list[str]


def load_cases(path: Path) -> list[ProbeCase]:
    cases: list[ProbeCase] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        raw = json.loads(line)
        cases.append(
            ProbeCase(
                case_id=raw["case_id"],
                question=raw["question"],
                expected_answerable=bool(raw["expected_answerable"]),
                gold_evidence=list(raw.get("gold_evidence", [])),
                tags=list(raw.get("tags", [])),
            )
        )
    return cases


def load_documents(manifest_path: Path):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    loader = KnowledgeDocumentLoader()
    documents = []
    for item in manifest["documents"]:
        source_path = ROOT / item["path"]
        if item["source_type"] != "markdown":
            raise ValueError(f"Unsupported A0 source_type for {item['document_id']}: {item['source_type']}")
        documents.append(
            loader.load_markdown(
                source_path,
                document_id=item["document_id"],
                version=item["version"],
                title=item.get("title"),
            )
        )
    return documents


def hit_matches_gold(hit: dict[str, Any], gold: dict[str, Any]) -> bool:
    chunk = hit["chunk"]
    if chunk["document_id"] != gold["document_id"]:
        return False
    if chunk["document_version"] != gold["document_version"]:
        return False
    if chunk["locator"] != gold["locator"]:
        return False
    required_text = gold.get("required_text")
    return not required_text or required_text in chunk["text"]


def evaluate_case(case: ProbeCase, hits: list[Any]) -> dict[str, Any]:
    dumped_hits = [hit.model_dump(mode="json") for hit in hits]
    matching_ranks: list[int] = []
    for rank, hit in enumerate(dumped_hits, start=1):
        if any(hit_matches_gold(hit, gold) for gold in case.gold_evidence):
            matching_ranks.append(rank)

    retrieved_any = bool(dumped_hits)
    hit_at_10 = bool(matching_ranks)
    if case.expected_answerable:
        status = "hit" if hit_at_10 else "miss"
    else:
        status = "false_positive" if retrieved_any else "correct_no_answer"

    return {
        "case_id": case.case_id,
        "question": case.question,
        "tags": case.tags,
        "expected_answerable": case.expected_answerable,
        "status": status,
        "hit_at_10": hit_at_10,
        "first_gold_rank": matching_ranks[0] if matching_ranks else None,
        "retrieved_count": len(dumped_hits),
        "top_hits": dumped_hits,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [item for item in results if item["expected_answerable"]]
    no_answer = [item for item in results if not item["expected_answerable"]]
    hits = [item for item in answerable if item["hit_at_10"]]
    reciprocal_ranks = [1 / item["first_gold_rank"] for item in answerable if item["first_gold_rank"]]
    correct_no_answer = [item for item in no_answer if item["status"] == "correct_no_answer"]
    return {
        "case_count": len(results),
        "answerable_count": len(answerable),
        "no_answer_count": len(no_answer),
        "hit_at_10": {
            "hits": len(hits),
            "total": len(answerable),
            "rate": round(len(hits) / len(answerable), 4) if answerable else None,
        },
        "mrr_at_10": round(sum(reciprocal_ranks) / len(answerable), 4) if answerable else None,
        "correct_no_answer": {
            "correct": len(correct_no_answer),
            "total": len(no_answer),
            "rate": round(len(correct_no_answer) / len(no_answer), 4) if no_answer else None,
        },
        "status_counts": {
            status: sum(1 for item in results if item["status"] == status)
            for status in sorted({item["status"] for item in results})
        },
    }


def write_markdown(path: Path, summary: dict[str, Any], results: list[dict[str, Any]]) -> None:
    lines = [
        "# RAG Exact Retrieval Baseline",
        "",
        "Generated from `evaluation/rag/run_a0_baseline.py` using the current `ExactRetriever`.",
        "",
        "## Summary",
        "",
        f"- Cases: {summary['case_count']}",
        f"- Answerable Hit@10: {summary['hit_at_10']['hits']}/{summary['hit_at_10']['total']} ({summary['hit_at_10']['rate']})",
        f"- Answerable MRR@10: {summary['mrr_at_10']}",
        f"- Correct no-answer: {summary['correct_no_answer']['correct']}/{summary['correct_no_answer']['total']} ({summary['correct_no_answer']['rate']})",
        f"- Status counts: `{json.dumps(summary['status_counts'], ensure_ascii=False)}`",
        "",
        "## Case Results",
        "",
        "| Case | Status | First gold rank | Top hit |",
        "|---|---|---:|---|",
    ]
    for item in results:
        top_hit = "None"
        if item["top_hits"]:
            chunk = item["top_hits"][0]["chunk"]
            top_hit = f"{chunk['document_id']} {chunk['document_version']} {chunk['locator']} score={item['top_hits'][0]['score']}"
        lines.append(f"| {item['case_id']} | {item['status']} | {item['first_gold_rank'] or ''} | {top_hit} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the A0 exact-retrieval baseline.")
    parser.add_argument("--dataset", type=Path, default=ROOT / "evaluation/rag/dataset.jsonl")
    parser.add_argument("--documents", type=Path, default=ROOT / "configs/knowledge/documents.json")
    parser.add_argument("--out-json", type=Path, default=ROOT / "evaluation/rag/baseline_results.json")
    parser.add_argument("--out-md", type=Path, default=ROOT / "evaluation/rag/baseline.md")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    cases = load_cases(args.dataset)
    documents = load_documents(args.documents)
    retriever = ExactRetriever(KnowledgeIndex.from_documents(documents))
    results = [evaluate_case(case, retriever.search(case.question, limit=args.limit)) for case in cases]
    summary = summarize(results)
    payload = {
        "schema_version": "rag_a0_baseline/1",
        "retriever": "ExactRetriever",
        "dataset": display_path(args.dataset),
        "documents": display_path(args.documents),
        "summary": summary,
        "results": results,
    }

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.out_md, summary, results)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
