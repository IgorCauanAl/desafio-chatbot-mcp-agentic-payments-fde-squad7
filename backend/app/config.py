import json
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", str(Path(__file__).resolve().parents[1] / ".env")),
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./payments.db"
    jwt_secret: str = Field(default="development-secret-change-me-32-chars")
    refresh_secret: str = Field(default="development-refresh-secret-change-me-32-chars")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_minutes: int = 60 * 24 * 7
    refresh_cookie_http_only: bool = True
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: str = "lax"
    intention_expiration_minutes: int = 10
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
        ]
    )
    backend_base_url: str = "http://localhost:8000"
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_api_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model: str = "gemini-2.5-flash"
    groq_api_key: str = ""
    groq_api_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"
    mcp_server_cwd: str = "mcp-server/src"
    mcp_server_module: str = "server_mcp.server"
    max_tool_iterations: int = 5

    @field_validator("jwt_secret", "refresh_secret")
    @classmethod
    def validate_secret(cls, value: str, info) -> str:
        if len(value) < 32:
            field_name = info.field_name.upper()
            raise ValueError(f"{field_name} deve ter pelo menos 32 caracteres")
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except json.JSONDecodeError:
                pass
            return [item.strip() for item in stripped.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
