import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any

import httpx
from mcp.shared.exceptions import McpError

from app.config import Settings
from app.errors import ApiError
from app.mcp_client import McpClient
from app.security import Principal

SYSTEM_PROMPT = """Voce e o assistente de pagamentos da loja.
Atenda apenas pedidos sobre catalogo, intencao de compra e compra.
Use as tools para consultar catalogo, registrar uma intencao ou realizar uma compra.
Nunca invente produtos, preco, estoque, identificadores, status ou resultados de pagamento.
Antes de registrar uma intencao, obtenha produto_id e quantidade; antes de comprar, obtenha
intencao_id e metodo_pagamento. Se faltar algum dado, pergunte de forma objetiva.
Quando uma tool retornar uma recusa ou erro, explique-a de forma amigavel, informe o proximo
passo possivel e nunca diga que a compra foi aprovada. Nao exponha detalhes internos do sistema.
Responda sempre em portugues do Brasil."""


class ChatOrchestrator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.mcp_client = McpClient(settings)
        self.histories: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def chat(self, principal: Principal, access_token: str, message: str) -> str:
        return "".join(
            [chunk async for chunk in self.stream_chat(principal, access_token, message)]
        )

    async def stream_chat(
        self, principal: Principal, access_token: str, message: str
    ) -> AsyncIterator[str]:
        async with self.locks[principal.session_id]:
            turn: list[dict[str, Any]] = [{"role": "user", "content": message}]
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *self.histories[principal.session_id],
                *turn,
            ]
            try:
                async with self.mcp_client.connect(access_token) as session:
                    tools = await self.mcp_client.tools_for_ollama(session)
                    for _ in range(self.settings.max_tool_iterations):
                        assistant: dict[str, Any] = {"role": "assistant", "content": ""}
                        content_parts: list[str] = []
                        tool_calls: list[dict[str, Any]] = []
                        async for delta in self._stream_ollama(messages, tools):
                            content = delta.get("content")
                            if isinstance(content, str) and content:
                                content_parts.append(content)
                                yield content
                            delta_tool_calls = delta.get("tool_calls", [])
                            if isinstance(delta_tool_calls, list):
                                tool_calls.extend(
                                    call for call in delta_tool_calls if isinstance(call, dict)
                                )
                        assistant["content"] = "".join(content_parts)
                        if tool_calls:
                            assistant["tool_calls"] = tool_calls
                        messages.append(assistant)
                        turn.append(assistant)
                        if not tool_calls:
                            if assistant["content"].strip():
                                self.histories[principal.session_id].extend(turn)
                                return
                            raise ApiError(
                                502,
                                "RESPOSTA_LLM_INVALIDA",
                                "O assistente nao conseguiu concluir a resposta. Tente novamente.",
                            )
                        for tool_call in tool_calls:
                            function = tool_call.get("function", {})
                            name = function.get("name")
                            arguments = self._tool_arguments(function.get("arguments", {}))
                            if not isinstance(name, str):
                                raise ApiError(
                                    502,
                                    "RESPOSTA_LLM_INVALIDA",
                                    (
                                        "O assistente nao conseguiu concluir a resposta. "
                                        "Tente novamente."
                                    ),
                                )
                            result = await self.mcp_client.call_tool(session, name, arguments)
                            tool_message = {"role": "tool", "tool_name": name, "content": result}
                            messages.append(tool_message)
                            turn.append(tool_message)
            except (McpError, OSError, httpx.HTTPError) as exc:
                raise ApiError(
                    503,
                    "ORQUESTRADOR_INDISPONIVEL",
                    "O assistente esta indisponivel no momento. Tente novamente em instantes.",
                ) from exc
            raise ApiError(
                502,
                "LIMITE_DE_TOOLS_ATINGIDO",
                "O assistente nao conseguiu concluir a solicitacao. Tente reformular a mensagem.",
            )

    async def _stream_ollama(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[dict[str, Any]]:
        async with httpx.AsyncClient(
            base_url=self.settings.ollama_base_url, timeout=60.0
        ) as client:
            async with client.stream(
                "POST",
                "/api/chat",
                json={
                    "model": self.settings.ollama_model,
                    "messages": messages,
                    "tools": tools,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ApiError(
                            502,
                            "RESPOSTA_LLM_INVALIDA",
                            "O assistente nao conseguiu concluir a resposta. Tente novamente.",
                        ) from exc
                    assistant = data.get("message")
                    if not isinstance(assistant, dict) or assistant.get("role") != "assistant":
                        raise ApiError(
                            502,
                            "RESPOSTA_LLM_INVALIDA",
                            "O assistente nao conseguiu concluir a resposta. Tente novamente.",
                        )
                    yield assistant

    @staticmethod
    def _tool_arguments(arguments: object) -> dict[str, Any]:
        if isinstance(arguments, dict):
            return arguments
        if isinstance(arguments, str):
            try:
                parsed = json.loads(arguments)
            except json.JSONDecodeError:
                return {}
            if isinstance(parsed, dict):
                return parsed
        return {}
