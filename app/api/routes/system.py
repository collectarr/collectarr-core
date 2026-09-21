from fastapi import APIRouter

from app.api.deps import DbSession
from app.services.health import HealthService

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(db: DbSession):
    return await HealthService(db).check()
