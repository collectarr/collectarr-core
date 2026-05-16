from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as redis

from app.core.config import get_settings


@asynccontextmanager
async def redis_client() -> AsyncIterator[redis.Redis | None]:
    settings = get_settings()
    if not settings.redis_url:
        yield None
        return

    client = redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=settings.redis_timeout_seconds,
        socket_timeout=settings.redis_timeout_seconds,
    )
    try:
        yield client
    finally:
        await client.aclose()
