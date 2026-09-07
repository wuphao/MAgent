from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SCHEMA_VERSION = "1.0"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceAsset(ContractModel):
    schema_version: str = SCHEMA_VERSION
    project_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    revision: int = Field(default=1, ge=1)
    content_hash: str = Field(min_length=64, max_length=64)
    media_type: str = Field(min_length=1)
    source_namespace: str = Field(min_length=1)
    uri: str = Field(min_length=1)
    available_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("available_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("available_at must be timezone aware")
        return value


class SourceLocator(ContractModel):
    schema_version: str = SCHEMA_VERSION
    asset_id: str = Field(min_length=1)
    asset_revision: int = Field(ge=1)
    record_locator: str = Field(min_length=1)
    value_locator: str = Field(min_length=1)
    parser_version: str = Field(min_length=1)
    locator_type: Literal["json_path", "cell", "page_span", "record"] = "record"
    extensions: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_precise_source_position(self) -> "SourceLocator":
        if self.record_locator == "unknown" or self.value_locator == "unknown":
            raise ValueError("source locator cannot use unknown positions")
        return self


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
