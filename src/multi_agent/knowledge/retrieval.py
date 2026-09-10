from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field

from multi_agent.knowledge.documents import KnowledgeChunk
from multi_agent.knowledge.embeddings import EmbeddingError, EmbeddingService
from multi_agent.knowledge.index import KnowledgeIndex
from multi_agent.knowledge.lexical import BM25LexicalIndex


class KnowledgeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    question: str
    document_ids: list[str] = Field(default_factory=list)
    instrument_versions: list[str] = Field(default_factory=list)
    include_parent_chunks: bool = False


class RetrievalScores(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lexical_score: float | None = None
    vector_score: float | None = None
    rrf_score: float | None = None
    lexical_rank: int | None = None
    vector_rank: int | None = None
    mode: str


class RetrievalHit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk: KnowledgeChunk
    score: int = Field(ge=0)
    matched_terms: list[str] = Field(default_factory=list)
    scores: RetrievalScores | None = None


class ExactRetriever:
    def __init__(self, index: KnowledgeIndex):
        self.index = index

    def search(self, query: str, limit: int = 5) -> list[RetrievalHit]:
        terms = [term.lower() for term in query.replace("/", " ").replace("_", " ").split() if term.strip()]
        hits: list[RetrievalHit] = []
        for chunk in self.index.chunks:
            haystack = (chunk.text + " " + " ".join(chunk.keywords)).lower()
            matched = [term for term in terms if term in haystack]
            score = len(set(matched))
            if score:
                hits.append(RetrievalHit(chunk=chunk, score=score, matched_terms=sorted(set(matched))))
        hits.sort(key=lambda item: (-item.score, item.chunk.document_id, item.chunk.locator))
        return hits[:limit]


class HybridRetriever:
    def __init__(self, index: KnowledgeIndex, embedding_service: EmbeddingService | None = None, chunk_vectors: dict[str, list[float]] | None = None):
        self.index = index
        self.embedding_service = embedding_service
        self.chunk_vectors = chunk_vectors or {}

    def build_vectors(self) -> dict[str, list[float]]:
        if self.embedding_service is None:
            raise EmbeddingError("embedding service is required to build vectors")
        chunks = self.index.child_chunks
        batch = self.embedding_service.embed_documents([chunk.text for chunk in chunks])
        self.chunk_vectors = {chunk.chunk_id: vector for chunk, vector in zip(chunks, batch.vectors)}
        return self.chunk_vectors

    def search(self, query: KnowledgeQuery, limit: int = 10, candidate_limit: int = 30, rrf_k: int = 60) -> list[RetrievalHit]:
        chunks = self._filtered_chunks(query)
        lexical_results = BM25LexicalIndex(chunks).search(query.question, limit=candidate_limit)
        vector_results = self._vector_search(query, chunks, candidate_limit)
        by_chunk: dict[str, dict[str, object]] = {}

        for result in lexical_results:
            entry = by_chunk.setdefault(result.chunk.chunk_id, {"chunk": result.chunk, "matched_terms": []})
            entry["lexical_score"] = result.score
            entry["lexical_rank"] = result.rank
            entry["matched_terms"] = result.matched_terms

        for rank, chunk, score in vector_results:
            entry = by_chunk.setdefault(chunk.chunk_id, {"chunk": chunk, "matched_terms": []})
            entry["vector_score"] = score
            entry["vector_rank"] = rank

        hits: list[RetrievalHit] = []
        for entry in by_chunk.values():
            lexical_rank = entry.get("lexical_rank")
            vector_rank = entry.get("vector_rank")
            rrf_score = 0.0
            modes = []
            if isinstance(lexical_rank, int):
                rrf_score += 1 / (rrf_k + lexical_rank)
                modes.append("lexical")
            if isinstance(vector_rank, int):
                rrf_score += 1 / (rrf_k + vector_rank)
                modes.append("vector")
            scores = RetrievalScores(
                lexical_score=entry.get("lexical_score") if isinstance(entry.get("lexical_score"), float) else None,
                vector_score=entry.get("vector_score") if isinstance(entry.get("vector_score"), float) else None,
                rrf_score=rrf_score,
                lexical_rank=lexical_rank if isinstance(lexical_rank, int) else None,
                vector_rank=vector_rank if isinstance(vector_rank, int) else None,
                mode="+".join(modes),
            )
            hits.append(RetrievalHit(
                chunk=entry["chunk"],
                score=max(1, int(round(rrf_score * 10000))),
                matched_terms=list(entry.get("matched_terms", [])),
                scores=scores,
            ))
        hits.sort(key=lambda item: (-(item.scores.rrf_score if item.scores else 0.0), item.chunk.document_id, item.chunk.locator))
        return hits[:limit]

    def _filtered_chunks(self, query: KnowledgeQuery) -> list[KnowledgeChunk]:
        chunks = self.index.chunks if query.include_parent_chunks else self.index.child_chunks
        filtered = []
        for chunk in chunks:
            if query.document_ids and chunk.document_id not in query.document_ids:
                continue
            if query.instrument_versions:
                versions = set(chunk.metadata.get("instrument_versions", []))
                if not versions.intersection(query.instrument_versions):
                    continue
            filtered.append(chunk)
        return filtered

    def _vector_search(self, query: KnowledgeQuery, chunks: list[KnowledgeChunk], limit: int) -> list[tuple[int, KnowledgeChunk, float]]:
        if self.embedding_service is None or not self.chunk_vectors:
            return []
        query_vector = self.embedding_service.embed_query(query.question).vectors[0]
        scored = []
        for chunk in chunks:
            vector = self.chunk_vectors.get(chunk.chunk_id)
            if vector is None:
                continue
            scored.append((cosine_similarity(query_vector, vector), chunk))
        scored.sort(key=lambda item: (-item[0], item[1].document_id, item[1].locator))
        return [(rank, chunk, score) for rank, (score, chunk) in enumerate(scored[:limit], start=1)]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise EmbeddingError("vector dimensions do not match")
    return sum(a * b for a, b in zip(left, right)) / ((_norm(left) or 1.0) * (_norm(right) or 1.0))


def _norm(vector: list[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))
