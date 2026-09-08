from __future__ import annotations

import hashlib
import json
import math
import re
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Protocol

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings

from agent_app.rag_loaders import load_document
from agent_app.settings import RagConfig

TOKEN_PATTERN = re.compile(r"[a-z0-9_./:-]+|[\u4e00-\u9fff]", re.I)


class RagStore(Protocol):
    def add_file(self, path: Path) -> int: ...
    def search(self, query: str) -> list[dict[str, object]]: ...
    def count(self) -> int: ...


class HashEmbedder:
    """Deterministic no-download baseline embedding."""

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = _tokens(text)
        features = tokens + [f"{tokens[i]}::{tokens[i + 1]}" for i in range(len(tokens) - 1)]
        for token in features:
            digest = hashlib.sha256(token.encode()).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dimensions] += 1 if digest[4] % 2 == 0 else -1
        norm = math.sqrt(sum(value * value for value in vector))
        return vector if norm == 0 else [value / norm for value in vector]

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


class SentenceTransformerEmbedder:
    """Production-quality multilingual semantic embedding adapter."""

    def __init__(self, model_name: str, dimensions: int) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError("Semantic embeddings require sentence-transformers") from error
        self._model = SentenceTransformer(model_name)
        actual = self._model.get_sentence_embedding_dimension()
        if actual != dimensions:
            raise ValueError(
                f"embedding_dimensions={dimensions}, but {model_name} outputs {actual} dimensions"
            )

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]:
        vectors = self._model.encode(
            list(texts), normalize_embeddings=True, show_progress_bar=False
        )
        return [vector.tolist() for vector in vectors]


def create_embedder(config: RagConfig) -> HashEmbedder | SentenceTransformerEmbedder:
    if config.embedding_provider == "hash":
        return HashEmbedder(config.embedding_dimensions)
    return SentenceTransformerEmbedder(config.embedding_model, config.embedding_dimensions)


class ChromaEmbeddingFunction(EmbeddingFunction[Documents]):
    def __init__(self, embedder: HashEmbedder) -> None:
        self._embedder = embedder

    def __call__(self, input: Documents) -> Embeddings:
        return self._embedder.embed_many(input)


def create_rag_store(config: RagConfig) -> RagStore:
    stores = {"chroma": ChromaRagStore, "qdrant": QdrantRagStore, "pgvector": PgvectorRagStore}
    if config.provider not in stores:
        raise ValueError("rag.provider must be one of: chroma, qdrant, pgvector")
    return stores[config.provider](config)


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> Iterable[str]:
    text = re.sub(r"\n{3,}", "\n\n", text.strip().lstrip("\ufeff"))
    if not text:
        return
    pieces = _recursive_split(text, chunk_size, ("\n\n", "\n", "。", "！", "？", ". ", " "))
    previous = ""
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        prefix = previous[-chunk_overlap:].strip() if previous else ""
        yield (f"{prefix}\n{piece}" if prefix else piece)[: chunk_size + chunk_overlap]
        previous = piece


def _recursive_split(text: str, limit: int, separators: tuple[str, ...]) -> list[str]:
    if len(text) <= limit:
        return [text]
    if not separators:
        return [text[i : i + limit] for i in range(0, len(text), limit)]
    separator, *rest = separators
    units = text.split(separator)
    if len(units) == 1:
        return _recursive_split(text, limit, tuple(rest))
    output, current = [], ""
    for unit in units:
        candidate = f"{current}{separator}{unit}" if current else unit
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                output.extend(_recursive_split(current, limit, tuple(rest)))
            current = unit
    if current:
        output.extend(_recursive_split(current, limit, tuple(rest)))
    return output


