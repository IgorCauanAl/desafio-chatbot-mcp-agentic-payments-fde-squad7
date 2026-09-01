import json
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
log = structlog.get_logger(__name__)
MAX_LOG_VALUE_LENGTH = 4000
SENSITIVE_KEYS = {"access_token", "authorization", "backend_token", "refresh_token", "token"}


class McpClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # capturando as informações que a IA está passando para o monitoramento
    def log(self, event: str, **data: Any) -> None:
        log.info(event, **{key: self._safe_log_value(key, value) for key, value in data.items()})

    @classmethod
    def _safe_log_value(cls, key: str, value: Any) -> Any:
        if key.lower() in SENSITIVE_KEYS:
            return "[REDACTED]"
        if isinstance(value, dict):
            return {
                str(item_key): cls._safe_log_value(str(item_key), item)
                for item_key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._safe_log_value(key, item) for item in value]
        if isinstance(value, str) and len(value) > MAX_LOG_VALUE_LENGTH:
            return f"{value[:MAX_LOG_VALUE_LENGTH]}...[truncated]"
        return value

    @asynccontextmanager
    async def connect(self, access_token: str) -> AsyncIterator[ClientSession]:
        server_cwd = PROJECT_ROOT / self.settings.mcp_server_cwd
        self.log("mcp_connect_start", server_cwd=str(server_cwd), access_token=access_token)
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
                self.log("mcp_connected", module=self.settings.mcp_server_module)
                yield session

    async def tools_for_ollama(self, session: ClientSession) -> list[dict[str, Any]]:
        result = await session.list_tools()
        tools = [
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
        self.log("mcp_tools_loaded", tool_names=[tool["function"]["name"] for tool in tools])
        return tools

    async def call_tool(
        self,
        session: ClientSession,
        name: str,
        arguments: dict[str, Any],
        *,
        user_id: str,
        session_id: str,
    ) -> str:
        audit = {
            "user_id": user_id,
            "session_id": session_id,
            "tool_name": name,
            "quantity": arguments.get("quantidade"),
            "amount": self._amount_from(arguments),
        }
        self.log("mcp_tool_call", **audit, arguments=arguments)
        try:
            result = await session.call_tool(name, arguments)
            serialized_result = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
        except Exception as exc:
            self.log("mcp_tool_result", **audit, status="error", error=str(exc))
            raise

        self.log(
            "mcp_tool_result",
            **audit,
            status=self._status_from(serialized_result),
            amount=self._amount_from(serialized_result) or audit["amount"],
            result=serialized_result,
        )
        return serialized_result

    @staticmethod
    def _amount_from(value: Any) -> Any:
        if isinstance(value, dict):
            for key in ("valor_total", "total_amount", "valor", "amount"):
                if value.get(key) is not None:
                    return value[key]
            for item in value.values():
                amount = McpClient._amount_from(item)
                if amount is not None:
                    return amount
            return None
        if isinstance(value, str):
            try:
                return McpClient._amount_from(json.loads(value))
            except json.JSONDecodeError:
                return None
        if isinstance(value, list):
            for item in value:
                amount = McpClient._amount_from(item)
                if amount is not None:
                    return amount
        return None

    @staticmethod
    def _status_from(value: str) -> str:
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            return "unknown"
        if isinstance(payload, dict):
            for key in ("status", "status_code"):
                if payload.get(key) is not None:
                    return str(payload[key])
            error = payload.get("error")
            if isinstance(error, dict) and error.get("code"):
                return str(error["code"])
            for item in payload.values():
                if isinstance(item, (dict, list, str)):
                    status = McpClient._status_from(
                        item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
                    )
                    if status != "unknown":
                        return status
        return "unknown"
