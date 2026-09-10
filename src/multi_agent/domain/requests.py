from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BudgetLimit(RequestModel):
    max_calls: int = Field(default=0, ge=0)
    max_tokens: int = Field(default=0, ge=0)
    max_cost: float | None = Field(default=None, ge=0)


class AnalysisRequest(RequestModel):
    project_id: str = Field(min_length=1)
    subject_scope: list[str] = Field(default_factory=list)
    goal: Literal["source_inventory", "xx_v1_assessment", "longitudinal_xx_v1", "multi_source_summary", "multimodal_summary", "rwe_patient_summary"]
    snapshot_id: str | None = None
    as_of: datetime
    allowed_capabilities: list[str] = Field(default_factory=list)
    budget: BudgetLimit = Field(default_factory=BudgetLimit)
    output_format: Literal["json", "markdown"] = "json"
    cancel_requested: bool = False

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must be timezone aware")
        return value

