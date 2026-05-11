from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import DbSession
from app.api.routes import admin, auth, collection, metadata, sync
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.services.health import HealthService

settings = get_settings()
configure_logging(settings.environment)

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)

app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(metadata.router)
app.include_router(collection.router)
app.include_router(sync.router)


@app.get("/health", tags=["system"])
async def health(db: DbSession):
    return await HealthService(db).check()
