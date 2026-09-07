from __future__ import annotations

from dataclasses import dataclass, field

from multi_agent.knowledge.documents import KnowledgeChunk, KnowledgeDocument


@dataclass
class KnowledgeIndex:
    chunks: list[KnowledgeChunk] = field(default_factory=list)

    @classmethod
    def from_documents(cls, documents: list[KnowledgeDocument]) -> "KnowledgeIndex":
        chunks = []
        for document in documents:
            chunks.extend(document.chunks)
        return cls(chunks=chunks)
