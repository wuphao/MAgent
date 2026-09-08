"""Backward-compatible alias for the new evidence synthesis agent."""

from archive.legacy_main_chain.agents.synthesis_agent import ClinicalSynthesisAgent


class ControllerAgent(ClinicalSynthesisAgent):
    name = "临床整合Agent"
