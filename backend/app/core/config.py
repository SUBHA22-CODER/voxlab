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
    # Audio artifact retention in days; 0 keeps artifacts forever. The sweep
    # deletes run-scoped directories whose last modification is older than
    # the cutoff (privacy: recordings must not linger indefinitely).
    audio_retention_days: int = 30
    # Second engine (Vosk): explicit model dir or opt-in auto-download of the
    # ~40 MB small English model. Default off — no surprise downloads.
    speech_vosk_model_dir: str = ""
    speech_vosk_auto_download: bool = False

    # Third engine (Wav2Vec2-base): CTC acoustic model from Hugging Face.
    # Default model: facebook/wav2vec2-base-960h (~380 MB).
    speech_wav2vec2_model: str = "facebook/wav2vec2-base-960h"
    speech_wav2vec2_revision: str = "main"
    speech_wav2vec2_device: str = "cpu"
    speech_wav2vec2_model_dir: str = ""
    speech_wav2vec2_auto_download: bool = False
    speech_wav2vec2_word_timestamps: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