def prepare_chunks(path: Path, config: RagConfig) -> tuple[str, str, list[str], list[dict[str, object]]]:
    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    doc_id = hashlib.sha256(str(path.resolve()).lower().encode()).hexdigest()[:24]
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    documents, metadatas = [], []
    for block in load_document(path):
        for content in split_text(block.text, config.chunk_size, config.chunk_overlap):
            index = len(documents)
            documents.append(content)
            metadatas.append({
                "doc_id": doc_id, "content_hash": content_hash,
                "source": str(path.resolve()), "file_name": path.name,
                "page": int(block.page), "section": block.section,
                "chunk_index": index, "created_at": created_at,
            })
    if not documents:
        raise ValueError("Document contains no extractable text.")
    return doc_id, content_hash, documents, metadatas


class HybridRetrievalMixin:
    _config: RagConfig
    _reranker: object | None = None

    def _rank(self, query: str, vector: list[dict[str, object]], corpus: list[dict[str, object]]) -> list[dict[str, object]]:
        started = time.perf_counter()
        query_tokens = _tokens(query)
        keyword = _bm25(query_tokens, corpus, self._config.candidate_k)
        vector_map = {str(item["id"]): item for item in vector}
        keyword_map = {str(item["id"]): score for item, score in keyword}
        candidates = {str(item["id"]): item for item in vector}
        candidates.update({str(item["id"]): item for item, _ in keyword})
        max_keyword = max(keyword_map.values(), default=1.0) or 1.0
        ranked = []
        denominator = self._config.vector_weight + self._config.keyword_weight + 0.1
        for item_id, item in candidates.items():
            vector_score = max(0.0, 1.0 - float(vector_map[item_id]["distance"])) if item_id in vector_map else 0.0
            keyword_score = keyword_map.get(item_id, 0.0) / max_keyword
            overlap = _overlap(query_tokens, _tokens(str(item["content"])))
            score = (self._config.vector_weight * vector_score + self._config.keyword_weight * keyword_score + 0.1 * overlap) / denominator
            if score >= self._config.min_relevance:
                row = dict(item)
                row.update(score=round(score, 6), vector_score=round(vector_score, 6), keyword_score=round(keyword_score, 6))
                ranked.append(row)
        ranked.sort(key=lambda row: float(row["score"]), reverse=True)
        ranked = self._semantic_rerank(query, ranked[: self._config.candidate_k])
        selected = _deduplicate(ranked)[: self._config.top_k]
        self._log(query, selected, time.perf_counter() - started)
        return selected

    def _semantic_rerank(self, query: str, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        if self._config.reranker_provider == "none" or len(rows) < 2:
            return rows
        if self._reranker is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as error:
                raise RuntimeError("Cross-encoder reranking requires sentence-transformers") from error
            self._reranker = CrossEncoder(self._config.reranker_model, trust_remote_code=True)
        raw_scores = self._reranker.predict(
            [(query, str(row["content"])) for row in rows], show_progress_bar=False
        )
        low, high = float(min(raw_scores)), float(max(raw_scores))
        span = high - low
        for row, raw_score in zip(rows, raw_scores):
            normalized = (float(raw_score) - low) / span if span else 1.0
            row["rerank_score"] = round(normalized, 6)
            row["score"] = round(0.4 * float(row["score"]) + 0.6 * normalized, 6)
        return sorted(rows, key=lambda row: float(row["score"]), reverse=True)

    def _log(self, query: str, results: list[dict[str, object]], elapsed: float) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "query": query, "provider": self._config.provider,
            "elapsed_ms": round(elapsed * 1000, 2),
            "results": [{
                "source": row["metadata"].get("source"),
                "page": row["metadata"].get("page", 0),
                "section": row["metadata"].get("section", ""),
                "chunk_index": row["metadata"].get("chunk_index", 0),
                "score": row.get("score", 0),
            } for row in results],
        }
        self._config.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._config.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


