from __future__ import annotations

import json
import os
from typing import Any


class MCPRegistry:
    def __init__(self) -> None:
        self.enabled = os.getenv("MCP_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
        self.server_url = os.getenv("MCP_SERVER_URL", "").strip()
        self.server_name = os.getenv("MCP_SERVER_NAME", "local-mcp").strip()
        self.notes = os.getenv("MCP_NOTES", "MCP bridge reserved for future tool integrations.").strip()

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "server_name": self.server_name,
            "server_url": self.server_url,
            "notes": self.notes,
        }

    def call(self, tool_name: str, arguments: str) -> str:
        if not self.enabled:
            return (
                "MCP 尚未启用。你可以通过环境变量 MCP_ENABLED=true、MCP_SERVER_URL 等参数接入外部工具。"
            )
        return json.dumps(
            {
                "status": "reserved",
                "tool_name": tool_name,
                "arguments": arguments,
                "note": "This project has a stable MCP extension point, but the remote transport is not wired yet.",
            },
            ensure_ascii=False,
        )

