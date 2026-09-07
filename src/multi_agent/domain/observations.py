from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from multi_agent.domain.assets import SCHEMA_VERSION, SourceLocator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ObservationRef(ContractModel):
    observation_id: str = Field(min_length=1)
    revision: int = Field(ge=1)


class SubjectLink(ContractModel):
    schema_version: str = SCHEMA_VERSION
    project_id: str = Field(min_length=1)
    source_namespace: str = Field(min_length=1)
    source_subject_key: str = Field(min_length=1)
    subject_ref: str = Field(min_length=1)
    basis: list[str] = Field(min_length=1)
    status: Literal["proposed", "validated", "rejected"] = "proposed"

    @field_validator("subject_ref")
    @classmethod
    def reject_shared_unknown_subject(cls, value: str) -> str:
        if value.strip().lower() == "unknown":
            raise ValueError("unknown subjects must not be merged into a shared subject")
        return value


class TypedValue(ContractModel):
    value_type: Literal["number", "string", "boolean", "date", "missing", "unknown"]
    value: int | float | str | bool | None = None
    unit: str | None = None
    comparator: Literal["<", "<=", "=", ">=", ">"] | None = None
    missing_reason: str | None = None

    @model_validator(mode="after")
    def validate_value_semantics(self) -> "TypedValue":
        if self.value_type in {"missing", "unknown"}:
            if self.value is not None:
                raise ValueError("missing and unknown values cannot carry a concrete value")
            if self.value_type == "missing" and not self.missing_reason:
                raise ValueError("missing values must carry a missing_reason")
            return self
        if self.value is None:
            raise ValueError("concrete values cannot be None")
        if self.value_type == "number" and not isinstance(self.value, (int, float)):
            raise ValueError("number values must be numeric")
        if self.value_type == "boolean" and not isinstance(self.value, bool):
            raise ValueError("boolean values must be boolean")
        if self.value_type in {"string", "date"} and not isinstance(self.value, str):
            raise ValueError("string and date values must be strings")
        return self


class Observation(ContractModel):
    schema_version: str = SCHEMA_VERSION
    project_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    revision: int = Field(default=1, ge=1)
    subject_ref: str = Field(min_length=1)
    concept_id: str = Field(min_length=1)
    value: TypedValue
    event_time: str | None = None
    event_time_precision: Literal["date", "datetime", "month", "year", "unknown"] = "unknown"
    available_at: datetime
    source: SourceLocator
    validation_status: Literal["valid", "quarantined", "needs_review"] = "valid"
    idempotency_key: str = Field(min_length=1)
    mapping_revision: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("available_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("available_at must be timezone aware")
        return value

    @field_validator("subject_ref")
    @classmethod
    def reject_shared_unknown_subject(cls, value: str) -> str:
        if value.strip().lower() == "unknown":
            raise ValueError("unknown subjects must not be merged into a shared subject")
        return value

    @model_validator(mode="after")
    def validate_time_precision(self) -> "Observation":
        if self.event_time is None and self.event_time_precision != "unknown":
            raise ValueError("event_time_precision must be unknown when event_time is absent")
        if self.event_time is not None and self.event_time_precision == "unknown":
            raise ValueError("event_time_precision must describe present event_time")
        return self
