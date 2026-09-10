from __future__ import annotations

from pathlib import Path

from multi_agent.knowledge import (
    KnowledgeDocumentLoader,
    KnowledgeIndex,
    KnowledgeIndexStore,
    build_index_manifest,
    stable_index_id,
)
from multi_agent.storage.sqlite import SQLiteStore


def test_manifest_loader_creates_parent_child_chunks_with_metadata() -> None:
    root = Path(__file__).resolve().parents[2]
    documents = KnowledgeDocumentLoader().load_manifest(root / "configs/knowledge/documents.json", root=root)
    document = documents[0]

    assert document.document_id == "xx_v1_dictionary"
    assert document.version == "2026-09-07"
    assert document.metadata["source_type"] == "markdown"
    assert document.metadata["instrument_versions"] == ["xx-v1"]

    parents = [chunk for chunk in document.chunks if chunk.chunk_kind == "parent"]
    children = [chunk for chunk in document.chunks if chunk.chunk_kind == "child"]
    assert parents
    assert children
    assert all(chunk.parent_chunk_id for chunk in children)
    assert all(chunk.content_hash for chunk in document.chunks)
    assert children[0].metadata["review_status"] == "draft"


def test_knowledge_index_store_round_trips_structured_chunks(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    documents = KnowledgeDocumentLoader().load_manifest(root / "configs/knowledge/documents.json", root=root)
    manifest = build_index_manifest(documents, strategy_version="structured-markdown-parent-child/1")
    index_id = stable_index_id(manifest)
    index = KnowledgeIndex.from_documents(documents)

    store = KnowledgeIndexStore(SQLiteStore(tmp_path / "knowledge.sqlite3"))
    stored = store.publish(index, index_id, manifest)
    reloaded = store.load(index_id)

    assert stored.index_id == index_id
    assert reloaded.index_id == index_id
    assert reloaded.manifest == manifest
    assert len(reloaded.chunks) == len(index.chunks)
    assert len(reloaded.child_chunks) > 0
    first_child = reloaded.child_chunks[0]
    assert reloaded.parent_for(first_child) is not None
