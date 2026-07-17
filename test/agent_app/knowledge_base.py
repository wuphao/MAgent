from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from agent_app.prompts import SEED_DOCUMENTS
from agent_app.settings import MANIFEST_PATH, now_iso


@dataclass
class UploadRecord:
    file_name: str
    stored_path: str
    source: str
    uploaded_at: str
    text_length: int


class LocalKnowledgeBase:
    def __init__(self, base_url: str, embedding_model: str) -> None:
        self.base_url = base_url
        self.embedding_model = embedding_model
        self._lock = threading.RLock()
        self._seed_documents = list(SEED_DOCUMENTS)
        self._user_documents: list[Document] = []
        self._manifest: list[dict[str, Any]] = []
        self._vectorstore: InMemoryVectorStore | None = None
        self._retriever = None
        self._index_error: str | None = None
        self._load_manifest()
        self._rebuild_index()

    def _load_manifest(self) -> None:
        if not MANIFEST_PATH.exists():
            return

        try:
            payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            return

        records = payload.get("records", [])
        for record in records:
            text = record.get("text", "")
            metadata = record.get("metadata", {})
            if not text:
                continue
            metadata = dict(metadata)
            metadata.setdefault("kind", "upload")
            self._user_documents.append(Document(page_content=text, metadata=metadata))
            self._manifest.append(record)

    def _persist_manifest(self) -> None:
        payload = {
            "updated_at": now_iso(),
            "records": self._manifest,
        }
        MANIFEST_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _all_documents(self) -> list[Document]:
        return [*self._seed_documents, *self._user_documents]

    def _rebuild_index(self) -> None:
        with self._lock:
            documents = self._all_documents()
            if not documents:
                self._vectorstore = None
                self._retriever = None
                self._index_error = "knowledge base is empty"
                return

            try:
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=800,
                    chunk_overlap=120,
                )
                split_docs = splitter.split_documents(documents)

                embeddings = OllamaEmbeddings(
                    model=self.embedding_model,
                    base_url=self.base_url,
                )
                self._vectorstore = InMemoryVectorStore.from_documents(
                    documents=split_docs,
                    embedding=embeddings,
                )
                self._retriever = self._vectorstore.as_retriever(search_kwargs={"k": 4})
                self._index_error = None
            except Exception as exc:
                self._vectorstore = None
                self._retriever = None
                self._index_error = str(exc)

    def add_file(self, file_name: str, text: str, stored_path: Path) -> UploadRecord:
        if not text.strip():
            raise ValueError("上传文件没有可用于检索的文本内容。")

        metadata = {
            "source": file_name,
            "kind": "upload",
            "stored_path": str(stored_path),
            "uploaded_at": now_iso(),
        }

        document = Document(page_content=text, metadata=metadata)
        record = {
            "file_name": file_name,
            "stored_path": str(stored_path),
            "source": file_name,
            "uploaded_at": metadata["uploaded_at"],
            "text": text,
            "metadata": metadata,
        }

        with self._lock:
            self._user_documents.append(document)
            self._manifest.append(record)
            self._persist_manifest()
            self._rebuild_index()

        return UploadRecord(
            file_name=file_name,
            stored_path=str(stored_path),
            source=file_name,
            uploaded_at=metadata["uploaded_at"],
            text_length=len(text),
        )

    def search(self, query: str, k: int = 4) -> list[Document]:
        with self._lock:
            retriever = self._retriever
        if retriever is None:
            return []

        try:
            docs = retriever.invoke(query)
        except Exception:
            return []
        return list(docs[:k]) if isinstance(docs, list) else list(docs)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "seed_documents": len(self._seed_documents),
                "uploaded_documents": len(self._user_documents),
                "total_documents": len(self._seed_documents) + len(self._user_documents),
                "indexed": self._retriever is not None,
                "manifest_records": len(self._manifest),
                "index_error": self._index_error,
            }

    def list_sources(self) -> list[dict[str, Any]]:
        with self._lock:
            records = [
                {
                    "source": doc.metadata.get("source", "unknown"),
                    "kind": doc.metadata.get("kind", "unknown"),
                    "uploaded_at": doc.metadata.get("uploaded_at", ""),
                }
                for doc in self._all_documents()
            ]
        return records

