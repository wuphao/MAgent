from __future__ import annotations

from pathlib import Path

from multi_agent.agents.base import TaskContext
from multi_agent.capabilities.invoker import CapabilityInvoker
from multi_agent.domain.capabilities import AgentFinding, AgentResult
from multi_agent.knowledge import ExactRetriever, KnowledgeDocumentLoader, KnowledgeIndex, RuleCandidateBuilder


class KnowledgeAgent:
    name = "KnowledgeAgent"

    def execute(self, context: TaskContext, capability_invoker: CapabilityInvoker) -> AgentResult:
        config = {**context.task_results.get("knowledge_config", {}), **context.task_parameters}
        docs_dir = Path(str(config.get("docs_dir", "configs/knowledge")))
        question = str(config.get("question", "xx-v1 total scoring definition"))
        documents = []
        if docs_dir.exists():
            loader = KnowledgeDocumentLoader()
            for path in sorted(docs_dir.glob("*.md")):
                documents.append(loader.load_markdown(path, path.stem, "1"))
        if not documents:
            return AgentResult(agent_name=self.name, status="no_data", limitations=["no versioned knowledge documents are available"])
        hits = ExactRetriever(KnowledgeIndex.from_documents(documents)).search(question)
        candidates = RuleCandidateBuilder().from_hits(question, hits)
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
            status="success" if hits else "no_data",
            findings=findings,
            output={
                "question": question,
                "hits": [hit.model_dump(mode="json") for hit in hits],
                "rule_candidates": [candidate.model_dump(mode="json") for candidate in candidates],
            },
            limitations=[] if hits else ["exact retrieval found no sourced knowledge chunk"],
        )

