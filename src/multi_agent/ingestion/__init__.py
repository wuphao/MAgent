"""Deterministic source ingestion and profiling."""

from multi_agent.ingestion.manifest import InputManifest
from multi_agent.ingestion.parsers import Parser
from multi_agent.ingestion.profiler import Profiler

__all__ = ["InputManifest", "Parser", "Profiler"]
