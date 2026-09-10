from __future__ import annotations

from multi_agent.agents.base import TaskContext
from multi_agent.agents.knowledge import KnowledgeAgent
from multi_agent.capabilities.invoker import CapabilityInvoker


def context_with(**parameters) -> TaskContext:
    return TaskContext(
        project_id="stage_d",
        goal="knowledge",
        observations=[],
        task_parameters=parameters,
    )


def test_knowledge_agent_returns_evidence_package_and_rule_candidate() -> None:
    result = KnowledgeAgent().execute(
        context_with(question="XX-v1 total 是怎么计算的？", instrument_versions=["xx-v1"]),
        CapabilityInvoker({}),
    )

    assert result.status == "success"
    assert result.output["query"]["instrument_versions"] == ["xx-v1"]
    assert result.output["hits"]
    assert result.output["evidence_package"]["status"] == "success"
    assert result.output["evidence_package"]["evidence"][0]["context_chunk"]["chunk_kind"] == "parent"
    assert result.output["rule_candidates"]
    candidate = result.output["rule_candidates"][0]
    assert candidate["status"] == "candidate"
    assert candidate["rule_type"] == "instrument_scoring_definition"
    assert candidate["applicable_versions"] == ["xx-v1"]
    assert candidate["evidence_refs"]
    assert "candidate must be activated" in candidate["limitations"][0]
    assert result.findings[0].status == "unresolved"


def test_knowledge_agent_requires_explicit_question() -> None:
    result = KnowledgeAgent().execute(context_with(), CapabilityInvoker({}))

    assert result.status == "no_data"
    assert result.output["status"] == "input_required"
    assert "knowledge question is required" in result.limitations


def test_knowledge_agent_does_not_silently_relax_wrong_version() -> None:
    result = KnowledgeAgent().execute(
        context_with(question="XX-v2 total 怎么算？"),
        CapabilityInvoker({}),
    )

    assert result.status == "no_data"
    assert result.output["hits"] == []
    assert result.output["query"]["instrument_versions"] == ["xx-v2"]
    assert result.output["rule_candidates"] == []


def test_rule_candidate_keeps_missing_rule_as_candidate_only() -> None:
    result = KnowledgeAgent().execute(
        context_with(question="缺失条目能不能按 0 自动填补？", instrument_versions=["xx-v1"]),
        CapabilityInvoker({}),
    )

    assert result.status == "success"
    assert result.output["rule_candidates"]
    candidate = result.output["rule_candidates"][0]
    assert candidate["status"] == "candidate"
    assert candidate["rule_type"] == "missing_item_handling"
    assert candidate["conditions"]
    assert candidate["exceptions"]
    assert all("activated" in limitation or "conservative" in limitation for limitation in candidate["limitations"])


def test_knowledge_agent_uses_relevance_gate_for_known_unsupported_query() -> None:
    result = KnowledgeAgent().execute(
        context_with(question="XX-v1 的 cutoff 阈值是多少？", instrument_versions=["xx-v1"]),
        CapabilityInvoker({}),
    )

    assert result.status == "no_data"
    assert result.output["hits"] == []
    assert result.output["evidence_package"]["status"] == "insufficient_evidence"
    assert result.output["rule_candidates"] == []


def test_knowledge_agent_accepts_string_instrument_version_without_splitting_characters() -> None:
    result = KnowledgeAgent().execute(
        context_with(question="XX-v1 total 是怎么计算的？", instrument_versions="xx-v1"),
        CapabilityInvoker({}),
    )

    assert result.status == "success"
    assert result.output["query"]["instrument_versions"] == ["xx-v1"]
