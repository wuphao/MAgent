from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from multi_agent.knowledge import EmbeddingConfig, EmbeddingError, EmbeddingService, OllamaEmbeddingClient  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe the configured Ollama embedding model.")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/knowledge/rag.json")
    parser.add_argument("--out-json", type=Path, default=ROOT / "evaluation/rag/ollama_embedding_probe.json")
    args = parser.parse_args()

    config = EmbeddingConfig.from_mapping(json.loads(args.config.read_text(encoding="utf-8")))
    client = OllamaEmbeddingClient(config.base_url, config.model, timeout_seconds=30.0)
    service = EmbeddingService(config, client)
    payload = {
        "schema_version": "rag_a1_ollama_embedding_probe/1",
        "model": config.model,
        "base_url": config.base_url,
        "status": "unknown",
        "checks": [],
    }

    try:
        documents = service.embed_documents(["XX-v1 total 表示四个条目的求和。", "缺失条目不能按 0 自动填补。"])
        query = service.embed_query("XX-v1 total 是怎么计算的？")
        payload.update(
            {
                "status": "success",
                "checks": [
                    {"name": "document_batch", "count": len(documents.vectors), "dimension": documents.dimension},
                    {"name": "query_single", "count": len(query.vectors), "dimension": query.dimension},
                ],
            }
        )
    except EmbeddingError as exc:
        payload.update({"status": "unavailable", "error": str(exc)})

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
