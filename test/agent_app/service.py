from __future__ import annotations

from typing import Any, Iterator

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from agent_app.knowledge_base import LocalKnowledgeBase, UploadRecord
from agent_app.mcp_registry import MCPRegistry
from agent_app.settings import (
    CHAT_MODEL_NAME,
    EMBEDDING_MODEL_NAME,
    OLLAMA_BASE_URL,
    ensure_data_dirs,
)
from agent_app.prompts import SYSTEM_PROMPT
from agent_app.text_utils import extract_stream_text, extract_text_from_model_output, safe_filename
from agent_app.tools import create_tools


class AgentService:
    def __init__(self) -> None:
        ensure_data_dirs()
        self.kb = LocalKnowledgeBase(
            base_url=OLLAMA_BASE_URL,
            embedding_model=EMBEDDING_MODEL_NAME,
        )
        self.mcp_registry = MCPRegistry()
        self.tools = create_tools(self.kb, self.mcp_registry)
        self.memory = MemorySaver()
        self.store = InMemoryStore()
        self.model = ChatOllama(
            model=CHAT_MODEL_NAME,
            base_url=OLLAMA_BASE_URL,
            temperature=0,
        )
        self.agent = create_agent(
            model=self.model,
            tools=self.tools,
            system_prompt=SYSTEM_PROMPT,
            checkpointer=self.memory,
            store=self.store,
            debug=False,
        )

    def config_for_session(self, session_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": session_id}}

    def invoke_chat(self, session_id: str, message: str) -> dict[str, Any]:
        try:
            result = self.agent.invoke(
                {"messages": [HumanMessage(content=message)]},
                config=self.config_for_session(session_id),
            )
        except Exception as exc:
            return {
                "session_id": session_id,
                "answer": f"模型调用失败：{exc}",
                "knowledge_base": self.kb.stats(),
                "mcp": self.mcp_registry.status(),
            }

        answer = extract_text_from_model_output(result)
        if not answer.strip():
            answer = "模型没有返回可解析的答案。"

        return {
            "session_id": session_id,
            "answer": answer,
            "knowledge_base": self.kb.stats(),
            "mcp": self.mcp_registry.status(),
        }

    def stream_chat(self, session_id: str, message: str) -> Iterator[dict[str, Any]]:
        try:
            stream = self.agent.stream(
                {"messages": [HumanMessage(content=message)]},
                config=self.config_for_session(session_id),
                stream_mode=["messages", "updates"],
            )
        except Exception as exc:
            yield {
                "event": "error",
                "data": {
                    "session_id": session_id,
                    "error": f"模型流式调用失败：{exc}",
                },
            }
            return

        last_snapshot = ""
        accumulated_text = ""

        try:
            for event in stream:
                text = extract_stream_text(event)
                if not text:
                    continue
                if text.startswith(last_snapshot):
                    delta = text[len(last_snapshot) :]
                else:
                    delta = text
                if not delta:
                    continue

                accumulated_text += delta
                last_snapshot = text if len(text) >= len(last_snapshot) else last_snapshot + delta
                yield {"event": "delta", "data": delta}
        except Exception as exc:
            yield {
                "event": "error",
                "data": {
                    "session_id": session_id,
                    "error": f"流式生成过程中出错：{exc}",
                },
            }
            return

        if not accumulated_text.strip():
            final = self.invoke_chat(session_id=session_id, message=message)
            yield {"event": "delta", "data": final["answer"]}
            yield {"event": "done", "data": final}
            return

        yield {
            "event": "done",
            "data": {
                "session_id": session_id,
                "answer": accumulated_text,
                "knowledge_base": self.kb.stats(),
                "mcp": self.mcp_registry.status(),
            },
        }

    def add_upload(self, file_name: str, raw_bytes: bytes) -> UploadRecord:
        from datetime import datetime
        from pathlib import Path

        from agent_app.settings import UPLOAD_DIR

        stored_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_filename(file_name)}"
        stored_path = UPLOAD_DIR / stored_name
        stored_path.write_bytes(raw_bytes)

        text = self._extract_text_for_indexing(file_name=file_name, raw_bytes=raw_bytes)
        return self.kb.add_file(file_name=file_name, text=text, stored_path=stored_path)

    def _extract_text_for_indexing(self, file_name: str, raw_bytes: bytes) -> str:
        from pathlib import Path

        suffix = Path(file_name).suffix.lower()
        if suffix in {".txt", ".md", ".markdown", ".json", ".csv", ".tsv", ".log", ".py", ".yaml", ".yml", ".toml"}:
            return raw_bytes.decode("utf-8", errors="ignore")

        text = raw_bytes.decode("utf-8", errors="ignore").strip()
        if text:
            return text

        raise ValueError(
            f"当前 demo 仅支持可直接转成文本的文件类型。文件 {file_name} 解析后没有可检索文本。"
        )

