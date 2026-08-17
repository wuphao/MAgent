# DeepSeek Command Line Chat Demo with Local RAG

This is a minimal learning demo. It uses DeepSeek for chat and Chroma for a
local RAG prototype.

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

This project uses a tiny local hash embedding function so the RAG pipeline can
run without downloading an embedding model. It is useful for learning the flow,
but production quality retrieval should replace it with a real embedding model
such as bge-m3, nomic-embed-text, or an API embedding model.

## Memory Commands

Long-term memory is saved to `data/memories.json`.

```powershell
/remember 用户偏好中文回答，回答要简洁直接
/memories
/forget mem_xxxxx
```

During chat, related memories are retrieved and added to the model context.
