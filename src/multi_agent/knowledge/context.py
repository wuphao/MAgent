from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from multi_agent.knowledge.documents import KnowledgeChunk
from multi_agent.knowledge.index import KnowledgeIndex
from multi_agent.knowledge.retrieval import KnowledgeQuery, RetrievalHit
from multi_agent.knowledge.answerability import AnswerabilityDecision, KnowledgeRelevanceGate


class KnowledgeEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    source_chunk: KnowledgeChunk
    context_chunk: KnowledgeChunk
    hit: RetrievalHit
    truncated: bool = False


class KnowledgeEvidencePackage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    question: str
    status: str
    index_id: str | None = None
    retrieval_mode: str
    evidence: list[KnowledgeEvidence] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    answerability: AnswerabilityDecision | None = None


class KnowledgeContextBuilder:
    def __init__(
        self,
        index: KnowledgeIndex,
        max_context_chars: int = 2400,
        max_evidence: int = 6,
        relevance_gate: KnowledgeRelevanceGate | None = None,
    ):
        self.index = index
        self.max_context_chars = max_context_chars
        self.max_evidence = max_evidence
        self.relevance_gate = relevance_gate or KnowledgeRelevanceGate()

    def build(self, query: KnowledgeQuery, hits: list[RetrievalHit]) -> KnowledgeEvidencePackage:
        decision = self.relevance_gate.decide(query, hits)
        if not decision.answerable:
            return KnowledgeEvidencePackage(
                question=query.question,
                status="no_match" if decision.reason == "no_match" else "insufficient_evidence",
                index_id=self.index.index_id,
                retrieval_mode="none" if not hits else "+".join(sorted({hit.scores.mode for hit in hits if hit.scores})),
                limitations=decision.limitations,
                answerability=decision,
            )

        evidence: list[KnowledgeEvidence] = []
        seen_context_ids: set[str] = set()
        used_chars = 0
        modes = sorted({hit.scores.mode for hit in hits if hit.scores})
        limitations: list[str] = []

        for hit in hits:
            parent = self.index.parent_for(hit.chunk)
            context_chunk = parent or hit.chunk
            if context_chunk.chunk_id in seen_context_ids:
                continue
            if len(evidence) >= self.max_evidence:
                limitations.append("evidence count was limited")
                break
            text_length = len(context_chunk.text)
            if used_chars + text_length > self.max_context_chars and evidence:
                limitations.append("context budget was reached")
                break
            seen_context_ids.add(context_chunk.chunk_id)
            used_chars += text_length
            evidence.append(
                KnowledgeEvidence(
                    evidence_id=f"knowledge_evidence_{context_chunk.chunk_id}",
                    source_chunk=hit.chunk,
                    context_chunk=context_chunk,
                    hit=hit,
                    truncated=False,
                )
            )

        if not evidence:
            limitations.append("context budget was too small for the first evidence chunk")
        return KnowledgeEvidencePackage(
            question=query.question,
            status="success" if evidence else "no_match",
            index_id=self.index.index_id,
            retrieval_mode="+".join(modes) if modes else "lexical",
            evidence=evidence,
            limitations=limitations,
            answerability=decision,
        )
