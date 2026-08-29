from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product, Purchase, PurchaseIntention, User


async def find_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email.lower()))


async def find_user(db: AsyncSession, user_id: str) -> User | None:
    return await db.get(User, user_id)


async def list_products(
    db: AsyncSession, category: str | None, page: int, limit: int
) -> tuple[list[Product], int]:
    safe_limit = min(limit, 100)
    filters = [Product.category == category] if category else []
    total = await db.scalar(select(func.count()).select_from(Product).where(*filters)) or 0
    result = await db.scalars(
        select(Product).where(*filters).offset((page - 1) * safe_limit).limit(safe_limit)
    )
    return list(result), total


async def find_product(db: AsyncSession, product_id: str) -> Product | None:
    return await db.get(Product, product_id)


async def find_intention_for_update(
    db: AsyncSession, intention_id: str
) -> PurchaseIntention | None:
    return await db.scalar(
        select(PurchaseIntention).where(PurchaseIntention.id == intention_id).with_for_update()
    )


async def find_purchase_by_key(db: AsyncSession, user_id: str, key: str) -> Purchase | None:
    return await db.scalar(
        select(Purchase).where(Purchase.user_id == user_id, Purchase.idempotency_key == key)
    )
