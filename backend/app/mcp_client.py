import json
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class McpClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @asynccontextmanager
    async def connect(self, access_token: str) -> AsyncIterator[ClientSession]:
        server_cwd = PROJECT_ROOT / self.settings.mcp_server_cwd
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", self.settings.mcp_server_module],
            cwd=str(server_cwd),
            env={
                **os.environ,
                "BACKEND_URL": self.settings.backend_base_url,
                "BACKEND_TOKEN": access_token,
            },
        )
        async with stdio_client(server) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                yield session

    async def tools_for_ollama(self, session: ClientSession) -> list[dict[str, Any]]:
        result = await session.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or tool.name,
                    "parameters": tool.inputSchema,
                },
            }
            for tool in result.tools
        ]

    async def call_tool(self, session: ClientSession, name: str, arguments: dict[str, Any]) -> str:
        result = await session.call_tool(name, arguments)
        return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
