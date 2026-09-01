import time
from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import get_settings
from app.database import Base, SessionFactory, engine
from app.errors import install_error_handlers
from app.models import Product, User
from app.routes import router
from app.security import hash_password

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(ensure_ascii=False),
    ]
)
log = structlog.get_logger()


async def seed() -> None:
    async with SessionFactory() as db:
        if await db.scalar(select(User.id).limit(1)) is None:
            db.add_all(
                [
                    User(
                        id="usr_alice",
                        email="alice@example.com",
                        password_hash=hash_password("alice123"),
                        spending_limit=1000,
                    ),
                    User(
                        id="usr_bob",
                        email="bob@example.com",
                        password_hash=hash_password("bob12345"),
                        spending_limit=100,
                    ),
                ]
            )
        if await db.scalar(select(Product.id).limit(1)) is None:
            db.add_all(
                [
                    Product(
                        id="prod_001",
                        name="Teclado Mecânico",
                        category="perifericos",
                        price=349.90,
                        currency="BRL",
                        stock=8,
                    ),
                    Product(
                        id="prod_002",
                        name="Mouse Ergonômico",
                        category="perifericos",
                        price=189.90,
                        currency="BRL",
                        stock=15,
                    ),
                    Product(
                        id="prod_003",
                        name="Fone Bluetooth",
                        category="audio",
                        price=249.90,
                        currency="BRL",
                        stock=12,
                    ),
                ]
            )
        await db.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await seed()
    yield
    await engine.dispose()


app = FastAPI(title="Agentic Payments Backend", version="0.1.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def audit_requests(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    log.info(
        "request",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    return response


@app.get(
    "/health",
    tags=["health"],
    summary="Liveness",
    description="Confirma que o processo está ativo.",
)
async def health():
    return {"status": "healthy"}


@app.get(
    "/api/v1/health", tags=["health"], summary="Readiness", description="Verifica o banco de dados."
)
async def readiness():
    async with SessionFactory() as db:
        await db.execute(select(1))
    return {"status": "healthy", "database": "healthy"}


install_error_handlers(app)
app.include_router(router)
