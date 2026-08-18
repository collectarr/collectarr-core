from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Collectarr"
    environment: str = "development"
    secret_key: str = Field(default="change-me-in-production")
    access_token_expire_minutes: int = 60 * 24 * 7
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:8081",
            "http://127.0.0.1:8081",
            "http://localhost:8082",
            "http://127.0.0.1:8082",
            "http://localhost:8083",
            "http://127.0.0.1:8083",
        ]
    )
    bootstrap_admin_emails: set[str] = Field(default_factory=set)

    database_url: str = "postgresql+asyncpg://collectarr:collectarr@localhost:5432/collectarr"
    redis_url: str | None = "redis://localhost:6379/0"
    redis_timeout_seconds: float = Field(default=0.5, ge=0.05)

    meili_url: str = "http://localhost:7700"
    meili_master_key: str = "collectarr-dev-key"
    meili_timeout_seconds: float = Field(default=5.0, ge=0.1)

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_bucket: str = "collectarr-images"
    s3_public_url: str = "http://localhost:9000/collectarr-images"
    s3_manage_public_read_policy: bool = True
    mirror_provider_images: bool = False
    mirror_provider_images_allow_restricted: bool = False
    image_download_timeout_seconds: float = 20.0
    max_image_bytes: int = 10 * 1024 * 1024
    max_image_pixels: int = 40_000_000
    provider_image_max_long_edge: int = Field(default=1280, ge=64)
    provider_image_quality: int = Field(default=82, ge=1, le=100)
    image_cache_max_bytes: int = Field(default=0, ge=0)
    image_cache_evict_target_bytes: int = Field(default=0, ge=0)
    image_cache_cleanup_batch_size: int = Field(default=250, ge=1)
    worker_index_interval_seconds: int = Field(default=900, ge=5)
    dev_stub_providers: bool = False
    auth_rate_limit_requests: int = Field(default=20, ge=0)
    auth_rate_limit_window_seconds: int = Field(default=60, ge=0)
    admin_provider_rate_limit_requests: int = Field(default=60, ge=0)
    admin_provider_rate_limit_window_seconds: int = Field(default=60, ge=0)
    admin_read_requires_auth_in_public: bool = True
    image_upload_rate_limit_requests: int = Field(default=30, ge=0)
    image_upload_rate_limit_window_seconds: int = Field(default=60, ge=0)
    image_max_per_entity: int = Field(default=20, ge=1)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def require_production_secret(self) -> "Settings":
        if (
            self.environment not in {"development", "test"}
            and self.secret_key == "change-me-in-production"
        ):
            raise ValueError("SECRET_KEY must be set outside development/test")
        if (
            self.image_cache_max_bytes > 0
            and self.image_cache_evict_target_bytes > self.image_cache_max_bytes
        ):
            raise ValueError("IMAGE_CACHE_EVICT_TARGET_BYTES must be <= IMAGE_CACHE_MAX_BYTES")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


def provider_stub_data_enabled() -> bool:
    settings = get_settings()
    return settings.dev_stub_providers or settings.environment in {"development", "test"}
