from __future__ import annotations

from pathlib import Path

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agent_app.memory import Memory, MemoryStore
from agent_app.rag_evaluator import EvaluationSummary, evaluate_retrieval
from agent_app.rag import create_rag_store
from agent_app.settings import AppConfig


SYSTEM_PROMPT = """
你是一个简洁的中文助手。默认使用中文回答。
如果用户问题附带了“长期记忆”，请把它作为用户偏好或项目背景使用。
如果用户问题附带了“本地知识库资料”，请优先根据资料回答。
知识库资料不足时，必须明确回答“知识库中没有足够信息”。
只引用资料中实际出现的来源，不得编造文件名、页码或章节。
使用知识库作答时，在关键结论后使用 [资料 N] 标注引用。
""".strip()


class ChatService:
    """DeepSeek chat service with optional long-term memory and local RAG."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
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
        retrieval_query = self._rewrite_query(message)
        user_message = self._build_augmented_message(message, retrieval_query)
        response = self._model.invoke([*self._messages, HumanMessage(content=user_message)])
        answer = self._message_text(response)
        self._messages.append(HumanMessage(content=message))
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

    def evaluate(self, dataset_path: str) -> EvaluationSummary:
        if self._rag is None:
            raise RuntimeError("RAG is disabled.")
        return evaluate_retrieval(
            self._rag.search, Path(dataset_path).expanduser().resolve()
        )

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

    def _build_augmented_message(self, message: str, retrieval_query: str) -> str:
        sections = []

        if self._memory is not None:
            memories = self._memory.search(retrieval_query)
            if memories:
                memory_context = "\n".join(
                    f"- ({memory.kind}) {memory.content}" for memory in memories
                )
                sections.append(f"长期记忆：\n{memory_context}")

        if self._rag is not None:
            documents = self._rag.search(retrieval_query)
            if documents:
                rag_context = self._format_context(documents)
                sections.append(f"本地知识库资料：\n{rag_context}")

        if not sections:
            return message

        context = "\n\n".join(sections)
        return f"{context}\n\n用户问题：\n{message}"

    def _rewrite_query(self, message: str) -> str:
        """Resolve follow-up references against recent conversation for retrieval."""
        if len(self._messages) <= 1 or not any(
            marker in message.lower()
            for marker in ("它", "这个", "那个", "上面", "前面", "其", "this", "that", "it")
        ):
            return message
        recent = self._messages[-6:]
        history = "\n".join(
            f"{'用户' if isinstance(item, HumanMessage) else '助手'}：{self._message_text(item)}"
            for item in recent
        )
        prompt = (
            "把新问题改写成可独立用于知识库检索的问题。保留专有名词和约束，"
            "不要回答问题，只输出改写后的单行问题。\n\n"
            f"对话历史：\n{history}\n\n新问题：{message}"
        )
        try:
            response = self._model.invoke([SystemMessage(content="你是检索查询改写器。"), HumanMessage(content=prompt)])
            rewritten = self._message_text(response).strip().splitlines()[0]
            return rewritten or message
        except Exception:
            return message

    def _format_context(self, documents: list[dict[str, object]]) -> str:
        budget = self._config.rag.max_context_chars
        blocks: list[str] = []
        used = 0
        for index, document in enumerate(documents, start=1):
            metadata = document["metadata"]
            location = [f"来源：{metadata.get('file_name') or metadata.get('source', '未知')}"]
            if metadata.get("page"):
                location.append(f"页码：{metadata['page']}")
            if metadata.get("section"):
                location.append(f"章节：{metadata['section']}")
            block = f"[资料 {index}]\n{'；'.join(location)}\n内容：{document['content']}"
            remaining = budget - used
            if remaining <= 0:
                break
            if len(block) > remaining:
                block = block[:remaining]
            blocks.append(block)
            used += len(block) + 2
        return "\n\n".join(blocks)

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
