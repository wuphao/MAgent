from __future__ import annotations

import json
from dataclasses import dataclass, field
from pydantic import TypeAdapter

from multi_agent.knowledge.documents import KnowledgeChunk, KnowledgeDocument
from multi_agent.storage.sqlite import SQLiteStore


CHUNK_ADAPTER = TypeAdapter(KnowledgeChunk)


@dataclass
class KnowledgeIndex:
    chunks: list[KnowledgeChunk] = field(default_factory=list)
    index_id: str | None = None
    manifest: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_documents(cls, documents: list[KnowledgeDocument]) -> "KnowledgeIndex":
        chunks = []
        for document in documents:
            chunks.extend(document.chunks)
        return cls(chunks=chunks)

    @property
    def child_chunks(self) -> list[KnowledgeChunk]:
        return [chunk for chunk in self.chunks if chunk.chunk_kind == "child"]

    def parent_for(self, chunk: KnowledgeChunk) -> KnowledgeChunk | None:
        if not chunk.parent_chunk_id:
            return None
        for candidate in self.chunks:
            if candidate.chunk_id == chunk.parent_chunk_id:
                return candidate
        return None


class KnowledgeIndexStore:
    def __init__(self, store: SQLiteStore):
        self.store = store
        self.store.migrate()
        self.migrate()

    def migrate(self) -> None:
        with self.store.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS knowledge_indexes (
                    index_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    manifest_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    index_id TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    document_version TEXT NOT NULL,
                    chunk_kind TEXT NOT NULL,
                    parent_chunk_id TEXT,
                    locator TEXT NOT NULL,
                    content_hash TEXT,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (index_id, chunk_id),
                    FOREIGN KEY (index_id) REFERENCES knowledge_indexes(index_id)
                );
                """
            )

    def publish(self, index: KnowledgeIndex, index_id: str, manifest: dict[str, object] | None = None) -> KnowledgeIndex:
        manifest = manifest or index.manifest
        with self.store.connect() as connection:
            connection.execute("BEGIN")
            connection.execute(
                """
                INSERT OR REPLACE INTO knowledge_indexes (index_id, manifest_json)
                VALUES (?, ?)
                """,
                (index_id, json.dumps(manifest, ensure_ascii=False, sort_keys=True)),
            )
            connection.execute("DELETE FROM knowledge_chunks WHERE index_id = ?", (index_id,))
            for chunk in index.chunks:
                connection.execute(
                    """
                    INSERT INTO knowledge_chunks (
                        index_id, chunk_id, document_id, document_version, chunk_kind,
                        parent_chunk_id, locator, content_hash, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        index_id,
                        chunk.chunk_id,
                        chunk.document_id,
                        chunk.document_version,
                        chunk.chunk_kind,
                        chunk.parent_chunk_id,
                        chunk.locator,
                        chunk.content_hash,
                        chunk.model_dump_json(),
                    ),
                )
        return KnowledgeIndex(chunks=index.chunks, index_id=index_id, manifest=manifest)

    def load(self, index_id: str) -> KnowledgeIndex:
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT manifest_json FROM knowledge_indexes WHERE index_id = ?",
                (index_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"knowledge index not found: {index_id}")
            chunk_rows = connection.execute(
                """
                SELECT payload_json FROM knowledge_chunks
                WHERE index_id = ?
                ORDER BY document_id, document_version, chunk_kind DESC, locator, chunk_id
                """,
                (index_id,),
            ).fetchall()
        chunks = [CHUNK_ADAPTER.validate_json(chunk_row["payload_json"]) for chunk_row in chunk_rows]
        return KnowledgeIndex(chunks=chunks, index_id=index_id, manifest=json.loads(row["manifest_json"]))


def build_index_manifest(documents: list[KnowledgeDocument], *, strategy_version: str) -> dict[str, object]:
    return {
        "schema_version": "knowledge_index_manifest/1",
        "strategy_version": strategy_version,
        "documents": [
            {
                "document_id": document.document_id,
                "version": document.version,
                "content_hash": document.content_hash,
                "chunk_count": len(document.chunks),
            }
            for document in documents
        ],
    }


def stable_index_id(manifest: dict[str, object]) -> str:
    import hashlib

    digest = hashlib.sha256(json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:20]
    return f"knowledge_index_{digest}"
