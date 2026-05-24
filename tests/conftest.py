import asyncio
import os
import socket
from collections.abc import AsyncIterator
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine.url import make_url

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://collectarr:collectarr@localhost:5432/collectarr_test"
)
# Keep provider tests deterministic even when local .env includes live keys.
os.environ["COMICVINE_API_KEY"] = ""
os.environ["TMDB_API_READ_ACCESS_TOKEN"] = ""
os.environ["TMDB_API_KEY"] = ""
os.environ["IGDB_CLIENT_ID"] = ""
os.environ["IGDB_CLIENT_SECRET"] = ""
os.environ["IGDB_ACCESS_TOKEN"] = ""
os.environ["BGG_API_TOKEN"] = ""

from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.core.rate_limit import reset_rate_limits  # noqa: E402
from app.models import Base  # noqa: E402
from app.services.provider_search_state import reset_provider_search_state  # noqa: E402


async def _create_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _ensure_test_database(database_url: str) -> None:
    url = make_url(database_url)
    database = url.database
    if not _is_safe_test_database(url):
        pytest.skip(
            "Refusing to reset PostgreSQL schema because DATABASE_URL is not a local *_test database"
        )

    maintenance_url = url.set(database="postgres")
    try:
        connection = await asyncpg.connect(
            user=maintenance_url.username,
            password=maintenance_url.password,
            database=maintenance_url.database,
            host=maintenance_url.host,
            port=maintenance_url.port or 5432,
        )
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"Cannot connect to PostgreSQL maintenance database: {exc}")

    try:
        exists = await connection.fetchval("select 1 from pg_database where datname = $1", database)
        if not exists:
            quoted_database = '"' + database.replace('"', '""') + '"'
            await connection.execute(f"create database {quoted_database} owner {url.username}")
    except asyncpg.PostgresError as exc:
        pytest.skip(f"Cannot create PostgreSQL test database {database}: {exc}")
    finally:
        await connection.close()

    try:
        target_connection = await asyncpg.connect(
            user=url.username,
            password=url.password,
            database=database,
            host=url.host,
            port=url.port or 5432,
        )
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"Cannot connect to PostgreSQL test database {database}: {exc}")

    try:
        await _reset_public_schema_objects(target_connection)
    except asyncpg.PostgresError as exc:
        pytest.skip(f"Cannot reset PostgreSQL test database {database}: {exc}")
    finally:
        await target_connection.close()


def _is_safe_test_database(url) -> bool:
    database = url.database or ""
    host = url.host or "localhost"
    return (
        os.environ.get("ENVIRONMENT") == "test"
        and database.endswith("_test")
        and host in {"localhost", "127.0.0.1", "::1"}
    )


async def _reset_public_schema_objects(connection: asyncpg.Connection) -> None:
    await connection.execute("drop schema if exists public cascade")
    await connection.execute("create schema public")


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    database_url = os.environ["DATABASE_URL"]
    url = make_url(database_url)
    host = url.host or "localhost"
    port = url.port or 5432
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        if sock.connect_ex((host, port)) != 0:
            pytest.skip(f"PostgreSQL test database is not available at {host}:{port}")
    asyncio.run(_ensure_test_database(database_url))
    asyncio.run(_create_schema())


@pytest_asyncio.fixture(autouse=True)
async def clean_database() -> AsyncIterator[None]:
    reset_rate_limits()
    reset_provider_search_state()
    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                """
                truncate table
                  users, admin_audit_logs, metadata_proposals, image_cache_entries, image_assets,
                  provider_ingest_jobs,
                                    bundle_release_items, bundle_releases,
                  story_arc_items, character_appearances, story_arcs, characters,
                  entity_tags, entity_persons, entity_organizations, tags, persons, organizations,
                                    variants, editions, external_provider_ids,
                  series_relations, items, volumes, series, franchises
                restart identity cascade
                """
            )
        )
        await db.commit()
    yield
    reset_rate_limits()
    reset_provider_search_state()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
