from __future__ import annotations

import asyncio
from typing import Any

from agent_app.settings import McpConfig


class MCPRegistry:
    """管理配置文件中声明的单个 MCP 服务。"""

    def __init__(self, config: McpConfig) -> None:
        self.config = config

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.config.enabled,
            "server_name": self.config.server_name,
            "transport": self.config.transport,
            "server_url": self.config.server_url,
        }

    def load_tools(self) -> list[Any]:
        """加载 MCP 工具；MCP 未启用时返回空列表。"""
        if not self.config.enabled:
            return []

        from langchain_mcp_adapters.client import MultiServerMCPClient

        if self.config.transport == "stdio":
            connection: dict[str, Any] = {
                "transport": "stdio",
                "command": self.config.command,
                "args": list(self.config.args),
            }
        else:
            connection = {
                "transport": "streamable_http",
                "url": self.config.server_url,
            }

        client = MultiServerMCPClient({self.config.server_name: connection})
        return asyncio.run(client.get_tools())
