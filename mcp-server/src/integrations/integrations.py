import os
import httpx
import json
from typing import Optional, Dict, Any

class BackendClient:
    def __init__(self):
        #Esperando o back-end definir as rotas
        self.base_url = os.getenv()

        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=10.0)

    async def listar_catalogo(self, categoria: Optional[str] = None) -> Dict[str, Any]:

        if categoria :
            params = {"categoria": categoria}
        else:
            params = {}

        try:
            # Esperando o back-end definir suas rotas
            response = await self.client.get("/catalogo", params=params)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            return {"erro": "FALHA_COMUNICACAO_BACKEND", "mensagem": str(e)}

    async def registrar_intencao(self, produto_id: str, quantidade: int) -> Dict[str, Any]:

        payload = {
            "produto_id": produto_id,
            "quantidade": quantidade
        }
        try:
            # Esperando o back-end definir suas rotas
            response = await self.client.post("/intencao", json=payload)

            return response.json()
        except httpx.HTTPError as e:

            # Se o back-end retornar 4xx ou 5xx, lemos o JSON de erro do backend
            if hasattr(e, 'response') and e.response is not None:
                return e.response.json()
            return {"erro": "FALHA_COMUNICACAO_BACKEND", "mensagem": str(e)}

    async def realizar_compra(self, intencao_id: str, metodo_pagamento: str) -> Dict[str, Any]:

        payload = {
            "intencao_id": intencao_id,
            "metodo_pagamento": metodo_pagamento
        }
        try:
            # Esperando o back-end definir suas rotas
            response = await self.client.post("/compra", json=payload)

            return response.json()
        except httpx.HTTPError as e:
            if hasattr(e, 'response') and e.response is not None:
                return e.response.json()
            return {
                "status": "recusado",
                "erro": "ERRO_INTERNO",
                "mensagem": "Não foi possível contatar o sistema de pagamentos."
            }

    async def fechar(self):
        # Fecha a sessão http.
        await self.client.aclose()