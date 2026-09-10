from __future__ import annotations

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
from evaluation.rag.run_c_hybrid import evaluate_case_by_text, query_for_case  # noqa: E402
from multi_agent.knowledge import (  # noqa: E402
    EmbeddingConfig,
    EmbeddingError,
    EmbeddingService,
    HybridRetriever,
    KnowledgeContextBuilder,
    KnowledgeDocumentLoader,
    KnowledgeIndex,
    KnowledgeRelevanceGate,
    OllamaEmbeddingClient,
    RelevanceGateConfig,
    build_index_manifest,
    stable_index_id,
)


def main() -> int:
    config = EmbeddingConfig.from_mapping(json.loads((ROOT / "configs/knowledge/rag.json").read_text(encoding="utf-8")))
    documents = KnowledgeDocumentLoader().load_manifest(ROOT / "configs/knowledge/documents.json", root=ROOT)
    manifest = build_index_manifest(documents, strategy_version="structured-markdown-parent-child/1")
    index = KnowledgeIndex.from_documents(documents)
    index.index_id = stable_index_id(manifest)
    index.manifest = manifest
    retriever = HybridRetriever(index, EmbeddingService(config, OllamaEmbeddingClient(config.base_url, config.model)))
    gate = KnowledgeRelevanceGate(RelevanceGateConfig.from_file(ROOT / "configs/knowledge/relevance.json"))
    cases = load_cases(ROOT / "evaluation/rag/dataset_a1.jsonl")

    try:
        retriever.build_vectors()
        results = []
        packages = []
        for case in cases:
            query = query_for_case(case)
            hits = retriever.search(query, limit=10)
            package = KnowledgeContextBuilder(index, relevance_gate=gate).build(query, hits)
            usable_hits = hits if package.status == "success" else []
            result = evaluate_case_by_text(case, usable_hits)
            result["answerability"] = package.answerability.model_dump(mode="json") if package.answerability else None
            results.append(result)
            if len(packages) < 8 and package.status != "success":
                packages.append(package.model_dump(mode="json"))
        payload = {
            "schema_version": "rag_e_relevance_gate_eval/1",
            "status": "success",
            "summary": summarize(results),
            "results": results,
            "sample_rejections": packages,
        }
    except EmbeddingError as exc:
        payload = {"schema_version": "rag_e_relevance_gate_eval/1", "status": "unavailable", "error": str(exc)}

    out_json = ROOT / "evaluation/rag/relevance_gate_e_results.json"
    out_md = ROOT / "evaluation/rag/relevance_gate_e.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(out_md, payload)
    print(json.dumps({key: payload[key] for key in payload if key in {"status", "summary", "error"}}, ensure_ascii=False))
    return 0 if payload["status"] == "success" else 2


def write_markdown(path: Path, payload: dict[str, object]) -> None:
    lines = ["# RAG E Relevance Gate", ""]
    if payload["status"] != "success":
        lines.extend([f"Status: `{payload['status']}`", f"Error: {payload.get('error', '')}", ""])
    else:
        summary = payload["summary"]
        lines.extend([
            f"- Status: `{payload['status']}`",
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
