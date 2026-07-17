from agents.biomarker_agent import BiomarkerAgent
from agents.biomarker_agent import BiomarkerAgent
from agents.cognitive_agent import CognitiveAgent
from agents.controller_agent import ControllerAgent
from agents.followup_agent import FollowUpAgent
from agents.imaging_agent import ImagingAgent
from agents.knowledge_agent import KnowledgeAgent


class Orchestrator:
    def __init__(self):
        self.agents = [
            ImagingAgent(),
            BiomarkerAgent(),
            CognitiveAgent(),
            FollowUpAgent(),
            KnowledgeAgent(),
        ]
        self.controller = ControllerAgent()

    def run(self, memory):
        for agent in self.agents:
            memory = agent.run(memory)

        memory = self.controller.run(memory)
        return memory
