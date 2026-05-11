import os
import socket
import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine.url import make_url
from sqlalchemy import text

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://collectarr:collectarr@localhost:5432/collectarr_test"
)

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402


async def _ensure_test_database(database_url: str) -> None:
    url = make_url(database_url)
    database = url.database
    if not database or not database.endswith("_test"):
        return

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
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")


@pytest_asyncio.fixture(autouse=True)
async def clean_database() -> AsyncIterator[None]:
    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                """
                truncate table
                  owned_item_tags, notes, owned_items, wishlist_items, tags, user_collections,
                  sync_changes, users, releases, variants, editions, external_provider_ids,
                  items, volumes, series, franchises
                restart identity cascade
                """
            )
        )
        await db.commit()
    yield


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
