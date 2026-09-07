from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from multi_agent.domain.assets import SourceLocator
from multi_agent.domain.observations import TypedValue


class MappingModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ParsedRecord(MappingModel):
    data: dict[str, Any]
    record_locator: str
    value_locators: dict[str, str] = Field(default_factory=dict)
    parent: dict[str, Any] = Field(default_factory=dict)


class ParsedDocument(MappingModel):
    project_id: str = Field(min_length=1)
    source_namespace: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    asset_revision: int = Field(ge=1)
    media_type: str = Field(min_length=1)
    available_at: datetime
    root: Any
    records: list[ParsedRecord]
    parser_version: str
    layout: Literal["json", "csv", "xlsx"]


class SourceProfile(MappingModel):
    parser_version: str
    layout: str
    record_count: int
    fields: dict[str, dict[str, Any]]
    top_level_paths: list[str] = Field(default_factory=list)
    structure_fingerprint: str
    semantic_metadata_fingerprint: str
    facts_from_full_scan: list[str] = Field(default_factory=list)
    facts_from_sample: list[str] = Field(default_factory=list)


class CandidateObservation(MappingModel):
    project_id: str
    subject_ref: str
    source_subject_key: str
    concept_id: str
    value: TypedValue
    event_time: str | None
    event_time_precision: Literal["date", "month", "year", "unknown"]
    source: SourceLocator
    idempotency_key: str
    mapping_revision: str
    record_key: str


class QuarantinedRecord(MappingModel):
    code: str
    message: str
    record_locator: str
    field_path: str
    raw_value: Any = None


class CandidateBatch(MappingModel):
    project_id: str
    mapping_id: str
    mapping_revision: str
    total_records: int
    candidates: list[CandidateObservation]
    quarantined: list[QuarantinedRecord] = Field(default_factory=list)
    operator_counts: dict[str, dict[str, int]] = Field(default_factory=dict)
    unmapped_fields: list[str] = Field(default_factory=list)


class ValidationReport(MappingModel):
    status: Literal["valid", "partial", "invalid"]
    total_records: int
    published_count: int
    quarantined_count: int
    operator_counts: dict[str, dict[str, int]]
    unmapped_fields: list[str]
    quarantined: list[QuarantinedRecord]
    source_locators_checked: int
