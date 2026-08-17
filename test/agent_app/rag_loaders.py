from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown", ".pdf", ".docx", ".csv"}


@dataclass(frozen=True)
class SourceBlock:
    text: str
    page: int = 0
    section: str = ""


def load_document(path: Path) -> list[SourceBlock]:
    if not path.is_file():
        raise FileNotFoundError(f"Document not found: {path}")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"Unsupported document type {suffix or '<none>'}. "
            f"Supported: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
        )
    if suffix in {".txt"}:
        return [SourceBlock(_clean(path.read_text(encoding="utf-8-sig")))]
    if suffix in {".md", ".markdown"}:
        return _load_markdown(path)
    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix == ".docx":
        return _load_docx(path)
    return _load_csv(path)


def _load_markdown(path: Path) -> list[SourceBlock]:
    text = path.read_text(encoding="utf-8-sig")
    blocks: list[SourceBlock] = []
    headings: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        content = _clean("\n".join(buffer))
        if content:
            blocks.append(SourceBlock(content, section=" > ".join(headings)))
        buffer.clear()

    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            buffer.append(line)
            continue
        flush()
        level = len(match.group(1))
        title = match.group(2).strip()
        headings[level - 1 :] = [title]
    flush()
    return blocks


def _load_pdf(path: Path) -> list[SourceBlock]:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError("PDF support requires: pip install pypdf") from error
    blocks = []
    for page_number, page in enumerate(PdfReader(str(path)).pages, start=1):
        text = _clean(page.extract_text() or "")
        if text:
            blocks.append(SourceBlock(text, page=page_number))
    return blocks


def _load_docx(path: Path) -> list[SourceBlock]:
    try:
        from docx import Document
    except ImportError as error:
        raise RuntimeError("DOCX support requires: pip install python-docx") from error
    blocks: list[SourceBlock] = []
    section = ""
    buffer: list[str] = []

    def flush() -> None:
        text = _clean("\n".join(buffer))
        if text:
            blocks.append(SourceBlock(text, section=section))
        buffer.clear()

    for paragraph in Document(str(path)).paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        if paragraph.style and paragraph.style.name.lower().startswith("heading"):
            flush()
            section = text
        else:
            buffer.append(text)
    flush()
    return blocks


def _load_csv(path: Path) -> list[SourceBlock]:
    blocks = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames:
            for row_number, row in enumerate(reader, start=2):
                text = "\n".join(
                    f"{key}: {value}" for key, value in row.items() if value not in (None, "")
                )
                if text:
                    blocks.append(SourceBlock(text, section=f"row {row_number}"))
        else:
            file.seek(0)
            for row_number, row in enumerate(csv.reader(file), start=1):
                text = " | ".join(row).strip()
                if text:
                    blocks.append(SourceBlock(text, section=f"row {row_number}"))
    return blocks


def _clean(text: str) -> str:
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
