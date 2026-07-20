from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver

from agent_app.knowledge_base import LocalKnowledgeBase
from agent_app.mcp_registry import MCPRegistry
from agent_app.prompts import SYSTEM_PROMPT
from agent_app.settings import AppConfig
from agent_app.tools import create_tools


class AgentService:
    """统一管理模型、知识库、工具和会话记忆。"""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.knowledge_base = LocalKnowledgeBase(config.ollama, config.rag)
        self.mcp = MCPRegistry(config.mcp)

        self.agent = self._create_agent()

    def _create_agent(self) -> Any:
        """创建 Agent，并注册内置工具和 MCP 工具。"""
        ollama_config = self.config.ollama
        model = ChatOllama(
            model=ollama_config.chat_model,
            base_url=ollama_config.base_url,
            temperature=ollama_config.temperature,
        )

        built_in_tools = create_tools(self.knowledge_base, self.mcp)
        external_tools = self.mcp.load_tools()

        return create_agent(
            model=model,
            tools=[*built_in_tools, *external_tools],
            system_prompt=SYSTEM_PROMPT,
            checkpointer=MemorySaver(),
        )

    def chat(self, message: str, session_id: str = "console") -> str:
        result = self.agent.invoke(
            {"messages": [HumanMessage(content=message)]},
            config={"configurable": {"thread_id": session_id}},
        )
        return self._last_message_text(result)

    def add_document(self, path: Path) -> None:
        self.knowledge_base.add_file(path)

    def status(self) -> dict[str, Any]:
        return {
            "rag": self.knowledge_base.stats(),
            "mcp": self.mcp.status(),
        }

    @staticmethod
    def _last_message_text(result: dict[str, Any]) -> str:
        content = result["messages"][-1].content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(item.get("text", "") for item in content if isinstance(item, dict))
        return str(content)