class ChromaRagStore(HybridRetrievalMixin):
    def __init__(self, config: RagConfig) -> None:
        self._config = config
        self._embedder = create_embedder(config)
        config.persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(config.persist_dir))
        self._collection = self._client.get_or_create_collection(
            config.collection_name, embedding_function=ChromaEmbeddingFunction(self._embedder), metadata={"hnsw:space": "cosine"}
        )

    def add_file(self, path: Path) -> int:
        doc_id, content_hash, documents, metadatas = prepare_chunks(path, self._config)
        existing = self._collection.get(where={"doc_id": doc_id}, include=["metadatas"])
        old = existing.get("metadatas") or []
        if old and old[0].get("content_hash") == content_hash:
            return 0
        if existing.get("ids"):
            self._collection.delete(where={"doc_id": doc_id})
        self._collection.add(ids=[f"{doc_id}:{i}" for i in range(len(documents))], documents=documents, metadatas=metadatas)
        return len(documents)

    def search(self, query: str) -> list[dict[str, object]]:
        if not query.strip() or not self.count():
            return []
        result = self._collection.query(query_texts=[query], n_results=min(self._config.candidate_k, self.count()), include=["documents", "metadatas", "distances"])
        vector = [{"id": i, "content": c, "metadata": m or {}, "distance": d} for i, c, m, d in zip(result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0])]
        rows = self._collection.get(include=["documents", "metadatas"])
        corpus = [{"id": i, "content": c, "metadata": m or {}, "distance": 1.0} for i, c, m in zip(rows["ids"], rows["documents"], rows["metadatas"])]
        return self._rank(query, vector, corpus)

    def count(self) -> int:
        return self._collection.count()


