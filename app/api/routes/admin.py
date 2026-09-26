from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAdmin, CurrentAdminReader, DbSession
from app.models.base import ItemKind
from app.schemas.admin import (
    AdminAuditLogResponse,
    AdminCatalogSummaryResponse,
    AdminDeleteResponse,
    AdminDuplicateActionResponse,
    AdminDuplicateCandidateResponse,
    AdminDuplicateIgnoreRequest,
    AdminDuplicateMergeRequest,
    AdminDuplicateQueueSummaryResponse,
    AdminDuplicateReviewEntryResponse,
    AdminDuplicateReviewRequest,
    AdminMetadataCorrectionRequest,
    AdminNormalizedMetadataDriftReportResponse,
    AdminSearchHistoryEntry,
    AdminSearchReindexResponse,
    AdminSearchStatusResponse,
    ImageCachePurgeResponse,
    ImageCacheStatsResponse,
    UserResponse,
    UserUpdateRequest,
)
from app.services.admin import AdminMetadataService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/catalog/summary", response_model=AdminCatalogSummaryResponse)
async def catalog_summary(db: DbSession, _reader: CurrentAdminReader) -> AdminCatalogSummaryResponse:
    return await AdminMetadataService(db).catalog_summary()


@router.get("/catalog/normalized-metadata-drift", response_model=AdminNormalizedMetadataDriftReportResponse)
async def catalog_normalized_metadata_drift(
    db: DbSession,
    _reader: CurrentAdminReader,
    sample_limit: int = Query(default=100, ge=1, le=500),
    scan_limit: int | None = Query(default=None, ge=100, le=100000),
) -> AdminNormalizedMetadataDriftReportResponse:
    return await AdminMetadataService(db).normalized_metadata_drift_report(
        sample_limit=sample_limit, scan_limit=scan_limit
    )


