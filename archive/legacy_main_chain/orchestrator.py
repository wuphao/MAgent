from __future__ import annotations

from typing import Any

from archive.legacy_main_chain.agents.cognitive_agent import CognitiveAgent
from archive.legacy_main_chain.agents.biomarker_agent import BiomarkerAgent
from archive.legacy_main_chain.agents.data_quality_agent import DataQualityAgent
from archive.legacy_main_chain.agents.functional_agent import FunctionalStagingAgent
from archive.legacy_main_chain.agents.imaging_agent import ImagingAgent
from archive.legacy_main_chain.agents.longitudinal_agent import LongitudinalAgent
from archive.legacy_main_chain.agents.synthesis_agent import ClinicalSynthesisAgent


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
