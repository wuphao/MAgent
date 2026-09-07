from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from multi_agent.domain.assets import SourceLocator, utc_now
from multi_agent.ingestion.manifest import InputManifest
from multi_agent.storage.assets import AssetRepository, AssetManifest


class TextSpan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    page: int = Field(ge=1)
    paragraph_index: int = Field(ge=0)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    text: str
    locator: SourceLocator


class TextDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    asset_id: str
    asset_revision: int
    media_type: str
    parser_version: str
    status: Literal["success", "capability_unavailable"]
    spans: list[TextSpan] = Field(default_factory=list)
    message: str | None = None


class TextParser:
    version = "stage07-text-parser/1"

    def __init__(self, assets: AssetRepository):
        self.assets = assets

    def parse(self, manifest: InputManifest) -> TextDocument:
        media_type = manifest.media_type or _media_type(manifest.path)
        asset = self.assets.register(AssetManifest(
            project_id=manifest.project_id,
            path=manifest.path,
            source_namespace=manifest.source_namespace,
            media_type=media_type,
        ))
        if media_type in {"text/plain", "text/markdown"}:
            return self._parse_text(manifest.path, manifest.project_id, asset.asset_id, asset.revision, media_type)
        if media_type == "application/pdf":
            return self._parse_pdf(manifest.path, manifest.project_id, asset.asset_id, asset.revision, media_type)
        raise ValueError(f"unsupported text media_type: {media_type}")

    def _parse_text(self, path: Path, project_id: str, asset_id: str, revision: int, media_type: str) -> TextDocument:
        text = path.read_text(encoding="utf-8-sig")
        spans = _paragraph_spans(text, project_id, asset_id, revision, self.version, page=1)
        return TextDocument(project_id=project_id, asset_id=asset_id, asset_revision=revision, media_type=media_type, parser_version=self.version, status="success", spans=spans)

    def _parse_pdf(self, path: Path, project_id: str, asset_id: str, revision: int, media_type: str) -> TextDocument:
        try:
            from pypdf import PdfReader
        except Exception:
            return TextDocument(project_id=project_id, asset_id=asset_id, asset_revision=revision, media_type=media_type, parser_version=self.version, status="capability_unavailable", message="pypdf is not available; OCR is not implemented in stage07")
        reader = PdfReader(str(path))
        spans: list[TextSpan] = []
        for page_number, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            spans.extend(_paragraph_spans(page_text, project_id, asset_id, revision, self.version, page_number))
        if not spans:
            return TextDocument(project_id=project_id, asset_id=asset_id, asset_revision=revision, media_type=media_type, parser_version=self.version, status="capability_unavailable", message="no machine-readable PDF text; OCR capability is required")
        return TextDocument(project_id=project_id, asset_id=asset_id, asset_revision=revision, media_type=media_type, parser_version=self.version, status="success", spans=spans)


def _paragraph_spans(text: str, project_id: str, asset_id: str, revision: int, parser_version: str, page: int) -> list[TextSpan]:
    spans: list[TextSpan] = []
    cursor = 0
    for paragraph_index, raw in enumerate(text.splitlines()):
        start = cursor
        end = cursor + len(raw)
        cursor = end + 1
        paragraph = raw.strip()
        if not paragraph:
            continue
        locator = SourceLocator(
            asset_id=asset_id,
            asset_revision=revision,
            record_locator=f"page:{page}:paragraph:{paragraph_index}",
            value_locator=f"page:{page}:chars:{start}-{end}",
            parser_version=parser_version,
            locator_type="page_span",
            extensions={"page": page, "paragraph_index": paragraph_index, "char_start": start, "char_end": end},
        )
        spans.append(TextSpan(page=page, paragraph_index=paragraph_index, char_start=start, char_end=end, text=paragraph, locator=locator))
    return spans


def _media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return "text/plain"
    if suffix == ".md":
        return "text/markdown"
    if suffix == ".pdf":
        return "application/pdf"
    raise ValueError(f"cannot infer text media_type from {path}")
