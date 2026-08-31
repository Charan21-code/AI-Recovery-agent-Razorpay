"""
Configuration management using pydantic-settings.
"""

from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    APP_NAME: str = Field(default="RevenueRecoveryIntelligenceEngine")
    APP_ENV: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    PORT: int = Field(default=8000)
    HOST: str = Field(default="0.0.0.0")
    LOG_LEVEL: str = Field(default="INFO")

    # Database
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./backend/data/recovery_engine.db")
    SYNC_DATABASE_URL: str = Field(default="sqlite:///./backend/data/recovery_engine.db")

    # Razorpay Integration (Test Mode)
    RAZORPAY_MODE: str = Field(default="test")
    RAZORPAY_KEY_ID: str = Field(default="rzp_test_placeholder_key")
    RAZORPAY_KEY_SECRET: str = Field(default="placeholder_secret_key")
    RAZORPAY_WEBHOOK_SECRET: str = Field(default="placeholder_webhook_secret")

    # LLM Reasoning Configuration
    LLM_PROVIDER: str = Field(default="mock")
    LLM_API_KEY: Optional[str] = Field(default=None)
    LLM_MODEL: str = Field(default="gemini-2.5-flash")
    LLM_TEMPERATURE: float = Field(default=0.2)

    # Policy Engine Defaults
    MAX_PAYMENT_RETRIES: int = Field(default=3)
    MIN_CONFIDENCE_THRESHOLD: float = Field(default=0.70)
    RETRY_WINDOW_HOURS: int = Field(default=24)
    MIN_RETRY_INTERVAL_MINUTES: int = Field(default=30)
    MAX_AUTOMATED_INTERVENTIONS: int = Field(default=3)
    ALLOW_DISCOUNT: bool = Field(default=False)
    MAX_DISCOUNT_PERCENT: float = Field(default=10.0)
    HUMAN_ESCALATION_AFTER_ATTEMPTS: int = Field(default=3)

    # Simulation
    DEFAULT_SIMULATION_SEED: int = Field(default=42)

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
