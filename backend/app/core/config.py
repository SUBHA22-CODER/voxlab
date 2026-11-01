from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, overridable via environment or backend/.env."""

    app_name: str = "VoxLab"
    secret_key: str = "dev-secret-change-me-0123456789abcdef"
    # Fernet key for encrypting stored agent credentials. When empty, one is
    # derived deterministically from secret_key (fine for local dev).
    encryption_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./voxlab.db"
    redis_url: str = ""

    # Any OpenAI-compatible provider (OpenAI, Z.ai/GLM, Groq, DeepSeek, Ollama...).
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"

    # Allow registered agent endpoints on localhost/private ranges (needed for
    # the local demo agent; disable in production).
    allow_local_endpoints: bool = True

    access_token_expire_minutes: int = 60 * 24 * 7
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Default per-turn end-to-end latency budget used for scoring when a
    # scenario does not define one.
    default_latency_budget_ms: int = 5000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
