from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from multi_agent.knowledge import (  # noqa: E402
    KnowledgeDocumentLoader,
    KnowledgeIndex,
    KnowledgeIndexStore,
    build_index_manifest,
    stable_index_id,
)
from multi_agent.storage.sqlite import SQLiteStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the B-stage structured knowledge index.")
    parser.add_argument("--documents", type=Path, default=ROOT / "configs/knowledge/documents.json")
    parser.add_argument("--db", type=Path, default=ROOT / "evaluation/rag/knowledge_index.sqlite3")
    parser.add_argument("--out-json", type=Path, default=ROOT / "evaluation/rag/b_index_manifest.json")
    args = parser.parse_args()

    documents = KnowledgeDocumentLoader().load_manifest(args.documents, root=ROOT)
    manifest = build_index_manifest(documents, strategy_version="structured-markdown-parent-child/1")
    index_id = stable_index_id(manifest)
    index = KnowledgeIndex.from_documents(documents)
    stored = KnowledgeIndexStore(SQLiteStore(args.db)).publish(index, index_id, manifest)
    reloaded = KnowledgeIndexStore(SQLiteStore(args.db)).load(index_id)
    payload = {
        "schema_version": "rag_b_index_build/1",
        "index_id": stored.index_id,
        "db": str(args.db.resolve().relative_to(ROOT)),
        "manifest": manifest,
        "chunk_count": len(reloaded.chunks),
        "child_chunk_count": len(reloaded.child_chunks),
        "parent_chunk_count": len([chunk for chunk in reloaded.chunks if chunk.chunk_kind == "parent"]),
        "sample_chunks": [chunk.model_dump(mode="json") for chunk in reloaded.chunks[:5]],
    }
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ["index_id", "chunk_count", "child_chunk_count", "parent_chunk_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
