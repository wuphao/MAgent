from __future__ import annotations

import math

import pytest

from multi_agent.knowledge import EmbeddingConfig, EmbeddingError, EmbeddingService, FakeEmbeddingClient
from multi_agent.knowledge.embeddings import format_document_input, validate_vectors


def config() -> EmbeddingConfig:
    return EmbeddingConfig(
        provider="ollama",
        base_url="http://localhost:11434",
        model="qwen3-embedding:0.6b",
        document_template_version="rag-doc-embedding/1",
        query_template_version="rag-query-embedding/1",
        query_instruction="Instruct: Retrieve reference passages.\nQuery: {query}",
        truncate=False,
        batch_size=8,
        concurrency=1,
    )


def test_embedding_service_normalizes_documents_and_records_metadata() -> None:
    fake = FakeEmbeddingClient([[3, 4], [0, 5]])
    service = EmbeddingService(config(), fake, model_digest="sha256:test")

    batch = service.embed_documents(["alpha", "beta"])

    assert batch.model == "qwen3-embedding:0.6b"
    assert batch.model_digest == "sha256:test"
    assert batch.dimension == 2
    assert batch.input_template_version == "rag-doc-embedding/1"
    assert batch.normalized is True
    assert fake.calls[0]["inputs"] == ["alpha", "beta"]
    assert fake.calls[0]["truncate"] is False
    assert math.isclose(sum(value * value for value in batch.vectors[0]), 1.0)


def test_embedding_query_uses_instruction_template() -> None:
    fake = FakeEmbeddingClient([[1, 0, 0]])
    service = EmbeddingService(config(), fake)

    batch = service.embed_query("XX-v1 total 是怎么计算的？")

    assert batch.input_template_version == "rag-query-embedding/1"
    assert fake.calls[0]["inputs"] == ["Instruct: Retrieve reference passages.\nQuery: XX-v1 total 是怎么计算的？"]


def test_format_document_input_can_include_title_and_section() -> None:
    formatted = format_document_input("正文", title="手册", section_path=["评分", "缺失"])

    assert formatted == "Title: 手册\nSection: 评分 > 缺失\n正文"


def test_validate_vectors_rejects_count_mismatch() -> None:
    with pytest.raises(EmbeddingError, match="count mismatch"):
        validate_vectors([[1, 2]], expected_count=2)


def test_validate_vectors_rejects_inconsistent_dimensions() -> None:
    with pytest.raises(EmbeddingError, match="inconsistent"):
        validate_vectors([[1, 2], [1]], expected_count=2)


def test_validate_vectors_rejects_non_finite_values() -> None:
    with pytest.raises(EmbeddingError, match="non-finite"):
        validate_vectors([[1, float("nan")]], expected_count=1)


def test_validate_vectors_rejects_zero_norm() -> None:
    with pytest.raises(EmbeddingError, match="zero norm"):
        validate_vectors([[0, 0]], expected_count=1)


def test_embedding_service_rejects_empty_text() -> None:
    service = EmbeddingService(config(), FakeEmbeddingClient([[1, 0]]))

    with pytest.raises(EmbeddingError, match="empty text"):
        service.embed_documents([""])
