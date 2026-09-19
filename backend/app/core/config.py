"""
Centralized application configuration.
All values are overridable via environment variables / .env file.
"""
from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "Merchant Growth AI"
    ENV: str = "development"
    DEBUG: bool = True
    JWT_SECRET: str = "change-this-in-production"
    ACCESS_TOKEN_MINUTES: int = 30
    REFRESH_TOKEN_DAYS: int = 30
    CART_RESERVATION_MINUTES: int = 20

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/merchant_growth"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    SESSION_TTL_SECONDS: int = 60 * 60 * 6  # 6 hours of conversational memory

    # LLM providers (used by the Intent Engine's LLM-backed parser)
    LLM_PROVIDER: str = "rule_based"  # "gemini" | "groq" | "openai" | "rule_based"
    GEMINI_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Sarvam voice
    SARVAM_API_KEY: str | None = None
    SARVAM_STT_LANGUAGE: str = "hi-IN"
    PAYTM_MID: str | None = None
    PAYTM_MERCHANT_KEY: str | None = None
    PAYTM_PRODUCTION: bool = False

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value: object) -> bool:
        if isinstance(value, str) and value.lower() in {"release", "production", "prod"}:
            return False
        return bool(value) if not isinstance(value, str) else value.lower() in {"1", "true", "yes", "on"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
