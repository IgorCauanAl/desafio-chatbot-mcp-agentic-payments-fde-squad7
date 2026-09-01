from datetime import UTC, datetime, timedelta
from math import ceil
from uuid import uuid4

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import ApiError
from app.models import IntentionStatus, PaymentMethod, Purchase, PurchaseIntention
from app.repositories import (
    find_intention_for_update,
    find_product,
    find_purchase_by_key,
    find_user,
    find_user_by_email,
    list_products,
)
from app.schemas import IntentionRequest, PurchaseRequest
from app.security import (
    Principal,
    create_access_token,
    create_refresh_token,
    validate_refresh_token,
    verify_password,
)


async def authenticate(db: AsyncSession, email: str, password: str) -> tuple[str, str, int]:
    user = await find_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise ApiError(401, "CREDENCIAIS_INVALIDAS", "Senha ou email incorreto")
    session_id = str(uuid4())
    access_token, expires_in = create_access_token(user.id, session_id)
    refresh_token = create_refresh_token(user.id, session_id)
    return access_token, refresh_token, expires_in


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> tuple[str, str, int]:
    user_id = validate_refresh_token(refresh_token)
    user = await find_user(db, user_id)
    if user is None:
        raise ApiError(401, "REFRESH_TOKEN_INVALIDO", "Refresh token inválido ou expirado")

    settings = get_settings()
    payload = jwt.decode(
        refresh_token,
        settings.refresh_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "sid", "exp"]},
    )
    session_id = str(payload.get("sid") or uuid4())
    access_token, expires_in = create_access_token(user.id, session_id)
    new_refresh_token = create_refresh_token(user.id, session_id)
    return access_token, new_refresh_token, expires_in


async def get_catalog(db: AsyncSession, category: str | None, page: int, limit: int):
    products, total = await list_products(db, category, page, limit)
    return products, {
        "page": page,
        "limit": min(limit, 100),
        "total": total,
        "total_pages": ceil(total / min(limit, 100)) if total else 0,
    }


async def register_intention(
    db: AsyncSession, principal: Principal, data: IntentionRequest
) -> PurchaseIntention:
    product = await find_product(db, data.product_id)
    if product is None:
        raise ApiError(404, "PRODUTO_NAO_ENCONTRADO", "Produto não encontrado")
    if product.stock < data.quantity:
        raise ApiError(422, "ESTOQUE_INSUFICIENTE", "Quantidade indisponível em estoque")
    now = datetime.now(UTC)
    intention = PurchaseIntention(
        id=f"int_{uuid4().hex[:12]}",
        user_id=principal.user_id,
        session_id=principal.session_id,
        product_id=product.id,
        quantity=data.quantity,
        total_amount=product.price * data.quantity,
        currency=product.currency,
        status=IntentionStatus.PENDING,
        created_at=now,
        expires_at=now + timedelta(minutes=get_settings().intention_expiration_minutes),
    )
    db.add(intention)
    await db.commit()
    await db.refresh(intention)
    return intention


def _purchase_payload(purchase: Purchase) -> dict:
    return {
        "status": "aprovado",
        "transaction_id": purchase.id,
        "intention_id": purchase.intention_id,
        "amount": purchase.amount,
        "payment_method": purchase.payment_method.value,
        "remaining_limit": purchase.remaining_limit,
        "date": purchase.created_at,
    }


async def execute_purchase(
    db: AsyncSession, principal: Principal, data: PurchaseRequest, idempotency_key: str
) -> dict:
    if data.payment_method not in {method.value for method in PaymentMethod}:
        raise ApiError(422, "METODO_INVALIDO", "Use um método de pagamento: cartao ou pix")
    previous = await find_purchase_by_key(db, principal.user_id, idempotency_key)
    if previous:
        if previous.intention_id != data.intention_id:
            raise ApiError(409, "CHAVE_IDEMPOTENCIA_REUTILIZADA", "Chave usada em outra compra")
        return _purchase_payload(previous)

    intention = await find_intention_for_update(db, data.intention_id)
    if (
        intention is None
        or intention.user_id != principal.user_id
        or intention.session_id != principal.session_id
    ):
        raise ApiError(404, "INTENCAO_INVALIDA", "Intenção inexistente nesta sessão")
    if intention.status == IntentionStatus.PAID:
        raise ApiError(409, "INTENCAO_JA_PAGA", "Esta intenção já foi utilizada")
    expires_at = intention.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        raise ApiError(410, "INTENCAO_EXPIRADA", "A intenção de compra expirou")

    user = await find_user(db, principal.user_id)
    product = await find_product(db, intention.product_id)
    if user is None or product is None:
        raise ApiError(404, "INTENCAO_INVALIDA", "Dados da intenção não estão disponíveis")
    if intention.total_amount > user.spending_limit:
        raise ApiError(422, "LIMITE_EXCEDIDO", "A compra excede o limite disponível")
    if product.stock < intention.quantity:
        raise ApiError(422, "ESTOQUE_INSUFICIENTE", "Quantidade indisponível em estoque")

    remaining = user.spending_limit - intention.total_amount
    purchase = Purchase(
        id=f"tx_{uuid4().hex[:12]}",
        intention_id=intention.id,
        user_id=user.id,
        amount=intention.total_amount,
        payment_method=PaymentMethod(data.payment_method),
        remaining_limit=remaining,
        idempotency_key=idempotency_key,
        created_at=datetime.now(UTC),
    )
    user.spending_limit = remaining
    product.stock -= intention.quantity
    intention.status = IntentionStatus.PAID
    db.add(purchase)
    await db.commit()
    return _purchase_payload(purchase)
