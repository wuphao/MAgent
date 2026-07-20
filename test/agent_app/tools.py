from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from agent_app.knowledge_base import LocalKnowledgeBase
from agent_app.mcp_registry import MCPRegistry
from agent_app.text_utils import safe_math_eval


def create_tools(kb: LocalKnowledgeBase, mcp: MCPRegistry) -> list[Any]:
    @tool
    def rag_search(query: str) -> str:
        """在本地知识库中检索与问题相关的资料。"""
        documents = kb.search(query)
        if not documents:
            return "没有找到相关资料。"
        return "\n\n".join(
            f"来源：{doc.metadata.get('source', '未知')}\n内容：{doc.page_content}"
            for doc in documents
        )

    @tool
    def calculator(expression: str) -> str:
        """计算只包含数字、括号和基本运算符的数学表达式。"""
        try:
            return safe_math_eval(expression)
        except (SyntaxError, ValueError, ZeroDivisionError) as error:
            return f"计算失败：{error}"

    @tool
    def mcp_status() -> str:
        """查看 MCP 服务的配置和启用状态。"""
        return json.dumps(mcp.status(), ensure_ascii=False)

    return [rag_search, calculator, mcp_status]
