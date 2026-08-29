from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Success[T](BaseModel):
    data: T
    meta: dict[str, int] | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    category: str
    price: Decimal
    currency: str
    stock: int


class IntentionRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=32)
    quantity: int = Field(gt=0, le=100)


class IntentionResponse(BaseModel):
    intention_id: str
    product_id: str
    quantity: int
    total_amount: Decimal
    currency: str
    status: Literal["pendente", "paga"]
    expires_at: datetime


class PurchaseRequest(BaseModel):
    intention_id: str = Field(min_length=1, max_length=32)
    payment_method: str = Field(min_length=1, max_length=20)


class PurchaseResponse(BaseModel):
    status: Literal["aprovado"] = "aprovado"
    transaction_id: str
    intention_id: str
    amount: Decimal
    payment_method: Literal["cartao", "pix"]
    remaining_limit: Decimal
    date: datetime


class HealthResponse(BaseModel):
    status: str
    database: str
