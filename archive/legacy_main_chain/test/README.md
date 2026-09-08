# DeepSeek Command Line Chat Demo with Local RAG

This is a learning-oriented RAG application. It uses DeepSeek for chat and
supports Chroma, Qdrant, and pgvector stores.

## Setup

```powershell
pip install -r requirements.txt
```

Fill in your DeepSeek API key in `config.toml`:

```toml
[deepseek]
api_key = "your-api-key"
base_url = "https://api.deepseek.com"
chat_model = "deepseek-chat"
temperature = 0.1
```

You can also leave `api_key` empty and set `DEEPSEEK_API_KEY` in your environment.

## Run

```powershell
python main.py
```

Type your message and press Enter. Press Ctrl+C, or Ctrl+Z then Enter, to exit.

## RAG Commands

```powershell
/add .\notes.txt
/search your question
/status
```

`/add` supports UTF-8 TXT, Markdown, PDF, DOCX, and CSV. Markdown headings,
PDF page numbers, DOCX headings, and CSV row numbers are retained as metadata.
Unchanged files are skipped; changed files replace their old chunks without
leaving stale trailing chunks.

The Chroma database is persisted under `data/chroma` by default.

The RAG backend is selected in `config.toml`:

```toml
[rag]
enabled = true
provider = "chroma" # chroma, qdrant, or pgvector
```

- `chroma`: local prototype, no separate database service required.
- `qdrant`: lightweight production service. Run Qdrant yourself and set `qdrant_url`.
- `pgvector`: use an existing PostgreSQL database with the pgvector extension and set `postgres_dsn`.

Qdrant and pgvector dependencies are optional. Uncomment them in
`requirements.txt` only when you switch to that backend.

Retrieval combines vector candidates with BM25 keyword candidates, applies a
`bge-reranker-v2-m3` cross-encoder rerank, removes duplicates, enforces a relevance floor,
and records query diagnostics in `data/rag_queries.jsonl`. Follow-up questions
are rewritten using recent chat history. Context is length-bounded and answers
are instructed to cite `[资料 N]` sources.

The default semantic embedding model is `BAAI/bge-m3`. A tiny local hash
embedding remains available by setting `embedding_provider = "hash"`; it is
only intended for offline pipeline demonstrations, not retrieval quality.

## Memory Commands

Long-term memory is saved to `data/memories.json`.

```powershell
/remember 用户偏好中文回答，回答要简洁直接
/memories
/forget mem_xxxxx
```

During chat, related memories are retrieved and added to the model context.

## Retrieval evaluation

`agent_app.rag_evaluator.evaluate_retrieval` reads JSONL cases containing
`question`, `expected_sources`, and `expected_keywords`, and reports Recall@K,
MRR, and keyword recall. This makes retrieval changes measurable rather than
subjective.
