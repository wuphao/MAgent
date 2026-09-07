from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from multi_agent.knowledge.documents import KnowledgeChunk
from multi_agent.knowledge.index import KnowledgeIndex


class RetrievalHit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk: KnowledgeChunk
    score: int = Field(ge=0)
    matched_terms: list[str] = Field(default_factory=list)


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
