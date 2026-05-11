from typing import Any

import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.search.client import SearchClient
from app.storage.client import ObjectStorage


class HealthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    async def check(self) -> dict[str, Any]:
        checks = {
            "postgres": await self._postgres(),
            "redis": await self._redis(),
            "meilisearch": await self._meilisearch(),
            "minio": await self._minio(),
        }
        status = "ok" if all(check["ok"] for check in checks.values()) else "degraded"
        return {"status": status, "checks": checks}

    async def _postgres(self) -> dict[str, Any]:
        try:
            await self.db.execute(text("select 1"))
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def _redis(self) -> dict[str, Any]:
        client = redis.from_url(self.settings.redis_url)
        try:
            await client.ping()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        finally:
            await client.aclose()

    async def _meilisearch(self) -> dict[str, Any]:
        try:
            SearchClient().client.health()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def _minio(self) -> dict[str, Any]:
        try:
            ObjectStorage().client.list_buckets()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

