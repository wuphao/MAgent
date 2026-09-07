from __future__ import annotations

from multi_agent.agents.base import TaskContext
from multi_agent.capabilities.invoker import CapabilityInvoker
from multi_agent.domain.capabilities import AgentResult
from multi_agent.reporting.publisher import ReportPublisher
from multi_agent.reporting.renderers import render_json, render_markdown, render_text


class SynthesisAgent:
    name = "SynthesisAgent"

    def execute(self, context: TaskContext, capability_invoker: CapabilityInvoker) -> AgentResult:
        snapshot = ReportPublisher().build_snapshot(
            run_id=context.run_id or "run_unknown",
            project_id=context.project_id,
            goal=context.goal,
            task_results=context.task_results,
            snapshot_id=context.snapshot_id,
        )
        return AgentResult(
            agent_name=self.name,
            status="success" if snapshot.status != "failed" else "capability_unavailable",
            limitations=snapshot.limitations,
            output={
                "report_snapshot": snapshot.model_dump(mode="json"),
                "report_json": render_json(snapshot),
                "report_markdown": render_markdown(snapshot),
                "report_text": render_text(snapshot),
            },
        )
