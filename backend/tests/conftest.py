import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["JWT_SECRET"] = "test-secret-with-at-least-32-characters"

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client():
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            yield http


@pytest_asyncio.fixture
async def alice_token(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/tokens", json={"email": "alice@example.com", "password": "alice123"}
    )
    return response.json()["data"]["access_token"]


@pytest_asyncio.fixture
async def bob_token(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/tokens", json={"email": "bob@example.com", "password": "bob12345"}
    )
    return response.json()["data"]["access_token"]
