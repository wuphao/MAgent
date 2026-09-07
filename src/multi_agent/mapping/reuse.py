from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from multi_agent.domain.mapping import SourceProfile


@dataclass(frozen=True)
class MappingReuseKey:
    project_id: str
    source_namespace: str
    structure_fingerprint: str
    semantic_metadata_fingerprint: str
    instrument_definition_version: str


@dataclass(frozen=True)
class ReuseDecision:
    status: Literal["reuse_allowed", "requires_validation", "suspend_active_mapping"]
    reason: str


def reuse_key(
    project_id: str,
    source_namespace: str,
    profile: SourceProfile,
    instrument_definition_version: str,
) -> MappingReuseKey:
    return MappingReuseKey(
        project_id=project_id,
        source_namespace=source_namespace,
        structure_fingerprint=profile.structure_fingerprint,
        semantic_metadata_fingerprint=profile.semantic_metadata_fingerprint,
        instrument_definition_version=instrument_definition_version,
    )


def decide_reuse(previous: MappingReuseKey, current: MappingReuseKey) -> ReuseDecision:
    if previous == current:
        return ReuseDecision("reuse_allowed", "structure, semantic metadata, and definition version match")
    if previous.structure_fingerprint == current.structure_fingerprint and (
        previous.semantic_metadata_fingerprint != current.semantic_metadata_fingerprint
        or previous.instrument_definition_version != current.instrument_definition_version
    ):
        return ReuseDecision("suspend_active_mapping", "same structure but semantic metadata or definition changed")
    return ReuseDecision("requires_validation", "mapping reuse key changed")
