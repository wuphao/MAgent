from __future__ import annotations

from multi_agent.knowledge.lexical import BM25LexicalIndex, tokenize
from multi_agent.knowledge.documents import KnowledgeChunk


def chunk(chunk_id: str, text: str, versions: list[str] | None = None) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id="doc",
        document_version="v1",
        title="Doc",
        text=text,
        locator=chunk_id,
        metadata={"instrument_versions": versions or ["xx-v1"]},
    )


def test_tokenize_keeps_english_terms_numbers_and_chinese_ngrams() -> None:
    tokens = tokenize("XX-v1 缺失条目不能按 0 自动填补")

    assert "xx-v1" in tokens
    assert "0" in tokens
    assert "缺失" in tokens
    assert "条目" in tokens


def test_bm25_returns_ranked_matches() -> None:
    index = BM25LexicalIndex([
        chunk("a", "XX-v1 total 表示四个条目的求和"),
        chunk("b", "缺失条目不能按 0 自动填补"),
    ])

    results = index.search("缺失条目怎么处理")

    assert results[0].chunk.chunk_id == "b"
    assert results[0].rank == 1
    assert results[0].score > 0
