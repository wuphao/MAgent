from __future__ import annotations

import json
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.runnables import Runnable
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from agent_app.prompts import SEED_DOCUMENTS
from agent_app.settings import OllamaConfig, RagConfig


class LocalKnowledgeBase:
    """持久化原始文档，并提供基于内存向量索引的语义检索。"""

    def __init__(self, ollama: OllamaConfig, config: RagConfig) -> None:
        self._ollama = ollama
        self._config = config
        self._manifest_path = config.data_dir / "documents.json"
        saved_documents = self._load_documents()
        self._documents = [*SEED_DOCUMENTS, *saved_documents]
        self._retriever = self._build_retriever()

    def _load_documents(self) -> list[Document]:
        if not self._manifest_path.exists():
            return []
        records = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        return [Document(page_content=item["text"], metadata=item["metadata"]) for item in records]

    def _save_documents(self) -> None:
        self._config.data_dir.mkdir(parents=True, exist_ok=True)
        user_documents = [
            document
            for document in self._documents
            if document.metadata.get("kind") == "file"
        ]
        records = [
            {"text": document.page_content, "metadata": document.metadata}
            for document in user_documents
        ]
        self._manifest_path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _build_retriever(self) -> Runnable:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self._config.chunk_size,
            chunk_overlap=self._config.chunk_overlap,
        )
        chunks = splitter.split_documents(self._documents)
        embeddings = OllamaEmbeddings(
            model=self._ollama.embedding_model,
            base_url=self._ollama.base_url,
        )
        store = InMemoryVectorStore.from_documents(chunks, embeddings)
        return store.as_retriever(search_kwargs={"k": self._config.top_k})

    def add_file(self, path: Path) -> None:
        """添加一个 UTF-8 文本文件，并重建内存索引。"""
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError("文件内容为空")
        self._documents.append(
            Document(page_content=text, metadata={"source": str(path), "kind": "file"})
        )
        self._save_documents()
        self._retriever = self._build_retriever()

    def search(self, query: str) -> list[Document]:
        """返回与查询最相关的文档片段。"""
        return list(self._retriever.invoke(query))

    def stats(self) -> dict[str, int]:
        return {
            "documents": len(self._documents),
            "user_documents": sum(
                doc.metadata.get("kind") == "file" for doc in self._documents
            ),
        }