class QdrantRagStore(HybridRetrievalMixin):
    def __init__(self, config: RagConfig) -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
        except ImportError as error:
            raise RuntimeError("Qdrant backend requires qdrant-client") from error
        self._config, self._embedder = config, create_embedder(config)
        self._client = QdrantClient(url=config.qdrant_url)
        if not self._client.collection_exists(config.collection_name):
            self._client.create_collection(config.collection_name, vectors_config=VectorParams(size=config.embedding_dimensions, distance=Distance.COSINE))

    def add_file(self, path: Path) -> int:
        from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct
        doc_id, content_hash, docs, metas = prepare_chunks(path, self._config)
        selector = Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))])
        old, _ = self._client.scroll(self._config.collection_name, scroll_filter=selector, limit=1, with_payload=True)
        if old and old[0].payload.get("content_hash") == content_hash:
            return 0
        self._client.delete(self._config.collection_name, points_selector=selector, wait=True)
        points = [PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{i}")), vector=self._embedder.embed(content), payload={**meta, "content": content}) for i, (content, meta) in enumerate(zip(docs, metas))]
        self._client.upsert(self._config.collection_name, points=points, wait=True)
        return len(points)

    def _all(self) -> list[dict[str, object]]:
        output, offset = [], None
        while True:
            points, offset = self._client.scroll(self._config.collection_name, limit=256, offset=offset, with_payload=True)
            output.extend({"id": str(p.id), "content": p.payload.get("content", ""), "metadata": p.payload, "distance": 1.0} for p in points)
            if offset is None:
                return output

    def search(self, query: str) -> list[dict[str, object]]:
        corpus = self._all()
        if not query.strip() or not corpus:
            return []
        hits = self._client.query_points(self._config.collection_name, query=self._embedder.embed(query), limit=min(self._config.candidate_k, len(corpus)), with_payload=True).points
        vector = [{"id": str(h.id), "content": h.payload.get("content", ""), "metadata": h.payload, "distance": 1 - float(h.score)} for h in hits]
        return self._rank(query, vector, corpus)

    def count(self) -> int:
        return int(self._client.count(self._config.collection_name, exact=True).count)


class PgvectorRagStore(HybridRetrievalMixin):
    def __init__(self, config: RagConfig) -> None:
        try:
            import psycopg
            from pgvector.psycopg import register_vector
        except ImportError as error:
            raise RuntimeError("pgvector backend requires psycopg and pgvector") from error
        self._config, self._embedder = config, create_embedder(config)
        self._connection = psycopg.connect(config.postgres_dsn)
        register_vector(self._connection)
        with self._connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cursor.execute(f"CREATE TABLE IF NOT EXISTS rag_chunks (id UUID PRIMARY KEY, doc_id TEXT NOT NULL, content_hash TEXT NOT NULL, content TEXT NOT NULL, metadata JSONB NOT NULL, embedding vector({config.embedding_dimensions}) NOT NULL)")
            cursor.execute("CREATE INDEX IF NOT EXISTS rag_chunks_doc_id_idx ON rag_chunks(doc_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS rag_chunks_embedding_idx ON rag_chunks USING ivfflat (embedding vector_cosine_ops)")
        self._connection.commit()

    def add_file(self, path: Path) -> int:
        doc_id, content_hash, docs, metas = prepare_chunks(path, self._config)
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT content_hash FROM rag_chunks WHERE doc_id=%s LIMIT 1", (doc_id,))
            old = cursor.fetchone()
            if old and old[0] == content_hash:
                return 0
            cursor.execute("DELETE FROM rag_chunks WHERE doc_id=%s", (doc_id,))
            for content, meta in zip(docs, metas):
                item_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{meta['chunk_index']}"))
                cursor.execute("INSERT INTO rag_chunks VALUES (%s,%s,%s,%s,%s,%s)", (item_id, doc_id, content_hash, content, json.dumps(meta, ensure_ascii=False), self._embedder.embed(content)))
        self._connection.commit()
        return len(docs)

    def _all(self) -> list[dict[str, object]]:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT id,content,metadata FROM rag_chunks")
            return [{"id": str(i), "content": c, "metadata": m, "distance": 1.0} for i, c, m in cursor.fetchall()]

    def search(self, query: str) -> list[dict[str, object]]:
        if not query.strip():
            return []
        value = self._embedder.embed(query)
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT id,content,metadata,embedding <=> %s AS distance FROM rag_chunks ORDER BY embedding <=> %s LIMIT %s", (value, value, self._config.candidate_k))
            vector = [{"id": str(i), "content": c, "metadata": m, "distance": float(d)} for i, c, m, d in cursor.fetchall()]
        return self._rank(query, vector, self._all())

    def count(self) -> int:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM rag_chunks")
            return int(cursor.fetchone()[0])


def _tokens(text: str) -> list[str]:
    tokens = TOKEN_PATTERN.findall(text.lower())
    chinese = "".join(char for char in text.lower() if "\u4e00" <= char <= "\u9fff")
    tokens.extend(chinese[i:i + 2] for i in range(max(0, len(chinese) - 1)))
    return tokens


def _bm25(query: list[str], corpus: list[dict[str, object]], limit: int) -> list[tuple[dict[str, object], float]]:
    if not query or not corpus:
        return []
    docs = [_tokens(str(item["content"])) for item in corpus]
    avg = sum(map(len, docs)) / len(docs) or 1
    df = Counter(token for token in set(query) for doc in docs if token in doc)
    scored = []
    for item, tokens in zip(corpus, docs):
        counts, score = Counter(tokens), 0.0
        for token in set(query):
            frequency = counts[token]
            if frequency:
                idf = math.log(1 + (len(docs) - df[token] + 0.5) / (df[token] + 0.5))
                score += idf * frequency * 2.5 / (frequency + 1.5 * (0.25 + 0.75 * len(tokens) / avg))
        if score:
            scored.append((item, score))
    return sorted(scored, key=lambda pair: pair[1], reverse=True)[:limit]


def _overlap(left: list[str], right: list[str]) -> float:
    return len(set(left) & set(right)) / len(set(left)) if left else 0.0


def _deduplicate(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output, seen = [], set()
    for row in rows:
        fingerprint = hashlib.sha1(re.sub(r"\s+", "", str(row["content"])).encode()).hexdigest()
        if fingerprint not in seen:
            seen.add(fingerprint)
            output.append(row)
    return output
