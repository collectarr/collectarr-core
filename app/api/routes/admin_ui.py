from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["admin"])

_ADMIN_STATIC_DIR = Path(__file__).resolve().parents[2] / "static" / "admin"
_ADMIN_HTML_PATH = _ADMIN_STATIC_DIR / "admin.html"
_ADMIN_UI_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data: http: https:; "
    "connect-src 'self'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


@router.get("/admin/ui")
async def admin_ui() -> FileResponse:
    return FileResponse(
        _ADMIN_HTML_PATH,
        media_type="text/html",
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": _ADMIN_UI_CSP,
            "X-Content-Type-Options": "nosniff",
        },
    )
