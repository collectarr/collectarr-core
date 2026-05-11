from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Collectarr"
    environment: str = "development"
    secret_key: str = Field(default="change-me-in-production")
    access_token_expire_minutes: int = 60 * 24 * 7
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:8080"])
    bootstrap_admin_emails: set[str] = Field(default_factory=set)

    database_url: str = "postgresql+asyncpg://collectarr:collectarr@localhost:5432/collectarr"
    redis_url: str = "redis://localhost:6379/0"

    meili_url: str = "http://localhost:7700"
    meili_master_key: str = "collectarr-dev-key"

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_bucket: str = "collectarr-images"
    s3_public_url: str = "http://localhost:9000/collectarr-images"

    comicvine_api_key: str | None = None
    comicvine_base_url: str = "https://comicvine.gamespot.com/api"
    comicvine_timeout_seconds: float = 20.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def require_production_secret(self) -> "Settings":
        if self.environment not in {"development", "test"} and self.secret_key == "change-me-in-production":
            raise ValueError("SECRET_KEY must be set outside development/test")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
