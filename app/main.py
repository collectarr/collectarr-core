from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import DbSession
from app.api.routes import admin, admin_ui, auth, images, metadata, tracking
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.providers.hardcover import HardcoverProvider
from app.services.health import HealthService

settings = get_settings()
configure_logging(settings.environment)

API_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        yield
    finally:
        await HardcoverProvider().aclose()

app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    version=API_VERSION,
    description="Collectarr metadata and library backend API",
    openapi_tags=[
        {"name": "system", "description": "Health and diagnostics"},
        {"name": "auth", "description": "Authentication and registration"},
        {"name": "metadata", "description": "Catalog metadata and library operations"},
        {"name": "tracking", "description": "User tracking entries and tracking analytics"},
        {"name": "admin", "description": "Administration and provider management"},
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|172\.\d+\.\d+\.\d+):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)

app.include_router(admin.router)
app.include_router(admin_ui.router)
app.include_router(auth.router)
app.include_router(images.router)
app.include_router(tracking.router)
app.include_router(metadata.router)


@app.get("/health", tags=["system"])
async def health(db: DbSession):
    return await HealthService(db).check()
