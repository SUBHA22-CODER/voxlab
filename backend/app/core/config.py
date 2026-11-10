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

    # --- Speech engine (VoxLab 2.0) -----------------------------------------
    # Default faster-whisper model key (tiny/base/small/medium/large-v3/...en).
    speech_whisper_model: str = "base"
    speech_device: str = "cpu"  # "cpu" | "cuda" (cuda only when explicitly set)
    speech_compute_type: str = "int8"
    speech_timeout_seconds: float = 120.0
    speech_max_upload_mb: int = 25
    speech_max_duration_seconds: float = 600.0
    # Where uploaded seed audio and candidate WAV artifacts are stored.
    audio_storage_dir: str = "./data/audio"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
