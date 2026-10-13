"""Application configuration settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """CatalogPilot environment and configuration settings."""

    ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000

    # Database (ADR-0001)
    DATABASE_URL: str = "sqlite:///./catalogpilot.db"

    # Store Adapter (ADR-0002, ADR-0009)
    STORE_MODE: str = "mock"
    WOOCOMMERCE_URL: str = "http://localhost:8080"
    WOOCOMMERCE_CONSUMER_KEY: str = "ck_test_sample_key"
    WOOCOMMERCE_CONSUMER_SECRET: str = "cs_test_sample_secret"

    # LLM Configuration (ADR-0005)
    LLM_PROVIDER: str = "gemini"
    LLM_MODE: str = "replay"  # "live" | "replay"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    LLM_FIXTURES_PATH: str = "app/fixtures/llm_cache.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
