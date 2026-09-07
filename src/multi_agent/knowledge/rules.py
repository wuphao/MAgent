from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from multi_agent.knowledge.retrieval import RetrievalHit


class RuleCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    rule_type: str
    statement: str
    chunk_refs: list[str] = Field(default_factory=list)
    status: str = "candidate"
    limitations: list[str] = Field(default_factory=list)


class RuleCandidateBuilder:
    def from_hits(self, question: str, hits: list[RetrievalHit]) -> list[RuleCandidate]:
        candidates: list[RuleCandidate] = []
        for hit in hits:
            text = hit.chunk.text
            lowered = text.lower()
            if "total" in lowered or "总分" in text:
                candidates.append(RuleCandidate(
                    candidate_id=f"candidate_{hit.chunk.chunk_id}",
                    rule_type="instrument_scoring_definition",
                    statement=text,
                    chunk_refs=[hit.chunk.chunk_id],
                    limitations=["candidate must be activated through instrument registry before scoring rules change"],
                ))
        return candidates
