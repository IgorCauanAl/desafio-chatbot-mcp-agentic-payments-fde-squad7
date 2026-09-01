from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import Settings
from app.main import app
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

    async def stream_chat(
        self, _principal: Principal, access_token: str, message: str
    ) -> AsyncIterator[str]:
        self.access_token = access_token
        self.message = message
        yield "Resposta "
        yield "do assistente"


def test_chat_websocket_forwards_authenticated_message(monkeypatch):
    fake = FakeOrchestrator()
    monkeypatch.setattr("app.routes.orchestrator", fake)

    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/tokens",
            json={"email": "alice@example.com", "password": "alice123"},
        )
        token = login.json()["data"]["access_token"]
        with client.websocket_connect(f"/api/v1/chat/ws?token={token}") as websocket:
            websocket.send_json({"message": "Liste o catalogo"})
            assert websocket.receive_json() == {"type": "chunk", "content": "Resposta "}
            assert websocket.receive_json() == {"type": "chunk", "content": "do assistente"}
            assert websocket.receive_json() == {"type": "done"}

    assert fake.access_token == token
    assert fake.message == "Liste o catalogo"


def test_chat_websocket_rejects_invalid_input_without_closing(monkeypatch):
    monkeypatch.setattr("app.routes.orchestrator", FakeOrchestrator())

    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/tokens",
            json={"email": "alice@example.com", "password": "alice123"},
        )
        token = login.json()["data"]["access_token"]
        with client.websocket_connect(f"/api/v1/chat/ws?token={token}") as websocket:
            websocket.send_json({"message": ""})
            assert websocket.receive_json() == {
                "type": "error",
                "code": "DADOS_INVALIDOS",
                "message": "Dados de entrada inválidos",
            }
            websocket.send_json({"message": "Liste o catalogo"})
            assert websocket.receive_json() == {"type": "chunk", "content": "Resposta "}


@pytest.mark.parametrize("query", ["", "?token=invalido"])
def test_chat_websocket_rejects_invalid_token(query):
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/api/v1/chat/ws{query}"):
                pass

    assert exc_info.value.code == 1008


def test_http_chat_route_is_removed():
    with TestClient(app) as client:
        response = client.post("/api/v1/chat", json={"message": "Liste o catalogo"})

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_orchestrator_sends_complete_session_history(monkeypatch):
    orchestrator = ChatOrchestrator(Settings())
    orchestrator.mcp_client = FakeMcpClient()
    requests: list[list[dict[str, Any]]] = []

    async def stream_ollama(messages: list[dict[str, Any]], _tools: list[dict[str, Any]]):
        requests.append(messages.copy())
        yield {"role": "assistant", "content": f"Resposta {len(requests)}"}

    monkeypatch.setattr(orchestrator, "_stream_ollama", stream_ollama)
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
