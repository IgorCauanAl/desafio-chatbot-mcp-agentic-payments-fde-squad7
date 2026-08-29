from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.config import get_settings
from app.errors import ApiError

password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    user_id: str
    session_id: str


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    return password_hash.verify(password, encoded)


def create_access_token(user_id: str) -> tuple[str, int]:
    settings = get_settings()
    expires = datetime.now(UTC) + timedelta(minutes=settings.access_token_minutes)
    payload = {"sub": user_id, "sid": str(uuid4()), "iat": datetime.now(UTC), "exp": expires}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, settings.access_token_minutes * 60


async def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> Principal:
    if credentials is None:
        raise ApiError(401, "NAO_AUTENTICADO", "Token de acesso ausente")
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "sid", "exp"]},
        )
    except InvalidTokenError as exc:
        raise ApiError(401, "TOKEN_INVALIDO", "Token de acesso inválido ou expirado") from exc
    return Principal(user_id=str(payload["sub"]), session_id=str(payload["sid"]))
