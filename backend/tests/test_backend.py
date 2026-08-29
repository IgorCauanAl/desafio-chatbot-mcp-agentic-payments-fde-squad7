from uuid import uuid4

import pytest


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_protected_catalog_and_login(client, alice_token):
    assert (await client.get("/api/v1/products")).status_code == 401
    response = await client.get("/api/v1/products", headers=auth(alice_token))
    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["pix", "cartao"])
async def test_purchase_with_both_methods(client, alice_token, method):
    intent = await client.post(
        "/api/v1/purchase-intentions",
        headers=auth(alice_token),
        json={"product_id": "prod_002", "quantity": 1},
    )
    intention_id = intent.json()["data"]["intention_id"]
    response = await client.post(
        "/api/v1/purchases",
        headers={**auth(alice_token), "Idempotency-Key": str(uuid4())},
        json={"intention_id": intention_id, "payment_method": method},
    )
    assert response.status_code == 201
    assert response.json()["data"]["payment_method"] == method


@pytest.mark.asyncio
async def test_rejects_forged_and_cross_session_intentions(client, alice_token):
    forged = await client.post(
        "/api/v1/purchases",
        headers={**auth(alice_token), "Idempotency-Key": str(uuid4())},
        json={"intention_id": "int_inventada", "payment_method": "pix"},
    )
    assert forged.status_code == 404
    assert forged.json()["error"]["code"] == "INTENCAO_INVALIDA"

    intent = await client.post(
        "/api/v1/purchase-intentions",
        headers=auth(alice_token),
        json={"product_id": "prod_001", "quantity": 1},
    )
    new_login = await client.post(
        "/api/v1/auth/tokens", json={"email": "alice@example.com", "password": "alice123"}
    )
    new_token = new_login.json()["data"]["access_token"]
    cross_session = await client.post(
        "/api/v1/purchases",
        headers={**auth(new_token), "Idempotency-Key": str(uuid4())},
        json={"intention_id": intent.json()["data"]["intention_id"], "payment_method": "pix"},
    )
    assert cross_session.json()["error"]["code"] == "INTENCAO_INVALIDA"


@pytest.mark.asyncio
async def test_limit_and_reuse_are_rejected(client, alice_token, bob_token):
    expensive = await client.post(
        "/api/v1/purchase-intentions",
        headers=auth(bob_token),
        json={"product_id": "prod_003", "quantity": 1},
    )
    denied = await client.post(
        "/api/v1/purchases",
        headers={**auth(bob_token), "Idempotency-Key": str(uuid4())},
        json={"intention_id": expensive.json()["data"]["intention_id"], "payment_method": "pix"},
    )
    assert denied.json()["error"]["code"] == "LIMITE_EXCEDIDO"

    intent = await client.post(
        "/api/v1/purchase-intentions",
        headers=auth(alice_token),
        json={"product_id": "prod_002", "quantity": 1},
    )
    payload = {"intention_id": intent.json()["data"]["intention_id"], "payment_method": "cartao"}
    first = await client.post(
        "/api/v1/purchases",
        headers={**auth(alice_token), "Idempotency-Key": str(uuid4())},
        json=payload,
    )
    assert first.status_code == 201
    reused = await client.post(
        "/api/v1/purchases",
        headers={**auth(alice_token), "Idempotency-Key": str(uuid4())},
        json=payload,
    )
    assert reused.json()["error"]["code"] == "INTENCAO_JA_PAGA"
