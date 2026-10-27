import os
import sys
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    ENV: str = Field(default="local", description="Environment: local, staging, production")
    DATABASE_URL: str = Field(default="", description="PostgreSQL / Supabase connection string")
    ALLOWED_ORIGINS: str = Field(default="http://localhost:3000", description="Comma-separated allowed CORS origins")
    MAX_SEATS_PER_BOOKING: int = Field(default=8, ge=1, le=20, description="Maximum seats per customer booking")
    SEAT_LOCK_MINUTES: int = Field(default=5, ge=1, le=30, description="Hold countdown duration in minutes")
    PAYMENT_HOLD_MINUTES: int = Field(default=10, ge=1, le=60, description="Payment gateway hold window in minutes")

    FIREBASE_PROJECT_ID: str = Field(default="")
    FIREBASE_CLIENT_EMAIL: str = Field(default="")
    FIREBASE_PRIVATE_KEY: str = Field(default="")

    AUTH_DEV_BYPASS: bool = Field(default=False, description="DEV ONLY: bypass Firebase token verification in local")
    ENABLE_DEV_PAYMENT_SIMULATOR: bool = Field(default=False, description="DEV ONLY: mount payment simulator route")

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    def validate_runtime_safety(self) -> None:
        """Enforce strict environment safety invariants."""
        if self.AUTH_DEV_BYPASS and self.ENV != "local":
            raise RuntimeError(
                f"FATAL SECURITY VIOLATION: AUTH_DEV_BYPASS is True, but ENV is '{self.ENV}'. "
                f"Authentication bypass is strictly prohibited outside local development."
            )
        if self.ENABLE_DEV_PAYMENT_SIMULATOR and self.ENV != "local":
            raise RuntimeError(
                f"FATAL SECURITY VIOLATION: ENABLE_DEV_PAYMENT_SIMULATOR is True, but ENV is '{self.ENV}'. "
                f"Dev payment simulator endpoints must never be registered in staging or production."
            )
        if not self.DATABASE_URL and self.ENV != "local":
            raise RuntimeError("FATAL CONFIG ERROR: Missing required environment variable 'DATABASE_URL' in non-local environment.")


def load_settings() -> Settings:
    try:
        cfg = Settings()
        cfg.validate_runtime_safety()
        return cfg
    except Exception as e:
        print(f"\n[FATAL CONFIGURATION ERROR] Failed to load application settings:\n  {e}\n", file=sys.stderr)
        raise


settings = load_settings()
