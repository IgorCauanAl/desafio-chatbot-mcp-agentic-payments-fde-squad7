from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]
    backend_base_url: str = "http://localhost:8000"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:1.7b"
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
