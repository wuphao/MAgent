from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class InputManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(min_length=1)
    path: Path
    source_namespace: str = Field(min_length=1)
    media_type: str | None = None
