from __future__ import annotations

import httpx
from fastapi import Response, status
from fastapi.responses import RedirectResponse

from app.api.deps import DbSession
from app.core.config import get_settings
from app.core.errors import ApiHTTPException
from app.models.base import ExternalProvider
from app.providers.gcd import GCDCoverFallback, GCDCoverImage, GCDProvider
from app.providers.mangadex import MangaDexProvider
from app.services.metadata import MetadataService

_MANGADEX_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


async def gcd_provider_image(
    db: DbSession,
    provider_item_id: str,
    *,
    series: str | None = None,
    issue: str | None = None,
    year: int | None = None,
    variant: str | None = None,
) -> Response:
    cover = await GCDProvider().get_cover_image(
        provider_item_id,
        fallback=GCDCoverFallback(
            series_title=series,
            issue_number=issue,
            start_year=year,
            variant_hint=variant,
        ),
    )
    mirrored_url = await _mirror_gcd_cover_if_enabled(db, provider_item_id, cover)
    if mirrored_url is not None:
        return RedirectResponse(
            mirrored_url,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    if cover.content is not None:
        return Response(
            content=cover.content,
            media_type=cover.content_type or "application/octet-stream",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    return Response(
        content=b"",
        media_type=cover.content_type or "application/octet-stream",
        headers={"Cache-Control": "public, max-age=86400"},
    )


async def mangadex_provider_image(db: DbSession, provider_item_id: str) -> Response:
    provider = MangaDexProvider()
    provider_item = await provider.get_item(provider_item_id)
    normalized = await provider.normalize(provider_item.raw)
    cover_url = normalized.cover_image_url
    if not cover_url:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="mangadex_cover_not_found",
            detail="MangaDex cover image not found",
        )
    mirrored_url = await _mirror_mangadex_cover_if_enabled(db, provider_item_id, cover_url)
    if mirrored_url is not None:
        return RedirectResponse(
            mirrored_url,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    media_type, content = await _download_mangadex_cover(cover_url)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


async def _mirror_gcd_cover_if_enabled(
    db: DbSession,
    provider_item_id: str,
    cover: GCDCoverImage,
) -> str | None:
    service = MetadataService(db)
    if cover.content is not None:
        return await service.mirror_provider_image_bytes(
            cover.content,
            source_url=cover.source_url,
            provider_name=ExternalProvider.gcd,
            provider_item_id=provider_item_id,
        )
    return await service.mirror_provider_image_url(
        cover.redirect_url,
        provider_name=ExternalProvider.gcd,
        provider_item_id=provider_item_id,
    )


async def _mirror_mangadex_cover_if_enabled(
    db: DbSession,
    provider_item_id: str,
    cover_url: str,
) -> str | None:
    return await MetadataService(db).mirror_provider_image_url(
        cover_url,
        provider_name=ExternalProvider.mangadex,
        provider_item_id=provider_item_id,
    )


async def _download_mangadex_cover(url: str) -> tuple[str, bytes]:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=settings.image_download_timeout_seconds,
        ) as client:
            async with client.stream(
                "GET",
                url,
                headers={
                    "User-Agent": settings.mangadex_user_agent,
                    "Referer": "https://mangadex.org/",
                    "Accept": "image/*",
                },
            ) as response:
                response.raise_for_status()
                media_type = response.headers.get("content-type", "application/octet-stream")
                if ";" in media_type:
                    media_type = media_type.split(";", 1)[0].strip()
                media_type = media_type.lower() or "application/octet-stream"
                if media_type not in _MANGADEX_IMAGE_CONTENT_TYPES:
                    raise ApiHTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        code="mangadex_cover_unavailable",
                        detail=f"MangaDex cover request returned unsupported content type: {media_type}",
                    )
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > settings.max_image_bytes:
                        raise ApiHTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            code="mangadex_cover_unavailable",
                            detail="MangaDex cover exceeded the configured size limit",
                        )
                return media_type, bytes(body)
    except httpx.HTTPStatusError as exc:
        raise ApiHTTPException(
            status_code=exc.response.status_code,
            code="mangadex_cover_unavailable",
            detail=f"MangaDex cover request failed: HTTP {exc.response.status_code}",
        ) from exc
    except httpx.RequestError as exc:
        raise ApiHTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="mangadex_cover_unavailable",
            detail=f"MangaDex cover request failed: {exc}",
        ) from exc
