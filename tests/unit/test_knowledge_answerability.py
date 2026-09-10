from __future__ import annotations

from multi_agent.knowledge import KnowledgeQuery, KnowledgeRelevanceGate, RelevanceGateConfig


def test_relevance_gate_rejects_configured_unsupported_phrase() -> None:
    gate = KnowledgeRelevanceGate(RelevanceGateConfig(unsupported_phrases=["阈值"]))
    decision = gate.decide(KnowledgeQuery(question="XX-v1 的 cutoff 阈值是多少？"), hits=[object()])

    assert decision.answerable is False
    assert decision.reason == "unsupported_query_concept"
    assert decision.rejected_phrases == ["阈值"]


def test_relevance_gate_accepts_hits_without_unsupported_phrase() -> None:
    gate = KnowledgeRelevanceGate(RelevanceGateConfig(unsupported_phrases=["阈值"]))
    decision = gate.decide(KnowledgeQuery(question="XX-v1 total 是怎么计算的？"), hits=[object()])

    assert decision.answerable is True
    assert decision.reason == "retrieved_evidence"
