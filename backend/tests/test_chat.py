from contextlib import asynccontextmanager
from typing import Any

import pytest

from app.config import Settings
from app.orchestrator import SYSTEM_PROMPT, ChatOrchestrator
from app.security import Principal


class FakeMcpClient:
    @asynccontextmanager
    async def connect(self, _access_token: str):
        yield object()

    async def tools_for_ollama(self, _session: object) -> list[dict[str, Any]]:
        return []


class FakeOrchestrator:
    def __init__(self) -> None:
        self.access_token = ""
        self.message = ""

    async def chat(self, _principal: Principal, access_token: str, message: str) -> str:
        self.access_token = access_token
        self.message = message
        return "Resposta do assistente"


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_chat_route_forwards_authenticated_message(client, alice_token, monkeypatch):
    fake = FakeOrchestrator()
    monkeypatch.setattr("app.routes.orchestrator", fake)

    response = await client.post(
        "/api/v1/chat", headers=auth(alice_token), json={"message": "Liste o catalogo"}
    )

    assert response.status_code == 200
    assert response.json()["data"] == {"reply": "Resposta do assistente"}
    assert fake.access_token == alice_token
    assert fake.message == "Liste o catalogo"


@pytest.mark.asyncio
async def test_orchestrator_sends_complete_session_history(monkeypatch):
    orchestrator = ChatOrchestrator(Settings())
    orchestrator.mcp_client = FakeMcpClient()
    requests: list[list[dict[str, Any]]] = []

    async def ask_ollama(messages: list[dict[str, Any]], _tools: list[dict[str, Any]]):
        requests.append(messages.copy())
        return {"role": "assistant", "content": f"Resposta {len(requests)}"}

    monkeypatch.setattr(orchestrator, "_ask_ollama", ask_ollama)
    principal = Principal(user_id="usr_alice", session_id="sessao-a")

    await orchestrator.chat(principal, "token-a", "Primeira mensagem")
    await orchestrator.chat(principal, "token-a", "Segunda mensagem")
    await orchestrator.chat(
        Principal(user_id="usr_alice", session_id="sessao-b"), "token-b", "Outra sessao"
    )

    assert requests[1] == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Primeira mensagem"},
        {"role": "assistant", "content": "Resposta 1"},
        {"role": "user", "content": "Segunda mensagem"},
    ]
    assert requests[2] == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Outra sessao"},
    ]
