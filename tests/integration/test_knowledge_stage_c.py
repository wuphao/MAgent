from __future__ import annotations

from pathlib import Path

from multi_agent.knowledge import (
    EmbeddingConfig,
    EmbeddingService,
    FakeEmbeddingClient,
    HybridRetriever,
    KnowledgeContextBuilder,
    KnowledgeDocumentLoader,
    KnowledgeIndex,
    KnowledgeQuery,
    KnowledgeRelevanceGate,
    RelevanceGateConfig,
)


def config() -> EmbeddingConfig:
    return EmbeddingConfig(
        provider="ollama",
        base_url="http://localhost:11434",
        model="qwen3-embedding:0.6b",
        document_template_version="rag-doc-embedding/1",
        query_template_version="rag-query-embedding/1",
        query_instruction="Query: {query}",
    )


def structured_index() -> KnowledgeIndex:
    root = Path(__file__).resolve().parents[2]
    documents = KnowledgeDocumentLoader().load_manifest(root / "configs/knowledge/documents.json", root=root)
    return KnowledgeIndex.from_documents(documents)


def test_hybrid_retriever_combines_lexical_and_vector_scores() -> None:
    index = structured_index()
    service = EmbeddingService(config(), FakeEmbeddingClient([[1, 0], [0, 1], [0, 1]]))
    retriever = HybridRetriever(index, service)
    retriever.build_vectors()

    hits = retriever.search(KnowledgeQuery(question="missing item should not be imputed as zero", instrument_versions=["xx-v1"]))

    assert hits
    assert hits[0].scores is not None
    assert hits[0].scores.rrf_score is not None
    assert hits[0].scores.mode in {"lexical", "vector", "lexical+vector"}


def test_hybrid_retriever_applies_instrument_version_filter_before_ranking() -> None:
    index = structured_index()
    retriever = HybridRetriever(index)

    hits = retriever.search(KnowledgeQuery(question="XX-v2 total 怎么算？", instrument_versions=["xx-v2"]))

    assert hits == []


def test_context_builder_restores_parent_for_child_hit() -> None:
    index = structured_index()
    retriever = HybridRetriever(index)
    hits = retriever.search(KnowledgeQuery(question="缺失条目不能按 0 自动填补", instrument_versions=["xx-v1"]))

    package = KnowledgeContextBuilder(index).build(KnowledgeQuery(question="缺失条目不能按 0 自动填补"), hits)

    assert package.status == "success"
    assert package.evidence
    assert package.evidence[0].source_chunk.chunk_kind == "child"
    assert package.evidence[0].context_chunk.chunk_kind == "parent"


def test_context_builder_can_reject_configured_unsupported_concepts() -> None:
    index = structured_index()
    retriever = HybridRetriever(index)
    hits = retriever.search(KnowledgeQuery(question="XX-v1 的 cutoff 阈值是多少？", instrument_versions=["xx-v1"]))
    gate = KnowledgeRelevanceGate(RelevanceGateConfig(unsupported_phrases=["cutoff", "阈值"]))

    package = KnowledgeContextBuilder(index, relevance_gate=gate).build(
        KnowledgeQuery(question="XX-v1 的 cutoff 阈值是多少？", instrument_versions=["xx-v1"]),
        hits,
    )

    assert package.status == "insufficient_evidence"
    assert package.evidence == []
    assert package.answerability is not None
    assert package.answerability.reason == "unsupported_query_concept"
