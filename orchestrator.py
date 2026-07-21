from __future__ import annotations

from typing import Any

from agents.cognitive_agent import CognitiveAgent
from agents.biomarker_agent import BiomarkerAgent
from agents.data_quality_agent import DataQualityAgent
from agents.functional_agent import FunctionalStagingAgent
from agents.imaging_agent import ImagingAgent
from agents.longitudinal_agent import LongitudinalAgent
from agents.synthesis_agent import ClinicalSynthesisAgent


class Orchestrator:
    """Run RWE agents in their evidence dependency order."""

    def __init__(self, use_llm: bool = False):
        self.agents = [
            DataQualityAgent(use_llm=use_llm),
            CognitiveAgent(use_llm=use_llm),
            FunctionalStagingAgent(use_llm=use_llm),
            LongitudinalAgent(use_llm=use_llm),
            BiomarkerAgent(use_llm=use_llm),
            ImagingAgent(use_llm=use_llm),
            ClinicalSynthesisAgent(use_llm=use_llm),
        ]

    def run(self, memory: dict[str, Any]) -> dict[str, Any]:
        for agent in self.agents:
            memory = agent.run(memory)
        memory["final_report"] = memory["agent_outputs"]["临床整合Agent"]
        return memory
