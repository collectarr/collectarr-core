from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Collectarr"
    environment: str = "development"
    secret_key: str = Field(default="change-me-in-production")
    access_token_expire_minutes: int = 60 * 24 * 7
    cors_origins: list[str] = Field(default_factory=list)
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
    worker_provider_ingest_interval_seconds: int = Field(default=30, ge=5)
    worker_provider_ingest_batch_size: int = Field(default=5, ge=1, le=100)
    worker_provider_ingest_stale_after_seconds: int = Field(default=1800, ge=60)
    worker_catalog_refresh_interval_seconds: int = Field(default=3600, ge=60)
    worker_catalog_refresh_stale_days: int = Field(default=30, ge=1)
    worker_catalog_refresh_batch_size: int = Field(default=10, ge=1, le=100)
    provider_ingest_retry_attempts: int = Field(default=1, ge=0, le=5)
    provider_search_rate_limit_requests: int = Field(default=30, ge=0)
    provider_search_rate_limit_window_seconds: int = Field(default=60, ge=0)
    provider_search_cache_ttl_seconds: int = Field(default=6 * 60 * 60, ge=0)
    provider_search_cache_max_entries: int = Field(default=2048, ge=0)
    provider_preview_cache_ttl_seconds: int = Field(default=15 * 60, ge=0)
    provider_preview_cache_max_entries: int = Field(default=256, ge=0)
    provider_search_retry_attempts: int = Field(default=1, ge=0, le=3)
    provider_search_retry_base_delay_seconds: float = Field(default=0.35, ge=0)
    provider_search_backoff_seconds: int = Field(default=5 * 60, ge=0)
    provider_search_comicvine_fallback_enabled: bool = True
    auth_rate_limit_requests: int = Field(default=20, ge=0)
    auth_rate_limit_window_seconds: int = Field(default=60, ge=0)
    admin_provider_rate_limit_requests: int = Field(default=60, ge=0)
    admin_provider_rate_limit_window_seconds: int = Field(default=60, ge=0)
    image_upload_rate_limit_requests: int = Field(default=30, ge=0)
    image_upload_rate_limit_window_seconds: int = Field(default=60, ge=0)
    image_max_per_entity: int = Field(default=20, ge=1)

    comicvine_api_key: str | None = None
    comicvine_base_url: str = "https://comicvine.gamespot.com/api"
    comicvine_timeout_seconds: float = 20.0
    comicvine_retry_attempts: int = 2
    comicvine_search_limit: int = 20
    comicvine_search_variant_detail_limit: int = Field(default=5, ge=0, le=20)
    comicvine_user_agent: str = "Collectarr/0.1 (+https://github.com/saitatter/collectarr)"

    gcd_base_url: str = "https://www.comics.org/api"
    gcd_timeout_seconds: float = 20.0
    gcd_search_limit: int = 20
    gcd_series_search_issue_span: int = Field(default=4, ge=1, le=25)
    gcd_user_agent: str = "Collectarr/0.1 (+https://github.com/saitatter/collectarr)"

    openlibrary_base_url: str = "https://openlibrary.org"
    openlibrary_covers_url: str = "https://covers.openlibrary.org"
    openlibrary_timeout_seconds: float = 20.0
    openlibrary_search_limit: int = 20
    openlibrary_user_agent: str = "Collectarr/0.1 (+https://github.com/saitatter/collectarr)"

    bgg_api_token: str | None = None
    bgg_base_url: str = "https://boardgamegeek.com/xmlapi2"
    bgg_timeout_seconds: float = 20.0
    bgg_retry_attempts: int = 2
    bgg_search_limit: int = 20
    bgg_user_agent: str = "Collectarr/0.1 (+https://github.com/saitatter/collectarr)"

    anilist_api_url: str = "https://graphql.anilist.co"
    anilist_timeout_seconds: float = 20.0
    anilist_search_limit: int = 20
    anilist_user_agent: str = "Collectarr/0.1 (+https://github.com/saitatter/collectarr)"

    musicbrainz_base_url: str = "https://musicbrainz.org/ws/2"
    cover_art_archive_base_url: str = "https://coverartarchive.org"
    musicbrainz_timeout_seconds: float = 20.0
    musicbrainz_search_limit: int = 20
    musicbrainz_user_agent: str = "Collectarr/0.1 (+https://github.com/saitatter/collectarr)"

    igdb_client_id: str | None = None
    igdb_client_secret: str | None = None
    igdb_access_token: str | None = None
    igdb_token_url: str = "https://id.twitch.tv/oauth2/token"
    igdb_base_url: str = "https://api.igdb.com/v4"
    igdb_timeout_seconds: float = 20.0
    igdb_search_limit: int = 20
    igdb_user_agent: str = "Collectarr/0.1 (+https://github.com/saitatter/collectarr)"

    tmdb_api_read_access_token: str | None = None
    tmdb_api_key: str | None = None
    tmdb_base_url: str = "https://api.themoviedb.org/3"
    tmdb_image_base_url: str = "https://image.tmdb.org/t/p"
    tmdb_timeout_seconds: float = 20.0
    tmdb_search_limit: int = 20
    tmdb_language: str = "en-US"
    tmdb_user_agent: str = "Collectarr/0.1 (+https://github.com/saitatter/collectarr)"

    hardcover_api_key: str | None = None
    hardcover_graphql_url: str = "https://api.hardcover.app/v1/graphql"
    hardcover_timeout_seconds: float = 30.0
    hardcover_search_limit: int = 20
    hardcover_user_agent: str = "Collectarr/0.1 (+https://github.com/saitatter/collectarr)"

    mangadex_base_url: str = "https://api.mangadex.org"
    mangadex_timeout_seconds: float = 20.0
    mangadex_search_limit: int = 20
    mangadex_feed_limit: int = 500
    mangadex_user_agent: str = "Collectarr/0.1 (+https://github.com/saitatter/collectarr)"

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
