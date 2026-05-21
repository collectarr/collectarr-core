import asyncio
import base64
import logging
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.errors import ApiHTTPException
from app.core.rate_limit import image_upload_rate_limit
from app.models.canonical import ImageAsset, ImageCacheEntry
from app.storage.client import ObjectStorage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/images", tags=["images"])

_IMAGE_TYPES = {"front_cover", "back_cover", "auxiliary"}


# ---------------------------------------------------------------------------
# Single image download — returns raw bytes from MinIO
# ---------------------------------------------------------------------------


@router.get(
    "/download",
    responses={
        200: {"content": {"image/webp": {}}, "description": "Processed image bytes"},
        404: {"description": "Object not found"},
    },
)
async def download_image(
    user: CurrentUser,
    object_key: str = Query(min_length=1, max_length=512),
) -> Response:
    try:
        body, content_type = await asyncio.to_thread(
            ObjectStorage.shared().get_object, object_key
        )
    except Exception:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="image_not_found",
            detail="Image object not found",
        )
    return Response(
        content=body,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


# ---------------------------------------------------------------------------
# Batch download — returns map of object_key → base64 bytes
# ---------------------------------------------------------------------------


@router.post("/batch-download")
async def batch_download_images(
    user: CurrentUser,
    object_keys: list[str] = Body(min_length=1, max_length=50),
) -> dict[str, str | None]:
    storage = ObjectStorage.shared()
    result: dict[str, str | None] = {}
    seen: set[str] = set()
    for key in object_keys:
        if key in seen:
            continue
        seen.add(key)
        try:
            body, _ = await asyncio.to_thread(storage.get_object, key)
            result[key] = base64.b64encode(body).decode("ascii")
        except Exception:
            result[key] = None
    return result


# ---------------------------------------------------------------------------
# Multi-image CRUD — ImageAsset per entity
# ---------------------------------------------------------------------------


class _ImageAssetOut(dict):
    """Lightweight dict subclass so FastAPI serialises it directly."""


def _asset_dict(asset: ImageAsset, storage: ObjectStorage) -> dict:
    return {
        "id": str(asset.id),
        "entity_type": asset.entity_type,
        "entity_id": str(asset.entity_id),
        "image_type": asset.image_type,
        "storage_key": asset.storage_key,
        "public_url": storage.public_object_url(asset.storage_key),
        "thumbnail_storage_key": asset.thumbnail_storage_key,
        "source_url": asset.source_url,
        "provider": asset.provider,
        "attribution": asset.attribution,
        "width": asset.width,
        "height": asset.height,
        "phash": asset.phash,
        "is_primary": asset.is_primary,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    }


@router.get("/entity/{entity_type}/{entity_id}")
async def list_entity_images(
    db: DbSession,
    user: CurrentUser,
    entity_type: str = Path(min_length=1, max_length=64),
    entity_id: UUID = Path(),
) -> list[dict]:
    result = await db.scalars(
        select(ImageAsset)
        .where(
            ImageAsset.entity_type == entity_type,
            ImageAsset.entity_id == entity_id,
        )
        .order_by(ImageAsset.is_primary.desc(), ImageAsset.created_at)
    )
    storage = ObjectStorage.shared()
    return [_asset_dict(asset, storage) for asset in result]


@router.post(
    "/entity/{entity_type}/{entity_id}",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(image_upload_rate_limit)],
)
async def add_entity_image(
    db: DbSession,
    user: CurrentUser,
    entity_type: str = Path(min_length=1, max_length=64),
    entity_id: UUID = Path(),
    image_type: str = Body(default="front_cover"),
    image_data_base64: str = Body(min_length=1),
    source_url: str | None = Body(default=None),
    provider: str | None = Body(default=None),
    attribution: str | None = Body(default=None),
    is_primary: bool = Body(default=False),
) -> dict:
    if image_type not in _IMAGE_TYPES:
        raise ApiHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_image_type",
            detail=f"image_type must be one of {sorted(_IMAGE_TYPES)}",
        )

    try:
        image_bytes = base64.b64decode(image_data_base64)
    except Exception:
        raise ApiHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_base64",
            detail="image_data_base64 is not valid base64",
        )

    # Reject uploads exceeding max_image_bytes
    settings = get_settings()
    if len(image_bytes) > settings.max_image_bytes:
        raise ApiHTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            code="image_too_large",
            detail=f"Image exceeds maximum allowed size of {settings.max_image_bytes} bytes",
        )

    # Enforce per-entity image count limit
    existing_count = await db.scalar(
        select(func.count()).where(
            ImageAsset.entity_type == entity_type,
            ImageAsset.entity_id == entity_id,
        )
    )
    if (existing_count or 0) >= settings.image_max_per_entity:
        raise ApiHTTPException(
            status_code=status.HTTP_409_CONFLICT,
            code="entity_image_limit_reached",
            detail=f"Entity already has {existing_count} images (max {settings.image_max_per_entity})",
        )

    from app.storage.images import ImageMirror

    mirror = ImageMirror()
    provider_value = provider or "user"
    item_id_str = str(entity_id)
    mirrored = await mirror.mirror_cover_bytes_best_effort(
        image_bytes,
        source_url=source_url or f"upload://{entity_type}/{item_id_str}/{image_type}",
        provider=provider_value,
        provider_item_id=item_id_str,
    )
    if mirrored is None:
        raise ApiHTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="image_processing_failed",
            detail="Image could not be processed",
        )

    # Content-hash dedup: check if identical image already attached to this entity
    existing = await db.scalar(
        select(ImageAsset).where(
            ImageAsset.entity_type == entity_type,
            ImageAsset.entity_id == entity_id,
            ImageAsset.storage_key == mirrored.key,
        )
    )
    if existing is not None:
        storage = ObjectStorage.shared()
        return _asset_dict(existing, storage)

    # If is_primary, clear other primaries of same type
    if is_primary:
        result = await db.scalars(
            select(ImageAsset).where(
                ImageAsset.entity_type == entity_type,
                ImageAsset.entity_id == entity_id,
                ImageAsset.image_type == image_type,
                ImageAsset.is_primary.is_(True),
            )
        )
        for old in result:
            old.is_primary = False

    asset = ImageAsset(
        entity_type=entity_type,
        entity_id=entity_id,
        image_type=image_type,
        storage_key=mirrored.key,
        source_url=source_url,
        provider=provider_value,
        attribution=attribution,
        width=mirrored.width,
        height=mirrored.height,
        is_primary=is_primary,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    storage = ObjectStorage.shared()
    return _asset_dict(asset, storage)


@router.delete(
    "/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_image(
    db: DbSession,
    user: CurrentUser,
    image_id: UUID,
) -> None:
    asset = await db.get(ImageAsset, image_id)
    if asset is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="image_not_found",
            detail="Image asset not found",
        )
    # Don't delete the S3 object — it may be referenced by ImageCacheEntry or
    # another entity.  Orphan cleanup can be done separately.
    await db.delete(asset)
    await db.commit()


@router.patch("/{image_id}/primary")
async def set_image_primary(
    db: DbSession,
    user: CurrentUser,
    image_id: UUID,
) -> dict:
    asset = await db.get(ImageAsset, image_id)
    if asset is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="image_not_found",
            detail="Image asset not found",
        )
    # Clear existing primary of same type for same entity
    result = await db.scalars(
        select(ImageAsset).where(
            ImageAsset.entity_type == asset.entity_type,
            ImageAsset.entity_id == asset.entity_id,
            ImageAsset.image_type == asset.image_type,
            ImageAsset.is_primary.is_(True),
            ImageAsset.id != asset.id,
        )
    )
    for old in result:
        old.is_primary = False
    asset.is_primary = True
    await db.commit()
    storage = ObjectStorage.shared()
    return _asset_dict(asset, storage)
