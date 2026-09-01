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

SYSTEM_PROMPT = (
    "REGRA ABSOLUTA DE SAÍDA: jamais exiba ao usuário IDs internos ou informações "
    "técnicas, mesmo quando estiverem presentes no resultado de uma ferramenta. "
    "Nunca mostre IDs de produto, intenção, transação ou sessão, códigos internos, "
    "JSON, payloads, nomes de campos do backend ou logs. Após uma compra aprovada, "
    "responda em linguagem natural informando apenas que a compra foi concluída e, "
    "se necessário, produto, quantidade, valor e método de pagamento. Não crie uma "
    "seção de detalhes da transação e nunca reproduza literalmente o retorno da tool.\n\n"
    "Você é o assistente virtual de vendas da loja. Seu objetivo é guiar o cliente de forma amigável e natural através do fluxo de compras, utilizando as ferramentas (tools) disponíveis. Fale em Português do Brasil.\n\nDIRETRIZES GERAIS DE COMPORTAMENTO:\n- NUNCA exponha IDs internos (como 'prod_003', 'int_a1b2c3' ou 'tx_9f8e7d') nas mensagens para o usuário. Mostre apenas os nomes reais dos produtos.\n- NUNCA invente, deduza ou assuma informações (produtos, preços, estoque ou métodos de pagamento). Se faltar um dado, pergunte ao cliente.\n- Se o cliente mencionar 'cartão de crédito' ou 'cartão de débito', traduza silenciosamente para o argumento 'cartao' ao chamar a tool de compra.\n- Proteja o papel: Você fala com o cliente final. Não repita mensagens técnicas de log ou erros de sistema de forma literal.\n\nO FLUXO DE COMPRA OBRIGATÓRIO (MÁQUINA DE ESTADOS):\nVocê deve respeitar estritamente a ordem abaixo e pausar para aguardar a resposta do usuário a cada pergunta.\n\nESTADO 1 - CONSULTA: Se o cliente perguntar o que tem na loja, chame a tool 'listar_catalogo' e apresente os produtos em uma lista limpa e legível, com nome e preço.\n\nESTADO 2 - INTENÇÃO: Se o cliente quiser comprar um item, verifique se ele informou a quantidade. Se não, PERGUNTE a quantidade. Tendo produto e quantidade, chame 'registrar_intencao'.\n\nESTADO 3 - ESCOLHA DO PAGAMENTO: Com a intenção registrada com sucesso, informe ao cliente (sem mostrar o ID da intenção) e pergunte EXATAMENTE: 'Como você prefere pagar: Cartão de Crédito/Débito ou Pix?' -> PARE e aguarde a resposta.\n\nESTADO 4 - RESUMO E APROVAÇÃO: Após o cliente escolher a forma de pagamento, apresente um resumo claro (Produto, Quantidade, Valor Total, Método escolhido). Em seguida, pergunte: 'Você confirma a compra?' -> PARE e aguarde o 'Sim'.\n\nESTADO 5 - CONCLUSÃO: SOMENTE APÓS o cliente dizer 'Sim' ou confirmar explicitamente, chame a tool 'realizar_compra', garantindo que o argumento 'confirmado' seja passado como true (se o seu backend exigir) junto com o 'intencao_id' e o 'metodo_pagamento'.\n\nTRATAMENTO DE ERROS:\nSe a tool 'realizar_compra' retornar um erro, explique-o de forma humana. \n- Exemplo: Se retornar 'LIMITE_EXCEDIDO', diga 'Infelizmente o valor desta compra ultrapassa o seu limite disponível no momento.'\n- Exemplo: Se retornar 'INTENCAO_EXPIRADA', diga 'O tempo para finalizar este pedido expirou. Vamos montar o pedido novamente?'"
)


