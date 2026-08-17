from __future__ import annotations

import hashlib
import math
import re
import uuid
from pathlib import Path
from typing import Iterable, Protocol

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings

from agent_app.settings import RagConfig


TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fff]+")


class RagStore(Protocol):
    def add_file(self, path: Path) -> int: ...

    def search(self, query: str) -> list[dict[str, object]]: ...

    def count(self) -> int: ...


class HashEmbedder:
    """Small local embedder for learning RAG without model downloads."""

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in _tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


class ChromaEmbeddingFunction(EmbeddingFunction[Documents]):
    def __init__(self, embedder: HashEmbedder) -> None:
        self._embedder = embedder

    def __call__(self, input: Documents) -> Embeddings:
        return self._embedder.embed_many(input)


def create_rag_store(config: RagConfig) -> RagStore:
    if config.provider == "chroma":
        return ChromaRagStore(config)
    if config.provider == "qdrant":
        return QdrantRagStore(config)
    if config.provider == "pgvector":
        return PgvectorRagStore(config)
    raise ValueError("rag.provider must be one of: chroma, qdrant, pgvector")


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> Iterable[str]:
    normalized = re.sub(r"\n{3,}", "\n\n", text.strip().lstrip("\ufeff"))
    if not normalized:
        return

    start = 0
    text_length = len(normalized)
    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = normalized[start:end].strip()
        if chunk:
            yield chunk
        if end == text_length:
            break
        start = max(end - chunk_overlap, start + 1)


def _tokens(text: str) -> list[str]:
    normalized = text.lower()
    tokens = TOKEN_PATTERN.findall(normalized)
    for chinese_text in CHINESE_PATTERN.findall(normalized):
        tokens.extend(
            chinese_text[index : index + 2] for index in range(len(chinese_text) - 1)
        )
    return tokens


class ChromaRagStore:
    def __init__(self, config: RagConfig) -> None:
        self._config = config
        self._embedder = HashEmbedder(config.embedding_dimensions)
        config.persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(config.persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=config.collection_name,
            embedding_function=ChromaEmbeddingFunction(self._embedder),
            metadata={"hnsw:space": "cosine"},
        )

    def add_file(self, path: Path) -> int:
        text = path.read_text(encoding="utf-8")
        chunks = list(
            split_text(text, self._config.chunk_size, self._config.chunk_overlap)
        )
        if not chunks:
            raise ValueError("File is empty.")

        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(path.resolve())))
        ids = [f"{doc_id}:{index}" for index in range(len(chunks))]
        metadatas = [
            {"source": str(path.resolve()), "chunk": index}
            for index in range(len(chunks))
        ]
        self._collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)
        return len(chunks)

    def search(self, query: str) -> list[dict[str, object]]:
        result = self._collection.query(
            query_texts=[query],
            n_results=self._config.top_k,
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [
            {"content": document, "metadata": metadata or {}, "distance": distance}
            for document, metadata, distance in zip(documents, metadatas, distances)
        ]

    def count(self) -> int:
        return self._collection.count()


class QdrantRagStore:
    def __init__(self, config: RagConfig) -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
        except ImportError as error:
            raise RuntimeError(
                "Qdrant backend requires: pip install qdrant-client"
            ) from error

        self._config = config
        self._embedder = HashEmbedder(config.embedding_dimensions)
        self._client = QdrantClient(url=config.qdrant_url)
        if not self._client.collection_exists(config.collection_name):
            self._client.create_collection(
                collection_name=config.collection_name,
                vectors_config=VectorParams(
                    size=config.embedding_dimensions,
                    distance=Distance.COSINE,
                ),
            )

    def add_file(self, path: Path) -> int:
        try:
            from qdrant_client.models import PointStruct
        except ImportError as error:
            raise RuntimeError(
                "Qdrant backend requires: pip install qdrant-client"
            ) from error

        text = path.read_text(encoding="utf-8")
        chunks = list(
            split_text(text, self._config.chunk_size, self._config.chunk_overlap)
        )
        if not chunks:
            raise ValueError("File is empty.")

        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(path.resolve())))
        points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{index}")),
                vector=self._embedder.embed(chunk),
                payload={
                    "content": chunk,
                    "source": str(path.resolve()),
                    "chunk": index,
                },
            )
            for index, chunk in enumerate(chunks)
        ]
        self._client.upsert(collection_name=self._config.collection_name, points=points)
        return len(chunks)

    def search(self, query: str) -> list[dict[str, object]]:
        hits = self._client.search(
            collection_name=self._config.collection_name,
            query_vector=self._embedder.embed(query),
            limit=self._config.top_k,
        )
        return [
            {
                "content": hit.payload.get("content", ""),
                "metadata": {
                    "source": hit.payload.get("source", "unknown"),
                    "chunk": hit.payload.get("chunk"),
                },
                "distance": 1.0 - float(hit.score),
            }
            for hit in hits
        ]

    def count(self) -> int:
        return self._client.count(
            collection_name=self._config.collection_name,
            exact=True,
        ).count


class PgvectorRagStore:
    def __init__(self, config: RagConfig) -> None:
        try:
            import psycopg
            from pgvector.psycopg import register_vector
        except ImportError as error:
            raise RuntimeError(
                "pgvector backend requires: pip install psycopg[binary] pgvector"
            ) from error

        if not config.postgres_dsn:
            raise ValueError("rag.postgres_dsn is required for pgvector backend.")

        self._config = config
        self._embedder = HashEmbedder(config.embedding_dimensions)
        self._connection = psycopg.connect(config.postgres_dsn)
        register_vector(self._connection)
        self._ensure_schema()

    def add_file(self, path: Path) -> int:
        text = path.read_text(encoding="utf-8")
        chunks = list(
            split_text(text, self._config.chunk_size, self._config.chunk_overlap)
        )
        if not chunks:
            raise ValueError("File is empty.")

        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(path.resolve())))
        with self._connection.cursor() as cursor:
            cursor.execute("DELETE FROM rag_chunks WHERE doc_id = %s", (doc_id,))
            for index, chunk in enumerate(chunks):
                cursor.execute(
                    """
                    INSERT INTO rag_chunks
                        (id, doc_id, source, chunk_index, content, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{index}")),
                        doc_id,
                        str(path.resolve()),
                        index,
                        chunk,
                        self._embedder.embed(chunk),
                    ),
                )
        self._connection.commit()
        return len(chunks)

    def search(self, query: str) -> list[dict[str, object]]:
        query_vector = self._embedder.embed(query)
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT source, chunk_index, content, embedding <=> %s AS distance
                FROM rag_chunks
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (query_vector, query_vector, self._config.top_k),
            )
            rows = cursor.fetchall()
        return [
            {
                "content": content,
                "metadata": {"source": source, "chunk": chunk_index},
                "distance": float(distance),
            }
            for source, chunk_index, content, distance in rows
        ]

    def count(self) -> int:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM rag_chunks")
            return int(cursor.fetchone()[0])

    def _ensure_schema(self) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS rag_chunks (
                    id UUID PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding vector({self._config.embedding_dimensions}) NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS rag_chunks_embedding_idx
                ON rag_chunks USING ivfflat (embedding vector_cosine_ops)
                """
            )
        self._connection.commit()
