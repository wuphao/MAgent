from __future__ import annotations

from pathlib import Path

from multi_agent.agents.base import TaskContext
from multi_agent.capabilities.invoker import CapabilityInvoker
from multi_agent.domain.capabilities import AgentFinding, AgentResult
from multi_agent.knowledge import (
    HybridRetriever,
    KnowledgeContextBuilder,
    KnowledgeDocumentLoader,
    KnowledgeIndex,
    KnowledgeQuery,
    KnowledgeRelevanceGate,
    RelevanceGateConfig,
    RuleCandidateBuilder,
)


class KnowledgeAgent:
    name = "KnowledgeAgent"

    def execute(self, context: TaskContext, capability_invoker: CapabilityInvoker) -> AgentResult:
        config = {**context.task_results.get("knowledge_config", {}), **context.task_parameters}
        question = str(config.get("question", "")).strip()
        if not question:
            return AgentResult(
                agent_name=self.name,
                status="no_data",
                limitations=["knowledge question is required"],
                output={"status": "input_required"},
            )

        manifest_path = Path(str(config.get("documents_manifest", "configs/knowledge/documents.json")))
        if not manifest_path.exists():
            return AgentResult(
                agent_name=self.name,
                status="no_data",
                limitations=[f"knowledge document manifest not found: {manifest_path}"],
            )

        documents = KnowledgeDocumentLoader().load_manifest(manifest_path, root=Path.cwd())
        if not documents:
            return AgentResult(agent_name=self.name, status="no_data", limitations=["no versioned knowledge documents are available"])

        index = KnowledgeIndex.from_documents(documents)
        query = KnowledgeQuery(
            question=question,
            document_ids=_as_list(config.get("document_ids", [])),
            instrument_versions=_as_list(config.get("instrument_versions", _infer_instrument_versions(question))),
        )
        hits = HybridRetriever(index).search(query, limit=int(config.get("limit", 10)))
        relevance_config_path = Path(str(config.get("relevance_config", "configs/knowledge/relevance.json")))
        relevance_gate = KnowledgeRelevanceGate(
            RelevanceGateConfig.from_file(relevance_config_path)
            if relevance_config_path.exists()
            else RelevanceGateConfig()
        )
        evidence_package = KnowledgeContextBuilder(
            index,
            max_context_chars=int(config.get("max_context_chars", 2400)),
            max_evidence=int(config.get("max_evidence", 6)),
            relevance_gate=relevance_gate,
        ).build(query, hits)
        usable_hits = hits if evidence_package.status == "success" else []
        candidates = RuleCandidateBuilder().from_hits(question, usable_hits)
        findings = [
            AgentFinding(
                finding_id=f"finding_knowledge_{candidate.candidate_id}",
                proposition=f"Knowledge candidate {candidate.rule_type}: {candidate.statement}",
                status="unresolved",
                limitations=candidate.limitations,
            )
            for candidate in candidates
        ]
        return AgentResult(
            agent_name=self.name,
            status="success" if evidence_package.status == "success" else "no_data",
            findings=findings,
            output={
                "question": question,
                "query": query.model_dump(mode="json"),
                "hits": [hit.model_dump(mode="json") for hit in usable_hits],
                "evidence_package": evidence_package.model_dump(mode="json"),
                "rule_candidates": [candidate.model_dump(mode="json") for candidate in candidates],
            },
            limitations=evidence_package.limitations,
        )


def _infer_instrument_versions(question: str) -> list[str]:
    lowered = question.lower()
    if "xx-v2" in lowered:
        return ["xx-v2"]
    if "xx-v1" in lowered:
        return ["xx-v1"]
    return []


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]

