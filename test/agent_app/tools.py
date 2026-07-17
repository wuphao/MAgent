from __future__ import annotations

import json
import re

from langchain_core.tools import tool

from agent_app.knowledge_base import LocalKnowledgeBase
from agent_app.mcp_registry import MCPRegistry
from agent_app.text_utils import safe_math_eval


def create_tools(kb: LocalKnowledgeBase, mcp_registry: MCPRegistry):
    @tool("rag_search")
    def rag_search(query: str) -> str:
        """从本地知识库中检索与问题相关的资料。"""

        docs = kb.search(query)
        if not docs:
            return "没有检索到相关资料。"

        results: list[str] = []
        for index, doc in enumerate(docs, start=1):
            source = doc.metadata.get("source", "unknown")
            kind = doc.metadata.get("kind", "unknown")
            content = doc.page_content.strip()
            results.append(
                f"[检索片段 {index}]\n"
                f"来源：{source}\n"
                f"类型：{kind}\n"
                f"内容：{content}"
            )
        return "\n\n".join(results)

    @tool("calculator")
    def calculator(expression: str) -> str:
        """执行数学计算。输入示例：(1963 + 2008) / 3。"""

        if not re.fullmatch(r"[0-9+\-*/().\s]+", expression):
            return "表达式包含非法字符，无法计算。"
        try:
            return safe_math_eval(expression)
        except Exception as exc:
            return f"计算失败：{exc}"

    @tool("knowledge_base_summary")
    def knowledge_base_summary() -> str:
        """查看本地知识库的状态。"""

        return json.dumps(
            {
                "stats": kb.stats(),
                "sources": kb.list_sources()[:20],
            },
            ensure_ascii=False,
            indent=2,
        )

    @tool("mcp_status")
    def mcp_status() -> str:
        """查看预留的 MCP 扩展状态。"""

        return json.dumps(mcp_registry.status(), ensure_ascii=False, indent=2)

    @tool("mcp_call")
    def mcp_call(tool_name: str, arguments: str) -> str:
        """预留的 MCP 调用入口。"""

        return mcp_registry.call(tool_name, arguments)

    return [rag_search, calculator, knowledge_base_summary, mcp_status, mcp_call]

