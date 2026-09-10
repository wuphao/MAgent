from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


class EmbeddingError(RuntimeError):
    pass


class EmbeddingClient(Protocol):
    def embed(self, inputs: list[str], *, truncate: bool = False) -> list[list[float]]:
        ...


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: str
    base_url: str
    model: str
    document_template_version: str
    query_template_version: str
    query_instruction: str
    truncate: bool = False
    batch_size: int = 8
    concurrency: int = 1

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "EmbeddingConfig":
        embedding = data.get("embedding", data)
        return cls(
            provider=str(embedding["provider"]),
            base_url=str(embedding["base_url"]).rstrip("/"),
            model=str(embedding["model"]),
            document_template_version=str(embedding["document_template_version"]),
            query_template_version=str(embedding["query_template_version"]),
            query_instruction=str(embedding["query_instruction"]),
            truncate=bool(embedding.get("truncate", False)),
            batch_size=int(embedding.get("batch_size", 8)),
            concurrency=int(embedding.get("concurrency", 1)),
        )


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: list[list[float]]
    model: str
    model_digest: str | None
    dimension: int
    input_template_version: str
    normalized: bool


class OllamaEmbeddingClient:
    def __init__(self, base_url: str, model: str, timeout_seconds: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def embed(self, inputs: list[str], *, truncate: bool = False) -> list[list[float]]:
        payload = json.dumps({"model": self.model, "input": inputs, "truncate": truncate}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise EmbeddingError(f"ollama embedding request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise EmbeddingError("ollama embedding response is not valid JSON") from exc

        embeddings = raw.get("embeddings")
        if not isinstance(embeddings, list):
            raise EmbeddingError("ollama embedding response does not include embeddings")
        return embeddings


class FakeEmbeddingClient:
    def __init__(self, vectors: list[list[float]] | Exception):
        self.vectors = vectors
        self.calls: list[dict[str, Any]] = []

    def embed(self, inputs: list[str], *, truncate: bool = False) -> list[list[float]]:
        self.calls.append({"inputs": inputs, "truncate": truncate})
        if isinstance(self.vectors, Exception):
            raise self.vectors
        return self.vectors[: len(inputs)]


class EmbeddingService:
    def __init__(self, config: EmbeddingConfig, client: EmbeddingClient, model_digest: str | None = None):
        self.config = config
        self.client = client
        self.model_digest = model_digest

    def embed_documents(self, texts: list[str]) -> EmbeddingBatch:
        prepared = [format_document_input(text) for text in texts]
        return self._embed(prepared, self.config.document_template_version)

    def embed_query(self, query: str) -> EmbeddingBatch:
        prepared = self.config.query_instruction.format(query=query)
        return self._embed([prepared], self.config.query_template_version)

    def _embed(self, inputs: list[str], template_version: str) -> EmbeddingBatch:
        if any(not item.strip() for item in inputs):
            raise EmbeddingError("empty text cannot be embedded")
        vectors = self.client.embed(inputs, truncate=self.config.truncate)
        normalized = normalize_vectors(validate_vectors(vectors, expected_count=len(inputs)))
        return EmbeddingBatch(
            vectors=normalized,
            model=self.config.model,
            model_digest=self.model_digest,
            dimension=len(normalized[0]) if normalized else 0,
            input_template_version=template_version,
            normalized=True,
        )


def format_document_input(text: str, *, title: str | None = None, section_path: list[str] | None = None) -> str:
    parts = []
    if title:
        parts.append(f"Title: {title}")
    if section_path:
        parts.append("Section: " + " > ".join(section_path))
    parts.append(text)
    return "\n".join(parts)


def validate_vectors(vectors: list[list[float]], *, expected_count: int) -> list[list[float]]:
    if len(vectors) != expected_count:
        raise EmbeddingError(f"embedding count mismatch: expected {expected_count}, got {len(vectors)}")
    if not vectors:
        raise EmbeddingError("embedding response is empty")
    dimension = len(vectors[0])
    if dimension == 0:
        raise EmbeddingError("embedding dimension is zero")
    for vector in vectors:
        if len(vector) != dimension:
            raise EmbeddingError("embedding dimensions are inconsistent")
        if any(not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in vector):
            raise EmbeddingError("embedding vector contains non-finite values")
        if math.sqrt(sum(float(value) * float(value) for value in vector)) == 0:
            raise EmbeddingError("embedding vector has zero norm")
    return [[float(value) for value in vector] for vector in vectors]


def normalize_vectors(vectors: list[list[float]]) -> list[list[float]]:
    normalized = []
    for vector in vectors:
        norm = math.sqrt(sum(value * value for value in vector))
        normalized.append([value / norm for value in vector])
    return normalized
