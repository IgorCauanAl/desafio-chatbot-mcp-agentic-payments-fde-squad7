import json
import os
from typing import Any
from uuid import uuid4

import httpx

class BackendClient:
    def __init__(self):
        self.base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        token = os.getenv("BACKEND_TOKEN")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=10.0,
        )

    async def listar_catalogo(self, categoria: str | None = None) -> dict[str, Any]:
        params = {"category": categoria} if categoria else {}

        try:
            response = await self.client.get("/api/v1/products", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return self._error_response(e)

    async def registrar_intencao(self, produto_id: str, quantidade: int) -> dict[str, Any]:
        payload = {"product_id": produto_id, "quantity": quantidade}
        try:
            response = await self.client.post("/api/v1/purchase-intentions", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return self._error_response(e)

    async def realizar_compra(self, intencao_id: str, metodo_pagamento: str) -> dict[str, Any]:
        payload = {"intention_id": intencao_id, "payment_method": metodo_pagamento}
        try:
            response = await self.client.post(
                "/api/v1/purchases",
                json=payload,
                headers={"Idempotency-Key": str(uuid4())},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return self._error_response(e)

    async def fechar(self):
        await self.client.aclose()

    @staticmethod
    def _error_response(error: httpx.HTTPError) -> dict[str, Any]:
        if isinstance(error, httpx.HTTPStatusError):
            try:
                return error.response.json()
            except json.JSONDecodeError:
                pass
        return {
            "error": {
                "code": "FALHA_COMUNICACAO_BACKEND",
                "message": "Não foi possível contatar o sistema de pagamentos.",
            }
        }