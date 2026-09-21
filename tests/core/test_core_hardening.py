from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.core.rate_limit import (
    auth_rate_limit,
    cleanup_rate_limits,
    rate_limit_bucket_count,
)


@pytest.mark.asyncio
async def test_auth_errors_return_specific_codes(client):
    failed_login = await client.post(
        "/auth/login",
        json={"email": "missing@example.com", "password": "password123"},
    )

    assert failed_login.status_code == 401
    assert failed_login.json()["code"] == "invalid_credentials"

    registered = await client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "password123", "display_name": "User"},
    )
    assert registered.status_code == 201

    duplicate = await client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "password123", "display_name": "User"},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "email_already_registered"


@pytest.mark.asyncio
async def test_auth_rate_limit_returns_retry_after(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_rate_limit_requests", 1)
    monkeypatch.setattr(settings, "auth_rate_limit_window_seconds", 60)

    first = await client.post(
        "/auth/login",
        json={"email": "missing@example.com", "password": "password123"},
    )
    limited = await client.post(
        "/auth/login",
        json={"email": "missing@example.com", "password": "password123"},
    )

    assert first.status_code == 401
    assert limited.status_code == 429
    assert limited.json()["code"] == "auth_rate_limited"
    assert int(limited.headers["Retry-After"]) > 0


def test_production_requires_explicit_secret(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="SECRET_KEY must be set outside development/test"):
        get_settings()

    monkeypatch.setenv("SECRET_KEY", "prod-secret-value")
    get_settings.cache_clear()
    settings = get_settings()

    assert settings.secret_key == "prod-secret-value"

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_metadata_errors_return_specific_codes(client):
    unknown_barcode = await client.get("/barcode/0000000000000", params={"kind": "comic"})
    unknown_type = await client.get(f"/api/v1/metadata/not-real/{uuid4()}")

    assert unknown_barcode.status_code == 404
    assert unknown_barcode.json()["code"] == "barcode_not_found"
    assert unknown_type.status_code == 404
    assert unknown_type.json()["code"] == "media_type_not_found"


@pytest.mark.asyncio
async def test_rate_limit_cleanup_removes_expired_client_buckets(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_rate_limit_requests", 100)
    monkeypatch.setattr(settings, "auth_rate_limit_window_seconds", 1)
    now = 0.0
    monkeypatch.setattr("app.core.rate_limit.monotonic", lambda: now)

    for index in range(3):
        await auth_rate_limit(
            SimpleNamespace(headers={"x-forwarded-for": f"10.0.0.{index}"}, client=None)
        )

    assert rate_limit_bucket_count() == 3

    now = 2.0
    cleanup_rate_limits()

    assert rate_limit_bucket_count() == 0
