from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from multi_agent.knowledge.retrieval import RetrievalHit


class RuleCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    rule_type: str
    statement: str
    chunk_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    applicable_versions: list[str] = Field(default_factory=list)
    status: str = "candidate"
    limitations: list[str] = Field(default_factory=list)


class RuleCandidateBuilder:
    def from_hits(self, question: str, hits: list[RetrievalHit]) -> list[RuleCandidate]:
        candidates: list[RuleCandidate] = []
        query = question.lower()
        for hit in hits:
            text = hit.chunk.text
            lowered = text.lower()
            if ("total" in query or "总分" in question) and ("total" in lowered or "总分" in text):
                candidates.append(RuleCandidate(
                    candidate_id=f"candidate_{hit.chunk.chunk_id}",
                    rule_type="instrument_scoring_definition",
                    statement=text,
                    chunk_refs=[hit.chunk.chunk_id],
                    evidence_refs=[f"knowledge_evidence_{hit.chunk.parent_chunk_id or hit.chunk.chunk_id}"],
                    conditions=_conditions(text),
                    exceptions=_exceptions(text),
                    applicable_versions=list(hit.chunk.metadata.get("instrument_versions", [])),
                    limitations=[
                        "candidate must be activated through instrument registry before scoring rules change",
                        "candidate extraction is conservative and source-bound",
                    ],
                ))
            elif ("缺失" in question or "missing" in query) and "缺失" in text:
                candidates.append(RuleCandidate(
                    candidate_id=f"candidate_{hit.chunk.chunk_id}",
                    rule_type="missing_item_handling",
                    statement=text,
                    chunk_refs=[hit.chunk.chunk_id],
                    evidence_refs=[f"knowledge_evidence_{hit.chunk.parent_chunk_id or hit.chunk.chunk_id}"],
                    conditions=_conditions(text),
                    exceptions=_exceptions(text),
                    applicable_versions=list(hit.chunk.metadata.get("instrument_versions", [])),
                    limitations=[
                        "candidate must be activated through instrument registry before scoring rules change",
                        "candidate extraction is conservative and source-bound",
                    ],
                ))
        return candidates


def _conditions(text: str) -> list[str]:
    conditions = []
    if "若" in text or "如果" in text:
        conditions.append("conditional rule; verify source condition before activation")
    if "缺失" in text:
        conditions.append("applies when item data are missing")
    return conditions


def _exceptions(text: str) -> list[str]:
    exceptions = []
    if "不能" in text:
        exceptions.append("source contains a prohibition; do not infer an automatic replacement rule")
    return exceptions
