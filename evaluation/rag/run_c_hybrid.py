from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from evaluation.rag.run_a0_baseline import load_cases, summarize  # noqa: E402
from multi_agent.knowledge import (  # noqa: E402
    EmbeddingConfig,
    EmbeddingError,
    EmbeddingService,
    HybridRetriever,
    KnowledgeContextBuilder,
    KnowledgeDocumentLoader,
    KnowledgeIndex,
    KnowledgeQuery,
    OllamaEmbeddingClient,
    build_index_manifest,
    stable_index_id,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the C-stage hybrid retrieval evaluation.")
    parser.add_argument("--dataset", type=Path, default=ROOT / "evaluation/rag/dataset_a1.jsonl")
    parser.add_argument("--documents", type=Path, default=ROOT / "configs/knowledge/documents.json")
    parser.add_argument("--rag-config", type=Path, default=ROOT / "configs/knowledge/rag.json")
    parser.add_argument("--out-json", type=Path, default=ROOT / "evaluation/rag/hybrid_c_results.json")
    parser.add_argument("--out-md", type=Path, default=ROOT / "evaluation/rag/hybrid_c.md")
    args = parser.parse_args()

    config = EmbeddingConfig.from_mapping(json.loads(args.rag_config.read_text(encoding="utf-8")))
    documents = KnowledgeDocumentLoader().load_manifest(args.documents, root=ROOT)
    manifest = build_index_manifest(documents, strategy_version="structured-markdown-parent-child/1")
    index = KnowledgeIndex.from_documents(documents)
    index.index_id = stable_index_id(manifest)
    index.manifest = manifest
    service = EmbeddingService(config, OllamaEmbeddingClient(config.base_url, config.model))
    retriever = HybridRetriever(index, service)
    cases = load_cases(args.dataset)

    try:
        retriever.build_vectors()
        results = [
            evaluate_case_by_text(
                case,
                retriever.search(query_for_case(case), limit=10),
            )
            for case in cases
        ]
        summary = summarize(results)
        packages = [
            KnowledgeContextBuilder(index).build(
                query_for_case(case),
                retriever.search(query_for_case(case), limit=3),
            ).model_dump(mode="json")
            for case in cases[:5]
        ]
        payload = {
            "schema_version": "rag_c_hybrid_eval/1",
            "status": "success",
            "retriever": "HybridRetriever",
            "dataset": str(args.dataset.resolve().relative_to(ROOT)),
            "index_id": index.index_id,
            "summary": summary,
            "results": results,
            "sample_evidence_packages": packages,
        }
    except EmbeddingError as exc:
        payload = {
            "schema_version": "rag_c_hybrid_eval/1",
            "status": "unavailable",
            "error": str(exc),
            "retriever": "HybridRetriever",
            "dataset": str(args.dataset),
        }

    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.out_md, payload)
    print(json.dumps({key: payload[key] for key in payload if key in {"status", "summary", "error"}}, ensure_ascii=False))
    return 0 if payload["status"] == "success" else 2


def evaluate_case_by_text(case, hits: list[object]) -> dict[str, object]:
    dumped_hits = [hit.model_dump(mode="json") for hit in hits]
    matching_ranks: list[int] = []
    for rank, hit in enumerate(dumped_hits, start=1):
        if any(hit_matches_gold_text(hit, gold) for gold in case.gold_evidence):
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


def query_for_case(case) -> KnowledgeQuery:
    lowered = case.question.lower()
    if "xx-v2" in lowered:
        versions = ["xx-v2"]
    elif "xx-v1" in lowered:
        versions = ["xx-v1"]
    else:
        versions = []
    return KnowledgeQuery(question=case.question, instrument_versions=versions)


def hit_matches_gold_text(hit: dict[str, object], gold: dict[str, object]) -> bool:
    chunk = hit["chunk"]
    if chunk["document_id"] != gold["document_id"]:
        return False
    if chunk["document_version"] != gold["document_version"]:
        return False
    required_text = gold.get("required_text")
    return not required_text or str(required_text) in chunk["text"]


def write_markdown(path: Path, payload: dict[str, object]) -> None:
    lines = ["# RAG C Hybrid Retrieval", ""]
    if payload["status"] != "success":
        lines.extend([f"Status: `{payload['status']}`", "", f"Error: {payload.get('error', '')}", ""])
    else:
        summary = payload["summary"]
        lines.extend([
            f"- Status: `{payload['status']}`",
            f"- Index: `{payload['index_id']}`",
            f"- Cases: {summary['case_count']}",
            f"- Answerable Hit@10: {summary['hit_at_10']['hits']}/{summary['hit_at_10']['total']} ({summary['hit_at_10']['rate']})",
            f"- Answerable MRR@10: {summary['mrr_at_10']}",
            f"- Correct no-answer: {summary['correct_no_answer']['correct']}/{summary['correct_no_answer']['total']} ({summary['correct_no_answer']['rate']})",
            f"- Status counts: `{json.dumps(summary['status_counts'], ensure_ascii=False)}`",
            "",
        ])
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
