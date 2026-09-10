from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str
    version: str
    title: str
    path: str
    content_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    chunks: list["KnowledgeChunk"] = Field(default_factory=list)


class KnowledgeChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str
    document_id: str
    document_version: str
    title: str
    text: str
    locator: str
    keywords: list[str] = Field(default_factory=list)
    chunk_kind: str = "child"
    parent_chunk_id: str | None = None
    section_path: list[str] = Field(default_factory=list)
    page: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    content_hash: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeDocumentManifestItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str
    version: str
    path: str
    title: str
    source_type: str
    applies_to: list[str] = Field(default_factory=list)
    instrument_versions: list[str] = Field(default_factory=list)
    effective_from: str | None = None
    effective_to: str | None = None
    review_status: str = "unknown"
    notes: str | None = None


class KnowledgeDocumentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    documents: list[KnowledgeDocumentManifestItem]


class KnowledgeDocumentLoader:
    def load_markdown(self, path: Path, document_id: str, version: str, title: str | None = None) -> KnowledgeDocument:
        text = path.read_text(encoding="utf-8-sig")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        chunks = []
        for index, block in enumerate([part.strip() for part in text.split("\n\n") if part.strip()]):
            chunks.append(KnowledgeChunk(
                chunk_id=_stable_id("chunk", document_id, version, str(index), block),
                document_id=document_id,
                document_version=version,
                title=title or path.stem,
                text=block,
                locator=f"paragraph:{index}",
                keywords=_keywords(block),
            ))
        return KnowledgeDocument(document_id=document_id, version=version, title=title or path.stem, path=str(path), content_hash=digest, chunks=chunks)

    def load_manifest(self, manifest_path: Path, root: Path | None = None) -> list[KnowledgeDocument]:
        manifest = KnowledgeDocumentManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        base = root or manifest_path.parents[2]
        documents = []
        for item in manifest.documents:
            source_path = base / item.path
            if item.source_type == "markdown":
                documents.append(self.load_structured_markdown(source_path, item))
            elif item.source_type == "text":
                documents.append(self.load_text(source_path, item))
            else:
                raise ValueError(f"unsupported knowledge source_type: {item.source_type}")
        return documents

    def load_structured_markdown(self, path: Path, item: KnowledgeDocumentManifestItem) -> KnowledgeDocument:
        text = path.read_text(encoding="utf-8-sig")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        chunks: list[KnowledgeChunk] = []
        section_path: list[str] = []
        parent_lines: list[str] = []
        parent_section: list[str] = []
        parent_start = 0

        def flush_parent(char_end: int) -> None:
            nonlocal parent_lines, parent_section, parent_start
            block = "\n".join(line for line in parent_lines).strip()
            if not block:
                parent_lines = []
                return
            parent_id = _stable_id("parent", item.document_id, item.version, "|".join(parent_section), block)
            parent_hash = hashlib.sha256(block.encode("utf-8")).hexdigest()
            parent_locator = f"section:{'/'.join(parent_section) or item.title}"
            chunks.append(_chunk(
                chunk_id=parent_id,
                item=item,
                text=block,
                locator=parent_locator,
                chunk_kind="parent",
                parent_chunk_id=None,
                section_path=parent_section,
                char_start=parent_start,
                char_end=char_end,
                content_hash=parent_hash,
            ))
            for child_index, child_text in enumerate(_split_child_blocks(block)):
                chunks.append(_chunk(
                    chunk_id=_stable_id("chunk", item.document_id, item.version, parent_id, str(child_index), child_text),
                    item=item,
                    text=child_text,
                    locator=f"{parent_locator}:child:{child_index}",
                    chunk_kind="child",
                    parent_chunk_id=parent_id,
                    section_path=parent_section,
                    content_hash=hashlib.sha256(child_text.encode("utf-8")).hexdigest(),
                ))
            parent_lines = []

        offset = 0
        for raw_line in text.splitlines(keepends=True):
            stripped = raw_line.strip()
            if stripped.startswith("#"):
                flush_parent(offset)
                level = len(stripped) - len(stripped.lstrip("#"))
                heading = stripped[level:].strip()
                section_path = section_path[: max(level - 1, 0)] + [heading]
                parent_section = list(section_path)
                parent_start = offset
            elif stripped and not parent_lines:
                parent_section = list(section_path)
                parent_start = offset
            parent_lines.append(raw_line.rstrip("\r\n"))
            offset += len(raw_line)
        flush_parent(len(text))

        return KnowledgeDocument(
            document_id=item.document_id,
            version=item.version,
            title=item.title,
            path=str(path),
            content_hash=digest,
            metadata=item.model_dump(exclude={"document_id", "version", "path", "title"}),
            chunks=chunks,
        )

    def load_text(self, path: Path, item: KnowledgeDocumentManifestItem) -> KnowledgeDocument:
        text = path.read_text(encoding="utf-8-sig")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        parent_id = _stable_id("parent", item.document_id, item.version, text)
        chunks = [
            _chunk(parent_id, item, text, "document:0", "parent", None, [], 0, len(text), digest),
        ]
        for index, block in enumerate(_split_child_blocks(text)):
            chunks.append(_chunk(
                _stable_id("chunk", item.document_id, item.version, str(index), block),
                item,
                block,
                f"document:0:child:{index}",
                "child",
                parent_id,
                [],
                None,
                None,
                hashlib.sha256(block.encode("utf-8")).hexdigest(),
            ))
        return KnowledgeDocument(
            document_id=item.document_id,
            version=item.version,
            title=item.title,
            path=str(path),
            content_hash=digest,
            metadata=item.model_dump(exclude={"document_id", "version", "path", "title"}),
            chunks=chunks,
        )


def _keywords(text: str) -> list[str]:
    known = ["xx-v1", "xx_v1", "total", "item", "score", "计分", "总分", "条目", "缺失", "reported"]
    lowered = text.lower()
    return [word for word in known if word.lower() in lowered or word in text]


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _split_child_blocks(text: str) -> list[str]:
    blocks = [part.strip() for part in text.split("\n\n") if part.strip() and not _is_markdown_heading(part.strip())]
    if blocks:
        return blocks
    return [line.strip() for line in text.splitlines() if line.strip() and not _is_markdown_heading(line.strip())]


def _is_markdown_heading(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith("#") and bool(stripped.lstrip("#").strip())


def _chunk(
    chunk_id: str,
    item: KnowledgeDocumentManifestItem,
    text: str,
    locator: str,
    chunk_kind: str,
    parent_chunk_id: str | None,
    section_path: list[str],
    char_start: int | None = None,
    char_end: int | None = None,
    content_hash: str | None = None,
) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id=item.document_id,
        document_version=item.version,
        title=item.title,
        text=text,
        locator=locator,
        keywords=_keywords(text),
        chunk_kind=chunk_kind,
        parent_chunk_id=parent_chunk_id,
        section_path=section_path,
        char_start=char_start,
        char_end=char_end,
        content_hash=content_hash,
        metadata={
            "applies_to": item.applies_to,
            "instrument_versions": item.instrument_versions,
            "effective_from": item.effective_from,
            "effective_to": item.effective_to,
            "review_status": item.review_status,
        },
    )
