from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str
    version: str
    title: str
    path: str
    content_hash: str
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


def _keywords(text: str) -> list[str]:
    known = ["xx-v1", "xx_v1", "total", "item", "score", "计分", "总分", "条目", "缺失", "reported"]
    lowered = text.lower()
    return [word for word in known if word.lower() in lowered or word in text]


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"