@router.get("/catalog/items", response_model=list[dict[str, Any]])
async def catalog_items(
    db: DbSession,
    _reader: CurrentAdminReader,
    q: str | None = Query(default=None, min_length=1, max_length=255),
    kind: ItemKind | None = None,
    publisher: str | None = Query(default=None, min_length=1, max_length=255),
    imprint: str | None = Query(default=None, min_length=1, max_length=255),
    subtitle: str | None = Query(default=None, min_length=1, max_length=255),
    series_group: str | None = Query(default=None, min_length=1, max_length=255),
    country: str | None = Query(default=None, min_length=1, max_length=64),
    language: str | None = Query(default=None, min_length=1, max_length=32),
    age_rating: str | None = Query(default=None, min_length=1, max_length=64),
    catalog_number: str | None = Query(default=None, min_length=1, max_length=100),
    release_status: str | None = Query(default=None, min_length=1, max_length=64),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[dict[str, Any]]:
    return await AdminMetadataService(db).catalog_items(
        q, kind, limit, publisher=publisher, imprint=imprint, subtitle=subtitle,
        series_group=series_group, country=country, language=language,
        age_rating=age_rating, catalog_number=catalog_number,
        release_status=release_status,
    )


@router.patch("/catalog/items/{kind}/{item_id}", response_model=dict[str, Any])
async def catalog_item_update(
    kind: ItemKind,
    item_id: UUID,
    payload: AdminMetadataCorrectionRequest,
    db: DbSession,
    user: CurrentAdmin,
) -> dict[str, Any]:
    return await AdminMetadataService(db, user).update_catalog_item(item_id, payload, kind)


@router.get("/search/status", response_model=AdminSearchStatusResponse)
async def search_status(db: DbSession, _reader: CurrentAdminReader) -> AdminSearchStatusResponse:
    return await AdminMetadataService(db).search_status()


@router.post("/search/reindex", response_model=AdminSearchReindexResponse)
async def search_reindex(db: DbSession, user: CurrentAdmin) -> AdminSearchReindexResponse:
    return await AdminMetadataService(db, user).reindex_search()


@router.get("/search/history", response_model=list[AdminSearchHistoryEntry])
async def search_history(db: DbSession, _reader: CurrentAdminReader) -> list[AdminSearchHistoryEntry]:
    return AdminMetadataService(db).search_history()


@router.get("/audit/logs", response_model=list[AdminAuditLogResponse])
async def audit_logs(
    db: DbSession,
    _reader: CurrentAdminReader,
    action: str | None = Query(default=None, min_length=1, max_length=100),
    entity_type: str | None = Query(default=None, min_length=1, max_length=64),
    entity_id: UUID | None = None,
    limit: int = Query(default=25, ge=1, le=100),
) -> list[AdminAuditLogResponse]:
    return await AdminMetadataService(db).audit_logs(action, entity_type, entity_id, limit)


@router.get("/duplicates", response_model=list[AdminDuplicateCandidateResponse])
async def duplicate_candidates(
    db: DbSession, _reader: CurrentAdminReader, limit: int = Query(default=10, ge=1, le=50)
) -> list[AdminDuplicateCandidateResponse]:
    return await AdminMetadataService(db).duplicate_candidates(limit)


@router.get("/duplicates/summary", response_model=AdminDuplicateQueueSummaryResponse)
async def duplicate_queue_summary(db: DbSession, _reader: CurrentAdminReader) -> AdminDuplicateQueueSummaryResponse:
    return await AdminMetadataService(db).duplicate_queue_summary()


@router.get("/duplicates/reviews", response_model=list[AdminDuplicateReviewEntryResponse])
async def duplicate_review_history(
    db: DbSession, _reader: CurrentAdminReader, limit: int = Query(default=25, ge=1, le=100)
) -> list[AdminDuplicateReviewEntryResponse]:
    return await AdminMetadataService(db).duplicate_review_history(limit)


@router.post("/duplicates/ignore", response_model=AdminDuplicateActionResponse)
async def ignore_duplicate_candidate(
    payload: AdminDuplicateIgnoreRequest, db: DbSession, user: CurrentAdmin
) -> AdminDuplicateActionResponse:
    return await AdminMetadataService(db, user).ignore_duplicate_candidate(payload)


@router.post("/duplicates/merge", response_model=AdminDuplicateActionResponse)
async def merge_duplicate_candidate(
    payload: AdminDuplicateMergeRequest, db: DbSession, user: CurrentAdmin
) -> AdminDuplicateActionResponse:
    return await AdminMetadataService(db, user).merge_duplicate_candidate(payload)


@router.post("/duplicates/review", response_model=AdminDuplicateActionResponse)
async def review_duplicate_candidate(
    payload: AdminDuplicateReviewRequest, db: DbSession, user: CurrentAdmin
) -> AdminDuplicateActionResponse:
    return await AdminMetadataService(db, user).review_duplicate_candidate(payload)


@router.get("/users", response_model=list[UserResponse])
async def list_users(db: DbSession, _user: CurrentAdmin) -> list[UserResponse]:
    return await AdminMetadataService(db).list_users()


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, db: DbSession, _user: CurrentAdmin) -> UserResponse:
    return await AdminMetadataService(db).get_user(user_id)


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID, payload: UserUpdateRequest, db: DbSession, user: CurrentAdmin
) -> UserResponse:
    return await AdminMetadataService(db, user).update_user(user_id, payload)


@router.get("/image-cache/stats", response_model=ImageCacheStatsResponse)
async def image_cache_stats(db: DbSession, _user: CurrentAdmin) -> ImageCacheStatsResponse:
    return await AdminMetadataService(db).image_cache_stats()


@router.post("/image-cache/purge", response_model=ImageCachePurgeResponse)
async def image_cache_purge(db: DbSession, user: CurrentAdmin) -> ImageCachePurgeResponse:
    return await AdminMetadataService(db, user).purge_image_cache()
