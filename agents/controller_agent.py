"""Backward-compatible alias for the new evidence synthesis agent."""

from agents.synthesis_agent import ClinicalSynthesisAgent


class ControllerAgent(ClinicalSynthesisAgent):
    name = "临床整合Agent"
