from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./payments.db"
    jwt_secret: str = Field(default="development-secret-change-me-32-chars")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    intention_expiration_minutes: int = 10
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    backend_base_url: str = "http://localhost:8000"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:1.7b"
    mcp_server_cwd: str = "mcp-server/src"
    mcp_server_module: str = "server_mcp.server"
    max_tool_iterations: int = 5

    @field_validator("jwt_secret")
    @classmethod
    def validate_secret(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET deve ter pelo menos 32 caracteres")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