class ChatOrchestrator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.mcp_client = McpClient(settings)
        self.histories: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.session_tokens: dict[str, dict[str, str]] = defaultdict(dict)

    def register_session_tokens(
        self,
        session_id: str,
        access_token: str,
        refresh_token: str,
    ) -> None:
        self.session_tokens[session_id] = {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def _refresh_access_token(self, refresh_token: str) -> tuple[str, str]:
        async with httpx.AsyncClient(
            base_url=self.settings.backend_base_url, timeout=30.0
        ) as client:
            response = await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
            )
            response.raise_for_status()
        payload = response.json()
        data = payload.get("data", {})
        return str(data.get("access_token", "")), str(data.get("refresh_token", refresh_token))

    async def chat(self, principal: Principal, access_token: str, message: str) -> str:
        return "".join(
            [chunk async for chunk in self.stream_chat(principal, access_token, message)]
        )

    async def stream_chat(
        self, principal: Principal, access_token: str, message: str
    ) -> AsyncIterator[str]:
        current_access_token = self.session_tokens.get(principal.session_id, {}).get(
            "access_token", access_token
        )
        current_refresh_token = self.session_tokens.get(principal.session_id, {}).get(
            "refresh_token"
        )

        async with self.locks[principal.session_id]:
            turn: list[dict[str, Any]] = [{"role": "user", "content": message}]
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *self.histories[principal.session_id],
                *turn,
            ]
            try:
                for attempt in range(3):
                    try:
                        async with self.mcp_client.connect(current_access_token) as session:
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
                                            call
                                            for call in delta_tool_calls
                                            if isinstance(call, dict)
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
                                        (
                                            "O assistente nao conseguiu concluir a resposta. "
                                            "Tente novamente."
                                        ),
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
                                    result = await self.mcp_client.call_tool(
                                        session,
                                        name,
                                        arguments,
                                        user_id=principal.user_id,
                                        session_id=principal.session_id,
                                    )
                                    tool_message = {
                                        "role": "tool",
                                        "tool_name": name,
                                        "tool_call_id": tool_call.get("id", ""),
                                        "content": result,
                                    }
                                    messages.append(tool_message)
                                    turn.append(tool_message)
                                    if name == "realizar_compra":
                                        purchase_message = self._purchase_message(result)
                                        if purchase_message:
                                            assistant_response = {
                                                "role": "assistant",
                                                "content": purchase_message,
                                            }
                                            messages.append(assistant_response)
                                            turn.append(assistant_response)
                                            self.histories[principal.session_id].extend(turn)
                                            yield purchase_message
                                            return
                        return
                    except ApiError as exc:
                        if (
                            exc.status_code == 401
                            and exc.code in {"TOKEN_INVALIDO", "NAO_AUTENTICADO"}
                            and current_refresh_token
                            and attempt < 2
                        ):
                            new_access, new_refresh = await self._refresh_access_token(
                                current_refresh_token
                            )
                            current_access_token = new_access
                            current_refresh_token = new_refresh
                            self.register_session_tokens(
                                principal.session_id, current_access_token, current_refresh_token
                            )
                            continue
                        raise
            except (McpError, OSError, httpx.HTTPError) as exc:
                raise ApiError(
                    503,
                    "ORQUESTRADOR_INDISPONIVEL",
                    "O assistente esta indisponivel no momento. Tente novamente em instantes.",
                ) from exc
            except BaseExceptionGroup as exc:
                api_error = self._find_api_error(exc)
                if api_error is not None:
                    raise api_error from exc
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
        if self.settings.llm_provider.strip().lower() == "groq":
            async for delta in self._stream_groq(messages, tools):
                yield delta
            return

        api_key = (self.settings.gemini_api_key or "").strip()
        if not api_key:
            raise ApiError(
                503,
                "LLM_INDISPONIVEL",
                "A chave da API do Gemini nao foi configurada. Defina a variavel GEMINI_API_KEY.",
            )

        base_url = self.settings.gemini_api_base_url.rstrip("/")
        model = self.settings.gemini_model
        url = f"{base_url}/models/{model}:generateContent"
        payload = {
            "contents": self._gemini_contents(messages),
            "generationConfig": {"temperature": 0.2},
        }
        if tools:
            payload["tools"] = [
                {"functionDeclarations": [self._gemini_tool_declaration(tool) for tool in tools]}
            ]

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                },
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response is not None and exc.response.status_code == 429:
                    raise ApiError(
                        503,
                        "LLM_SOBRECARREGADO",
                        (
                            "O assistente esta temporariamente ocupado. "
                            "Tente novamente em alguns segundos."
                        ),
                    ) from exc
                detail = exc.response.text[:600] if exc.response is not None else str(exc)
                raise ApiError(
                    502,
                    "RESPOSTA_LLM_INVALIDA",
                    f"Falha na comunicação com o Gemini: {detail}",
                ) from exc

            data = response.json()
            candidates = data.get("candidates") or []
            if not candidates:
                raise ApiError(
                    502,
                    "RESPOSTA_LLM_INVALIDA",
                    "O assistente nao conseguiu concluir a resposta. Tente novamente.",
                )

            parts = candidates[0].get("content", {}).get("parts", [])
            text_parts: list[str] = []
            tool_calls: list[dict[str, Any]] = []

            for part in parts:
                if "text" in part:
                    text_parts.append(str(part["text"]))
                if "functionCall" in part:
                    function_call = part["functionCall"]
                    tool_calls.append(
                        {
                            "id": function_call.get("id") or f"call_{len(tool_calls)}",
                            "type": "function",
                            "function": {
                                "name": function_call.get("name"),
                                "arguments": function_call.get("args", {}),
                            },
                        }
                    )

            if tool_calls:
                yield {"role": "assistant", "content": "", "tool_calls": tool_calls}
                return

            response_text = "".join(text_parts).strip()
            if not response_text:
                raise ApiError(
                    502,
                    "RESPOSTA_LLM_INVALIDA",
                    "O assistente nao conseguiu concluir a resposta. Tente novamente.",
                )

            yield {"role": "assistant", "content": response_text}

    async def _stream_groq(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[dict[str, Any]]:
        api_key = (self.settings.groq_api_key or "").strip()
        if not api_key:
            raise ApiError(
                503,
                "LLM_INDISPONIVEL",
                "A chave da API da Groq nao foi configurada. Defina a variavel GROQ_API_KEY.",
            )

        payload: dict[str, Any] = {
            "model": self.settings.groq_model,
            "messages": self._openai_messages(messages),
            "temperature": 0.2,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.settings.groq_api_base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response is not None and exc.response.status_code == 429:
                    raise ApiError(
                        503,
                        "LLM_SOBRECARREGADO",
                        (
                            "O assistente esta temporariamente ocupado. "
                            "Tente novamente em alguns segundos."
                        ),
                    ) from exc
                detail = exc.response.text[:600] if exc.response is not None else str(exc)
                raise ApiError(
                    502,
                    "RESPOSTA_LLM_INVALIDA",
                    f"Falha na comunicação com a Groq: {detail}",
                ) from exc

        choices = response.json().get("choices") or []
        if not choices:
            raise ApiError(
                502,
                "RESPOSTA_LLM_INVALIDA",
                "O assistente nao conseguiu concluir a resposta. Tente novamente.",
            )

        assistant_message = choices[0].get("message") or {}
        raw_tool_calls = assistant_message.get("tool_calls") or []
        if isinstance(raw_tool_calls, list) and raw_tool_calls:
            normalized_calls = []
            for call in raw_tool_calls:
                if not isinstance(call, dict):
                    continue
                function = call.get("function") or {}
                normalized_calls.append(
                    {
                        "id": call.get("id") or f"call_{len(normalized_calls)}",
                        "type": "function",
                        "function": {
                            "name": function.get("name"),
                            "arguments": function.get("arguments", {}),
                        },
                    }
                )
            if normalized_calls:
                yield {"role": "assistant", "content": "", "tool_calls": normalized_calls}
                return

        content = assistant_message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ApiError(
                502,
                "RESPOSTA_LLM_INVALIDA",
                "O assistente nao conseguiu concluir a resposta. Tente novamente.",
            )
        yield {"role": "assistant", "content": content}

    @staticmethod
    def _gemini_contents(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if role == "system":
                converted.append(
                    {
                        "role": "user",
                        "parts": [{"text": f"Sistema: {content or ''}"}],
                    }
                )
                continue
            if role == "tool":
                converted.append(
                    {
                        "role": "user",
                        "parts": [{"text": f"Ferramenta: {content or ''}"}],
                    }
                )
                continue
            if isinstance(content, str) and content:
                converted.append(
                    {
                        "role": "model" if role == "assistant" else "user",
                        "parts": [{"text": content}],
                    }
                )
        return converted

    @staticmethod
    def _openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for message in messages:
            role = message.get("role")
            if role == "tool":
                converted.append(
                    {
                        "role": "tool",
                        "tool_call_id": message.get("tool_call_id", ""),
                        "content": message.get("content", ""),
                    }
                )
                continue
            converted_message: dict[str, Any] = {
                "role": role if role in {"system", "user", "assistant"} else "user",
                "content": message.get("content", ""),
            }
            if role == "assistant" and message.get("tool_calls"):
                converted_message["tool_calls"] = message["tool_calls"]
            converted.append(converted_message)
        return converted

    @staticmethod
    def _gemini_tool_declaration(tool: dict[str, Any]) -> dict[str, Any]:
        function = tool.get("function", {})
        schema = function.get("parameters", {})
        return {
            "name": function.get("name"),
            "description": function.get("description") or function.get("name"),
            "parameters": schema,
        }

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

    @staticmethod
    def _find_api_error(error: BaseExceptionGroup) -> ApiError | None:
        for nested in error.exceptions:
            if isinstance(nested, ApiError):
                return nested
            if isinstance(nested, BaseExceptionGroup):
                found = ChatOrchestrator._find_api_error(nested)
                if found is not None:
                    return found
        return None

    @staticmethod
    def _purchase_message(result: str) -> str | None:
        payload: object = result
        seen: set[int] = set()

        for _ in range(6):
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    return payload or None
            if isinstance(payload, list):
                if not payload:
                    return None
                payload = payload[0]
                continue
            if not isinstance(payload, dict):
                return payload if isinstance(payload, str) else None

            obj_id = id(payload)
            if obj_id in seen:
                break
            seen.add(obj_id)

            for key in ("data", "structured_content", "structuredContent", "content"):
                candidate = payload.get(key)
                if candidate is None:
                    continue

                if isinstance(candidate, dict):
                    payload = candidate
                    break
                if isinstance(candidate, list):
                    if not candidate:
                        return None
                    first = candidate[0]
                    if isinstance(first, dict):
                        text = first.get("text")
                        if isinstance(text, str):
                            payload = text
                            break
                    payload = first
                    break
                if isinstance(candidate, str):
                    payload = candidate
                    break
            else:
                break

        if not isinstance(payload, dict):
            if isinstance(payload, str):
                normalized = payload.strip()
                if normalized:
                    return normalized
            return None

        if payload.get("status") == "aprovado":
            return "Compra aprovada! O pagamento foi concluído com sucesso."
        if payload.get("status") == "pendente":
            return "A compra ainda não foi confirmada. Você confirma o pagamento?"

        error = payload.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message")
        else:
            code = payload.get("erro")
            message = payload.get("mensagem")

        messages = {
            "LIMITE_EXCEDIDO": "Infelizmente, o valor desta compra ultrapassa seu limite disponível.",
            "INTENCAO_EXPIRADA": "O prazo para finalizar este pedido expirou.",
            "INTENCAO_JA_PAGA": "Esta compra já foi concluída.",
            "INTENCAO_INVALIDA": "Não consegui validar este pedido. Vamos iniciar uma nova compra?",
            "METODO_INVALIDO": "Esse método de pagamento não está disponível.",
        }
        if isinstance(code, str) and code in messages:
            return messages[code]
        if isinstance(message, str) and message.strip():
            return message
        return None
