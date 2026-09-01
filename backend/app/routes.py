import json

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.errors import ApiError
from app.models import PurchaseIntention
from app.orchestrator import ChatOrchestrator
from app.schemas import (
    ChatMessage,
    IntentionRequest,
    IntentionResponse,
    LoginRequest,
    ProductResponse,
    PurchaseRequest,
    PurchaseResponse,
    Success,
    TokenResponse,
)
from app.security import Principal, get_principal, validate_token
from app.services import authenticate, execute_purchase, get_catalog, register_intention

router = APIRouter(prefix="/api/v1")
orchestrator = ChatOrchestrator(get_settings())


@router.post(
    "/auth/tokens",
    response_model=Success[TokenResponse],
    tags=["auth"],
    summary="Autenticar usuário",
    description="Emite um JWT para credenciais válidas.",
    responses={401: {"description": "Credenciais inválidas"}},
)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    token, expires_in = await authenticate(db, data.email, data.password)
    return {"data": {"access_token": token, "token_type": "bearer", "expires_in": expires_in}}


@router.websocket("/chat/ws")
async def chat(websocket: WebSocket) -> None:
    access_token = websocket.query_params.get("token")
    if not access_token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        principal = validate_token(access_token)
    except ApiError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    while True:
        try:
            payload = await websocket.receive_json()
            data = ChatMessage.model_validate(payload)
            async for chunk in orchestrator.stream_chat(principal, access_token, data.message):
                await websocket.send_json({"type": "chunk", "content": chunk})
            await websocket.send_json({"type": "done"})
        except WebSocketDisconnect:
            return
        except (json.JSONDecodeError, ValidationError):
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "DADOS_INVALIDOS",
                    "message": "Dados de entrada inválidos",
                }
            )
        except ApiError as exc:
            await websocket.send_json({"type": "error", "code": exc.code, "message": exc.message})


@router.get(
    "/products",
    response_model=Success[list[ProductResponse]],
    tags=["products"],
    summary="Listar catálogo",
    description="Lista produtos com paginação e categoria opcional.",
    responses={401: {"description": "Não autenticado"}},
)
async def products(
    category: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    items, meta = await get_catalog(db, category, page, limit)
    return {"data": items, "meta": meta}


def intention_response(item: PurchaseIntention) -> dict:
    return {
        "intention_id": item.id,
        "product_id": item.product_id,
        "quantity": item.quantity,
        "total_amount": item.total_amount,
        "currency": item.currency,
        "status": item.status.value,
        "expires_at": item.expires_at,
    }


@router.post(
    "/purchase-intentions",
    status_code=status.HTTP_201_CREATED,
    response_model=Success[IntentionResponse],
    tags=["purchase-intentions"],
    summary="Registrar intenção",
    description="Calcula o valor no backend e vincula a intenção à sessão.",
    responses={404: {"description": "Produto não encontrado"}, 422: {"description": "Sem estoque"}},
)
async def create_intention(
    data: IntentionRequest,
    request: Request,
    response: Response,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    item = await register_intention(db, principal, data)
    response.headers["Location"] = f"{request.url}/{item.id}"
    return {"data": intention_response(item)}


@router.get(
    "/purchase-intentions/{intention_id}",
    response_model=Success[IntentionResponse],
    tags=["purchase-intentions"],
    summary="Consultar intenção",
    description="Consulta uma intenção pertencente ao usuário e à sessão JWT atuais.",
    responses={404: {"description": "Intenção inválida para a sessão"}},
)
async def get_intention(
    intention_id: str,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(PurchaseIntention, intention_id)
    if item is None or item.user_id != principal.user_id or item.session_id != principal.session_id:
        raise ApiError(404, "INTENCAO_INVALIDA", "Intenção inexistente nesta sessão")
    return {"data": intention_response(item)}


@router.post(
    "/purchases",
    status_code=status.HTTP_201_CREATED,
    response_model=Success[PurchaseResponse],
    tags=["purchases"],
    summary="Realizar compra",
    description="Executa uma intenção válida com PIX ou cartão.",
    responses={
        404: {"description": "Intenção inválida"},
        409: {"description": "Já paga"},
        410: {"description": "Expirada"},
        422: {"description": "Limite ou método inválido"},
    },
)
async def create_purchase(
    data: PurchaseRequest,
    response: Response,
    idempotency_key: str = Header(min_length=8, max_length=128, alias="Idempotency-Key"),
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    result = await execute_purchase(db, principal, data, idempotency_key)
    response.headers["Location"] = f"/api/v1/purchases/{result['transaction_id']}"
    return {"data": result}
