from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.toml"


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str
    base_url: str
    chat_model: str
    temperature: float


@dataclass(frozen=True)
class RagConfig:
    provider: str
    persist_dir: Path
    collection_name: str
    chunk_size: int
    chunk_overlap: int
    top_k: int
    enabled: bool
    embedding_dimensions: int
    qdrant_url: str
    postgres_dsn: str


@dataclass(frozen=True)
class MemoryConfig:
    enabled: bool
    path: Path
    top_k: int


@dataclass(frozen=True)
class AppConfig:
    deepseek: DeepSeekConfig
    rag: RagConfig
    memory: MemoryConfig


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    """Load DeepSeek settings from config.toml, with environment overrides."""
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("rb") as file:
        raw = tomllib.load(file)

    deepseek_section = raw.get("deepseek", {})
    rag_section = raw.get("rag", {})
    memory_section = raw.get("memory", {})
    config = AppConfig(
        deepseek=DeepSeekConfig(
            api_key=os.getenv("DEEPSEEK_API_KEY", deepseek_section.get("api_key", "")),
            base_url=os.getenv(
                "DEEPSEEK_BASE_URL",
                deepseek_section.get("base_url", "https://api.deepseek.com"),
            ),
            chat_model=os.getenv(
                "DEEPSEEK_CHAT_MODEL",
                deepseek_section.get("chat_model", "deepseek-chat"),
            ),
            temperature=float(deepseek_section.get("temperature", 0.1)),
        ),
        rag=RagConfig(
            provider=str(rag_section.get("provider", "chroma")),
            persist_dir=(
                path.parent / rag_section.get("persist_dir", "data/chroma")
            ).resolve(),
            collection_name=str(rag_section.get("collection_name", "local_docs")),
            chunk_size=int(rag_section.get("chunk_size", 800)),
            chunk_overlap=int(rag_section.get("chunk_overlap", 120)),
            top_k=int(rag_section.get("top_k", 4)),
            enabled=bool(rag_section.get("enabled", True)),
            embedding_dimensions=int(rag_section.get("embedding_dimensions", 384)),
            qdrant_url=str(rag_section.get("qdrant_url", "http://localhost:6333")),
            postgres_dsn=str(rag_section.get("postgres_dsn", "")),
        ),
        memory=MemoryConfig(
            enabled=bool(memory_section.get("enabled", True)),
            path=(
                path.parent / memory_section.get("path", "data/memories.json")
            ).resolve(),
            top_k=int(memory_section.get("top_k", 5)),
        ),
    )
    _validate_config(config)
    return config


def _validate_config(config: AppConfig) -> None:
    if config.rag.provider not in {"chroma", "qdrant", "pgvector"}:
        raise ValueError("rag.provider must be one of: chroma, qdrant, pgvector")
    if config.rag.chunk_overlap >= config.rag.chunk_size:
        raise ValueError("rag.chunk_overlap must be smaller than rag.chunk_size")
    if config.rag.top_k < 1:
        raise ValueError("rag.top_k must be greater than 0")
    if config.rag.embedding_dimensions < 1:
        raise ValueError("rag.embedding_dimensions must be greater than 0")
    if config.rag.provider == "pgvector" and not config.rag.postgres_dsn:
        raise ValueError("rag.postgres_dsn is required when provider is pgvector")
    if config.memory.top_k < 1:
        raise ValueError("memory.top_k must be greater than 0")
