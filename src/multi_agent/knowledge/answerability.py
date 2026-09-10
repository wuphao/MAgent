from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from multi_agent.knowledge.retrieval import KnowledgeQuery, RetrievalHit


class AnswerabilityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    answerable: bool
    reason: str
    rejected_phrases: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class RelevanceGateConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "knowledge_relevance_config/1"
    unsupported_phrases: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @classmethod
    def from_file(cls, path: Path) -> "RelevanceGateConfig":
        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))


class KnowledgeRelevanceGate:
    def __init__(self, config: RelevanceGateConfig | None = None):
        self.config = config or RelevanceGateConfig()

    def decide(self, query: KnowledgeQuery, hits: list[RetrievalHit]) -> AnswerabilityDecision:
        if not hits:
            return AnswerabilityDecision(
                answerable=False,
                reason="no_match",
                limitations=["knowledge retrieval returned no matching chunks"],
            )

        rejected = [
            phrase
            for phrase in self.config.unsupported_phrases
            if phrase.casefold() in query.question.casefold()
        ]
        if rejected:
            return AnswerabilityDecision(
                answerable=False,
                reason="unsupported_query_concept",
                rejected_phrases=rejected,
                limitations=self.config.limitations
                or ["query contains a configured unsupported concept for the current knowledge base"],
            )

        return AnswerabilityDecision(answerable=True, reason="retrieved_evidence")
