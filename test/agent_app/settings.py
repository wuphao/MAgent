from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.toml"
DEFAULT_DATA_DIR = "data"


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str
    chat_model: str
    embedding_model: str
    temperature: float


@dataclass(frozen=True)
class RagConfig:
    data_dir: Path
    chunk_size: int
    chunk_overlap: int
    top_k: int


@dataclass(frozen=True)
class McpConfig:
    enabled: bool
    server_name: str
    transport: str
    server_url: str
    command: str
    args: tuple[str, ...]


@dataclass(frozen=True)
class AppConfig:
    ollama: OllamaConfig
    rag: RagConfig
    mcp: McpConfig


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    """读取 TOML 配置，并允许用环境变量覆盖 Ollama 配置。"""
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在：{path}")

    with path.open("rb") as file:
        raw = tomllib.load(file)

    ollama_section = raw.get("ollama", {})
    rag_section = raw.get("rag", {})
    mcp_section = raw.get("mcp", {})

    data_dir = path.parent / rag_section.get("data_dir", DEFAULT_DATA_DIR)

    config = AppConfig(
        ollama=OllamaConfig(
            base_url=os.getenv(
                "OLLAMA_BASE_URL",
                ollama_section.get("base_url", "http://localhost:11434"),
            ),
            chat_model=os.getenv(
                "OLLAMA_CHAT_MODEL",
                ollama_section.get("chat_model", "qwen3:8b"),
            ),
            embedding_model=os.getenv(
                "OLLAMA_EMBEDDING_MODEL",
                ollama_section.get("embedding_model", "nomic-embed-text"),
            ),
            temperature=float(ollama_section.get("temperature", 0.1)),
        ),
        rag=RagConfig(
            data_dir=data_dir.resolve(),
            chunk_size=int(rag_section.get("chunk_size", 800)),
            chunk_overlap=int(rag_section.get("chunk_overlap", 120)),
            top_k=int(rag_section.get("top_k", 4)),
        ),
        mcp=McpConfig(
            enabled=bool(mcp_section.get("enabled", False)),
            server_name=str(mcp_section.get("server_name", "local-mcp")),
            transport=str(mcp_section.get("transport", "streamable_http")),
            server_url=str(mcp_section.get("server_url", "")),
            command=str(mcp_section.get("command", "")),
            args=tuple(str(item) for item in mcp_section.get("args", [])),
        ),
    )
    _validate_config(config)
    return config


def _validate_config(config: AppConfig) -> None:
    if config.rag.chunk_overlap >= config.rag.chunk_size:
        raise ValueError("rag.chunk_overlap 必须小于 rag.chunk_size")
    if config.rag.top_k < 1:
        raise ValueError("rag.top_k 必须大于 0")
    if config.mcp.transport not in {"stdio", "streamable_http"}:
        raise ValueError("mcp.transport 只支持 stdio 或 streamable_http")
    if config.mcp.enabled and config.mcp.transport == "stdio" and not config.mcp.command:
        raise ValueError("启用 stdio MCP 时必须配置 mcp.command")
    if config.mcp.enabled and config.mcp.transport == "streamable_http" and not config.mcp.server_url:
        raise ValueError("启用 streamable_http MCP 时必须配置 mcp.server_url")
