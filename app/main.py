from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as api_v1_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.environment)

API_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    version=API_VERSION,
    description="Collectarr metadata and library backend API",
    openapi_tags=[
        {"name": "system", "description": "Health and diagnostics"},
        {"name": "auth", "description": "Authentication and registration"},
        {"name": "metadata", "description": "Catalog metadata and library operations"},
        {"name": "admin", "description": "Catalog and account administration"},
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

app.include_router(api_v1_router)
