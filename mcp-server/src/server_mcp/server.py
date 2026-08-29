import json
from typing import Optional
from mcp.server.fastmcp import FastMCP
from integrations.integrations import BackendClient

mcp = FastMCP("serverMCP")

backend_client = BackendClient()

@mcp.tool()
async def listar_catalogo(categoria: Optional[str] = None) -> str:

    resultado = await backend_client.listar_catalogo(categoria)
    return json.dumps(resultado, ensure_ascii=False)


@mcp.tool()
async def registrar_intencao(produto_id: str, quantidade: int) -> str:

    if quantidade <= 0:
        resultado = {

            "status": "recusado",
            "erro": "QUANTIDADE_INVALIDA",
            "mensagem": "A quantidade solicitada deve ser maior que zero."
        }
    else:
        resultado = await backend_client.registrar_intencao(produto_id, quantidade)

    return json.dumps(resultado, ensure_ascii=False)


@mcp.tool()
async def realizar_compra(intencao_id: str, metodo_pagamento: str) -> str:

    if metodo_pagamento not in ["cartao", "pix"]:
        resultado = {
            "status": "recusado",
            "erro": "METODO_INVALIDO",
            "mensagem": f"O método '{metodo_pagamento}' não é aceito. Escolha 'cartao' ou 'pix'."
        }
    else:
        resultado = await backend_client.realizar_compra(intencao_id, metodo_pagamento)

    return json.dumps(resultado, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport='stdio')