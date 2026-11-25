
import os
from dataclasses import dataclass


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {
        "1", "true", "yes", "on"
    }


@dataclass
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL", "sqlite:////data/app.db"
    )

    # Gemini primary provider
    llm_api_keys: list[str] = None
    llm_model: str = os.getenv(
        "LLM_MODEL", "gemini/gemini-3.1-flash-lite"
    )

    # Groq backup provider
    groq_api_key: str = os.getenv("GROQ_API_KEY", "").strip()
    groq_model: str = os.getenv(
        "GROQ_MODEL", "groq/openai/gpt-oss-120b"
    )

    allowed_origins: list[str] = None

    enable_failure_simulation: bool = _bool(
        "ENABLE_FAILURE_SIMULATION", True
    )

    default_system_prompt: str = os.getenv(
        "DEFAULT_SYSTEM_PROMPT",
        "You are Lyftr AI, a helpful, accurate, and concise assistant."
    )

    cache_dir: str = os.getenv(
        "LITELLM_CACHE_DIR", "/data/litellm_cache"
    )

    def __post_init__(self):
        self.llm_api_keys = [
            k.strip()
            for k in os.getenv("LLM_API_KEYS", "").split(",")
            if k.strip()
        ]

        self.allowed_origins = [
            x.strip()
            for x in os.getenv(
                "ALLOWED_ORIGINS", "http://localhost:3000"
            ).split(",")
            if x.strip()
        ]


settings = Settings()
