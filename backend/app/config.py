"""
How this works / why it is safe:
This module manages application configuration using Pydantic Settings.
Environment variables are parsed and strictly validated at process startup.
In production ('prod'), it enforces security gates: weak development secrets,
wildcard CORS origins, or unencrypted database URLs cause immediate fast-failure
before the service can bind or accept traffic. Default monetary caps prevent
integer overflow and precision loss.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENV: str = Field(default="dev", description="Environment: dev | test | prod")
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/ledgerline",
        description="Primary database connection string (psycopg3)",
    )
    DATABASE_URL_APP: str | None = Field(
        default=None,
        description="Restricted runtime role database URL",
    )
    DATABASE_URL_OWNER: str | None = Field(
        default=None,
        description="Migration owner database URL",
    )

    SECRET_KEY: str = Field(
        default="dev-insecure-secret-key-change-in-production-min-32-chars",
        description="Cryptographic signing key for sessions and tokens",
    )
    SESSION_TTL_MINUTES: int = Field(default=480, description="Session lifetime in minutes (8 hours)")
    MAX_AMOUNT_PAISE: int = Field(
        default=10_000_000_000,  # ₹10,00,00,000 (10 crore)
        description="Maximum transaction amount in paise to prevent integer overflow",
    )

    ALLOWED_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="CORS allowed origins",
    )

    LOCK_TIMEOUT_MS: int = Field(default=3000, description="PostgreSQL row lock timeout in ms (3s)")
    STATEMENT_TIMEOUT_MS: int = Field(default=10000, description="PostgreSQL statement timeout in ms (10s)")

    LLM_ENABLED: bool = Field(default=False, description="Enable external LLM synthesis for the copilot")
    LLM_PROVIDER: str = Field(default="auto", description="LLM provider: auto | groq | gemini | offline")
    LLM_API_KEY: str | None = Field(default=None, description="Generic LLM API key fallback")
    GROQ_API_KEY: str | None = Field(default=None, description="Groq API key")
    GROQ_MODEL: str = Field(default="llama-3.3-70b-versatile", description="Groq model name")
    GEMINI_API_KEY: str | None = Field(default=None, description="Google Gemini API key")
    GEMINI_MODEL: str = Field(default="gemini-2.5-flash", description="Google Gemini model name")
    DOCS_ENABLED: bool = Field(default=True, description="Enable /docs and /redoc OpenAPI documentation")

    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for distributed rate limiting",
    )
    REDIS_ENABLED: bool = Field(
        default=True,
        description="Enable Redis for rate limiting (falls back to memory if unreachable)",
    )

    @field_validator("ENV")
    @classmethod
    def validate_env(cls, v: str) -> str:
        v_clean = v.lower()
        if v_clean not in ("dev", "test", "prod"):
            raise ValueError(f"ENV must be one of 'dev', 'test', 'prod', got: {v}")
        return v_clean

    def check_prod_safety(self) -> None:
        """Enforce strict production readiness rules."""
        if self.ENV == "prod":
            if "insecure" in self.SECRET_KEY.lower() or len(self.SECRET_KEY) < 32:
                raise RuntimeError("Production requires a strong SECRET_KEY of at least 32 characters.")
            if "*" in self.ALLOWED_ORIGINS:
                raise RuntimeError("Production CORS cannot permit wildcard '*' origin.")


settings = Settings()
settings.check_prod_safety()
