from __future__ import annotations

from pathlib import Path

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agent_app.memory import Memory, MemoryStore
from agent_app.rag import create_rag_store
from agent_app.settings import AppConfig


SYSTEM_PROMPT = """
你是一个简洁的中文助手。默认使用中文回答。
如果用户问题附带了“长期记忆”，请把它作为用户偏好或项目背景使用。
如果用户问题附带了“本地知识库资料”，请优先根据资料回答。
如果资料不足，请明确说明，不要编造来源。
""".strip()


class ChatService:
    """DeepSeek chat service with optional long-term memory and local RAG."""

    def __init__(self, config: AppConfig) -> None:
        deepseek = config.deepseek
        self._model = ChatOpenAI(
            model=deepseek.chat_model,
            api_key=deepseek.api_key,
            base_url=deepseek.base_url,
            temperature=deepseek.temperature,
        )
        self._rag = create_rag_store(config.rag) if config.rag.enabled else None
        self._memory = MemoryStore(config.memory) if config.memory.enabled else None
        self._messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]

    def chat(self, message: str) -> str:
        user_message = self._build_augmented_message(message)
        self._messages.append(HumanMessage(content=user_message))
        response = self._model.invoke(self._messages)
        answer = self._message_text(response)
        self._messages.append(AIMessage(content=answer))
        return answer

    def add_document(self, path: str) -> int:
        if self._rag is None:
            raise RuntimeError("RAG is disabled.")
        return self._rag.add_file(Path(path).expanduser().resolve())

    def search(self, query: str) -> list[dict[str, object]]:
        if self._rag is None:
            return []
        return self._rag.search(query)

    def rag_status(self) -> dict[str, object]:
        if self._rag is None:
            return {"enabled": False, "chunks": 0}
        return {"enabled": True, "chunks": self._rag.count()}

    def remember(self, content: str, kind: str = "fact") -> Memory:
        if self._memory is None:
            raise RuntimeError("Memory is disabled.")
        return self._memory.add(content, kind=kind)

    def memories(self) -> list[Memory]:
        if self._memory is None:
            return []
        return self._memory.list()

    def forget(self, memory_id: str) -> bool:
        if self._memory is None:
            return False
        return self._memory.forget(memory_id)

    def memory_status(self) -> dict[str, object]:
        if self._memory is None:
            return {"enabled": False, "active": 0, "total": 0}
        return self._memory.status()

    def _build_augmented_message(self, message: str) -> str:
        sections = []

        if self._memory is not None:
            memories = self._memory.search(message)
            if memories:
                memory_context = "\n".join(
                    f"- ({memory.kind}) {memory.content}" for memory in memories
                )
                sections.append(f"长期记忆：\n{memory_context}")

        if self._rag is not None:
            documents = self._rag.search(message)
            if documents:
                rag_context = "\n\n".join(
                    "[资料 {index}]\n来源：{source}\n内容：{content}".format(
                        index=index,
                        source=document["metadata"].get("source", "未知"),
                        content=document["content"],
                    )
                    for index, document in enumerate(documents, start=1)
                )
                sections.append(f"本地知识库资料：\n{rag_context}")

        if not sections:
            return message

        context = "\n\n".join(sections)
        return f"{context}\n\n用户问题：\n{message}"

    @staticmethod
    def _message_text(message: BaseMessage) -> str:
        content = message.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                item.get("text", "") for item in content if isinstance(item, dict)
            )
        return str(content)
