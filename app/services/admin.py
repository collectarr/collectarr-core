from collections import deque
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from enum import Enum as PythonEnum
import logging
import re
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalog.physical_formats import (
    PhysicalFormatConfig,
    is_video_item_kind,
    physical_format_for_id,
)
from app.core.config import get_settings
from app.core.errors import ApiHTTPException
from app.catalog.media_types import media_type_for_kind
from app.models.base import ExternalProvider, ItemKind, SeriesRelationType
from app.models.canonical import (
    AdminAuditLog,
    BundleRelease,
    BundleReleaseItem,
    Character,
    CharacterAppearance,
    Edition,
    EntityOrganization,
    EntityPerson,
    EntityTag,
    ExternalProviderId,
    ImageAsset,
    ImageCacheEntry,
    Item,
    MetadataProposal,
    Organization,
    Person,
    ProviderIngestJob,
    Series,
    SeriesRelation,
    StoryArc,
    StoryArcItem,
    Tag,
    Variant,
    Volume,
)
from app.models.user import User
from app.providers.base import (
    MetadataProvider,
    NormalizedBundleMember,
    NormalizedCredit,
    NormalizedItem,
    NormalizedRelation,
    NormalizedSeason,
    NormalizedVariantCover,
    ProviderItem,
)
from app.providers.comicvine import ComicVineCharacterDetail, ComicVineProvider
from app.providers.normalize import normalize_arc_title, normalize_person_name
from app.providers.registry import ProviderRegistry
from app.repositories.metadata import MetadataRepository
from app.services.provider_preview_state import (
    HydratedProviderPreview,
    ProviderPreviewState,
)
from app.services.provider_search_state import ProviderSearchState
from app.schemas.admin import (
    AdminBundleReleaseCorrectionRequest,
    AdminAuditLogResponse,
    ProviderCacheStatsResponse,
    ProviderCacheSummaryResponse,
    AdminCatalogSummaryResponse,
    AdminDuplicateActionResponse,
    AdminDuplicateCandidateResponse,
    AdminDuplicateIgnoreRequest,
    AdminDuplicateMergeRequest,
    AdminMetadataCorrectionRequest,
    AdminSeriesTagsUpdateRequest,
    AdminSearchHistoryEntry,
    AdminSearchReindexResponse,
    AdminSearchStatusResponse,
    ProviderBatchHydrateRequest,
    ProviderBatchHydrateResponse,
    ProviderBatchHydrateResultItem,
    ProviderIngestHistoryEntry,
    ProviderIngestJobCreateRequest,
    ProviderIngestJobResponse,
    ProviderIngestJobRunResponse,
    ProviderIngestJobSummaryResponse,
    ProviderIngestRequest,
    ProviderIngestRetryRequest,
    ProviderIngestResponse,
    ProviderPreviewCredit,
    ProviderPreviewResponse,
    ProviderPreviewTrack,
    MetadataProposalAdminResponse,
    MetadataProposalSummaryResponse,
    ProviderSearchRequest,
    ProviderStatusResponse,
)
from app.schemas.metadata import (
    BundleReleaseDetailResponse,
    ProviderLink,
    SeriesResponse,
    bundle_release_member_sort_key,
    bundle_release_detail_from_model,
    item_response_from_model,
)
from app.search.client import SearchClient
from app.search.documents import item_search_document
from app.services.metadata import MetadataService
from app.storage.image_cache import ImageCache
from app.storage.images import ImageMirror


_SEARCH_HISTORY: deque[AdminSearchHistoryEntry] = deque(maxlen=20)
_INGEST_HISTORY: deque[ProviderIngestHistoryEntry] = deque(maxlen=50)
_INGEST_HISTORY_SEQUENCE = 0
logger = logging.getLogger(__name__)


def _meili_document_count(stats: Any) -> int | None:
    if isinstance(stats, dict):
        value = stats.get("numberOfDocuments")
        if value is None:
            value = stats.get("number_of_documents")
    else:
        value = getattr(stats, "number_of_documents", None)
        if value is None:
            value = getattr(stats, "numberOfDocuments", None)
        if value is None and hasattr(stats, "model_dump"):
            dumped = stats.model_dump(by_alias=True)
            value = dumped.get("numberOfDocuments")
            if value is None:
                value = dumped.get("number_of_documents")
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError:
            return None
    return value if isinstance(value, int) else None


class AdminMetadataService:
    def __init__(self, db: AsyncSession, actor: User | None = None) -> None:
        self.db = db
        self.actor_user_id = actor.id if actor else None
        self.actor_email = actor.email if actor else None
        self.providers = ProviderRegistry()
        self.provider_preview_state = ProviderPreviewState()
        self.settings = get_settings()
        self.provider_search_state = ProviderSearchState(self.settings)
        self._comicvine_character_details: dict[str, ComicVineCharacterDetail | None] = {}

    async def _provider_links_for_items(
        self, item_ids: list[UUID]
    ) -> dict[UUID, list[ProviderLink]]:
        if not item_ids:
            return {}
        result = await self.db.execute(
            select(ExternalProviderId)
            .where(
                ExternalProviderId.entity_type == "item",
                ExternalProviderId.entity_id.in_(item_ids),
            )
            .order_by(ExternalProviderId.provider, ExternalProviderId.provider_item_id)
        )
        links_by_item: dict[UUID, list[ProviderLink]] = {}
        for row in result.scalars():
            links_by_item.setdefault(row.entity_id, []).append(
                ProviderLink(
                    provider=row.provider,
                    entity_type=row.entity_type,
                    provider_item_id=row.provider_item_id,
                    site_url=row.site_url,
                    api_url=row.api_url,
                )
            )
        return links_by_item

    async def _item_response(self, item: Item) -> Any:
        links_by_item = await self._provider_links_for_items([item.id])
        return item_response_from_model(item, extra_provider_links=links_by_item.get(item.id))

    async def _item_responses(self, items: list[Item]) -> list[Any]:
        links_by_item = await self._provider_links_for_items([item.id for item in items])
        return [
            item_response_from_model(item, extra_provider_links=links_by_item.get(item.id))
            for item in items
        ]

    @staticmethod
    def _provider_link_url_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _looks_like_api_url(value: str) -> bool:
        lowered = value.casefold()
        return "/api/" in lowered or "api." in lowered

    @classmethod
    def _provider_link_urls_from_value(cls, value: Any) -> tuple[str | None, str | None]:
        site_url: str | None = None
        api_url: str | None = None
        if isinstance(value, dict):
            site_url = cls._provider_link_url_text(
                value.get("site_detail_url")
                or value.get("site_url")
                or value.get("html_url")
                or value.get("web_url")
                or value.get("external_url")
                or value.get("permalink")
            )
            api_url = cls._provider_link_url_text(value.get("api_detail_url") or value.get("api_url"))
            fallback_url = cls._provider_link_url_text(value.get("url") or value.get("source_url"))
            if fallback_url:
                if api_url is None and cls._looks_like_api_url(fallback_url):
                    api_url = fallback_url
                elif site_url is None:
                    site_url = fallback_url
            return site_url, api_url
        fallback_url = cls._provider_link_url_text(value)
        if fallback_url is None:
            return None, None
        if cls._looks_like_api_url(fallback_url):
            return None, fallback_url
        return fallback_url, None

    def _provider_link_urls_for_provider(
        self,
        provider: ExternalProvider,
        provider_ids: dict[str, str],
        raw_value: Any,
    ) -> dict[str, dict[str, str | None]] | None:
        provider_item_id = provider_ids.get(provider.value)
        if not provider_item_id:
            return None
        site_url, api_url = self._provider_link_urls_from_value(raw_value)
        if site_url is None and api_url is None:
            return None
        return {provider.value: {"site_url": site_url, "api_url": api_url}}

    @staticmethod
    def _credit_provider_urls(credit: NormalizedCredit) -> dict[str, str | None] | None:
        if credit.site_detail_url is None and credit.api_detail_url is None:
            return None
        return {
            "site_url": credit.site_detail_url,
            "api_url": credit.api_detail_url,
        }

    async def provider_statuses(self) -> list[ProviderStatusResponse]:
        return [
            ProviderStatusResponse(
                name=status.name,
                display_name=status.display_name,
                kind=status.kind.value,
                supported_kinds=[kind.value for kind in status.supported_kinds],
                status="live" if status.is_configured else "stub",
                is_configured=status.is_configured,
                supports_search=status.supports_search,
                supports_ingest=status.supports_ingest,
                requires_user_key=status.requires_user_key,
                non_commercial_only=status.non_commercial_only,
                allows_redistribution=status.allows_redistribution,
                allows_image_mirroring=status.allows_image_mirroring,
                requires_attribution=status.requires_attribution,
                license_name=status.license_name,
                terms_url=status.terms_url,
                attribution_url=status.attribution_url,
                rate_limit=status.rate_limit,
                cache_policy=status.cache_policy,
                message=status.status_message,
            )
            for status in self.providers.status_entries()
        ]

    async def provider_cache_stats(self) -> ProviderCacheSummaryResponse:
        return ProviderCacheSummaryResponse(
            search=ProviderCacheStatsResponse(**(await self.provider_search_state.stats())),
            preview=ProviderCacheStatsResponse(**(await self.provider_preview_state.stats())),
        )

    async def catalog_summary(self) -> AdminCatalogSummaryResponse:
        duplicate_groups = await self._duplicate_group_count()
        return AdminCatalogSummaryResponse(
            items=await self._count(Item),
            items_by_kind=await self._item_counts_by_kind(),
            series=await self._count(Series),
            volumes=await self._count(Volume),
            editions=await self._count(Edition),
            variants=await self._count(Variant),
            provider_links=await self._count(ExternalProviderId),
            image_assets=await self._count_image_assets(),
            image_cache_entries=await self._count(ImageCacheEntry),
            pending_proposals=await self._count_pending_proposals(),
            missing_cover_items=await self._count_missing_cover_items(),
            missing_provider_link_items=await self._count_missing_provider_link_items(),
            duplicate_candidate_groups=duplicate_groups,
            provider_ingest_successes=await self._provider_ingest_success_count(),
            provider_ingest_failures=await self._provider_ingest_failure_count(),
        )

    async def search_status(self) -> AdminSearchStatusResponse:
        try:
            client = SearchClient()
            client.client.health()
            stats = client.client.index(client.index_name).get_stats()
            document_count = _meili_document_count(stats)
        except Exception as exc:
            logger.warning("admin_search_status_failed error=%s", exc)
            return AdminSearchStatusResponse(
                ok=False,
                index_name=SearchClient.index_name,
                error=str(exc),
            )
        return AdminSearchStatusResponse(
            ok=True,
            index_name=client.index_name,
            document_count=document_count,
            is_empty=document_count == 0 if document_count is not None else None,
        )

    async def reindex_search(self) -> AdminSearchReindexResponse:
        search = SearchClient()
        try:
            await search.configure()
            documents = await self._search_documents()
            await search.replace_documents(documents)
        except Exception as exc:
            logger.warning("admin_search_reindex_failed index=%s error=%s", search.index_name, exc)
            response = AdminSearchReindexResponse(
                ok=False,
                index_name=search.index_name,
                indexed_documents=0,
                error=str(exc),
            )
            self._record_search_history(response)
            return response
        response = AdminSearchReindexResponse(
            ok=True,
            index_name=search.index_name,
            indexed_documents=len(documents),
        )
        self._record_search_history(response)
        return response

    def search_history(self) -> list[AdminSearchHistoryEntry]:
        return list(_SEARCH_HISTORY)

    async def audit_logs(
        self,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        limit: int = 25,
    ) -> list[AdminAuditLogResponse]:
        stmt = select(AdminAuditLog).order_by(
            AdminAuditLog.created_at.desc(),
            AdminAuditLog.id.desc(),
        )
        if action:
            stmt = stmt.where(AdminAuditLog.action == action)
        if entity_type:
            stmt = stmt.where(AdminAuditLog.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(AdminAuditLog.entity_id == entity_id)
        result = await self.db.execute(stmt.limit(limit))
        return [AdminAuditLogResponse.model_validate(row) for row in result.scalars()]

    async def catalog_items(
        self,
        query: str | None = None,
        kind: ItemKind | None = None,
        limit: int = 25,
    ) -> list[Any]:
        items = await MetadataRepository(self.db).search_items(
            query=query,
            kind=kind,
            limit=limit,
        )
        return await self._item_responses(items)

    async def update_catalog_item(
        self,
        item_id: UUID,
        payload: AdminMetadataCorrectionRequest,
        kind: ItemKind | None = None,
    ) -> Any:
        item = await MetadataRepository(self.db).get_item(item_id, kind)
        if item is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="metadata_item_not_found",
                detail="Item not found",
            )
        update_data = payload.model_dump(exclude_unset=True)
        before = {
            "title": item.title,
            "item_number": item.item_number,
            "synopsis": item.synopsis,
            "edition_title": None,
            "page_count": item.page_count,
            "runtime_minutes": item.runtime_minutes,
            "publisher": None,
            "release_date": None,
            "imprint": None,
            "subtitle": None,
            "series_group": None,
            "country": None,
            "language": None,
            "age_rating": None,
            "catalog_number": None,
            "release_status": None,
            "variant_name": None,
            "barcode": None,
            "cover_image_url": None,
            "thumbnail_image_url": None,
        }
        if "title" in update_data and payload.title is not None:
            item.title = payload.title
        if "item_number" in update_data:
            item.item_number = payload.item_number
        if "synopsis" in update_data:
            item.synopsis = payload.synopsis
        if "page_count" in update_data:
            item.page_count = payload.page_count
        if "runtime_minutes" in update_data:
            item.runtime_minutes = payload.runtime_minutes
        item.sort_key = self._sort_key(item.kind, item.title, item.item_number)

        edition = self._primary_edition_model(item)
        physical_format = None
        if "physical_format" in update_data:
            physical_format = self._validated_physical_format(
                item.kind,
                payload.physical_format,
            )
        if edition is not None:
            edition_metadata = dict(edition.metadata_json or {})
            normalized_metadata = dict(edition_metadata.get("normalized") or {})
            before["edition_title"] = edition.title
            before["publisher"] = edition.publisher
            before["release_date"] = edition.release_date
            before["imprint"] = normalized_metadata.get("imprint")
            before["subtitle"] = normalized_metadata.get("subtitle")
            before["series_group"] = normalized_metadata.get("series_group")
            before["country"] = normalized_metadata.get("country")
            before["language"] = edition.language or normalized_metadata.get("language")
            before["age_rating"] = normalized_metadata.get("age_rating")
            before["catalog_number"] = normalized_metadata.get("catalog_number")
            before["release_status"] = normalized_metadata.get("release_status")
            if "edition_title" in update_data:
                edition.title = payload.edition_title
            if "publisher" in update_data:
                edition.publisher = payload.publisher
            if "release_date" in update_data:
                edition.release_date = payload.release_date
            if "imprint" in update_data:
                normalized_metadata["imprint"] = payload.imprint
            if "series_group" in update_data:
                normalized_metadata["series_group"] = payload.series_group
            if "subtitle" in update_data:
                normalized_metadata["subtitle"] = payload.subtitle
            if "country" in update_data:
                normalized_metadata["country"] = payload.country
            if "language" in update_data:
                edition.language = payload.language
                normalized_metadata["language"] = payload.language
            if "age_rating" in update_data:
                normalized_metadata["age_rating"] = payload.age_rating
            if "catalog_number" in update_data:
                normalized_metadata["catalog_number"] = payload.catalog_number
            if "release_status" in update_data:
                normalized_metadata["release_status"] = payload.release_status
            if normalized_metadata != dict(edition_metadata.get("normalized") or {}):
                edition_metadata["normalized"] = normalized_metadata
            if edition_metadata != dict(edition.metadata_json or {}):
                edition.metadata_json = edition_metadata
            if physical_format is not None:
                self._apply_physical_format_to_edition(edition, physical_format)

        variant = self._primary_variant_model(item)
        if variant is not None:
            before["variant_name"] = variant.name
            before["barcode"] = variant.barcode
            before["cover_image_url"] = variant.cover_image_url
            before["thumbnail_image_url"] = variant.thumbnail_image_url
            if "variant_name" in update_data and payload.variant_name is not None:
                variant.name = payload.variant_name
            if "barcode" in update_data:
                variant.barcode = payload.barcode
            if "cover_image_url" in update_data:
                variant.cover_image_url = payload.cover_image_url
                variant.metadata_json = self._metadata_with_cover(
                    variant.metadata_json,
                    payload.cover_image_url,
                )
            if "thumbnail_image_url" in update_data:
                variant.thumbnail_image_url = payload.thumbnail_image_url
            if physical_format is not None:
                self._apply_physical_format_to_variant(variant, physical_format)

        metadata = dict(item.metadata_json or {})
        metadata["admin_corrected_at"] = datetime.now(UTC).isoformat()
        metadata["admin_corrected_fields"] = sorted(update_data.keys())
        item.metadata_json = metadata
        self._record_admin_audit(
            action="metadata.correction",
            entity_type="item",
            entity_id=item.id,
            details={
                "kind": item.kind,
                "fields": sorted(update_data.keys()),
                "before": before,
                "after": update_data,
            },
        )
        await self.db.commit()
        loaded_item = await MetadataRepository(self.db).get_item(item.id)
        if loaded_item:
            await SearchClient().index_documents_best_effort([item_search_document(loaded_item)])
        return await self._item_response(loaded_item)

    async def update_series_tags(
        self,
        series_id: UUID,
        payload: AdminSeriesTagsUpdateRequest,
    ) -> SeriesResponse:
        series = await self.db.get(Series, series_id)
        if series is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="series_not_found",
                detail="Series not found",
            )

        before = await self._entity_tag_names("series", series.id, self._series_tag_kind(series.kind))
        normalized_tags = self._normalize_admin_tags(payload.tags)
        await self._replace_entity_tags(
            entity_type="series",
            entity_id=series.id,
            tag_kind=self._series_tag_kind(series.kind),
            names=normalized_tags,
        )

        metadata = dict(series.metadata_json or {})
        metadata["admin_corrected_at"] = datetime.now(UTC).isoformat()
        metadata["admin_corrected_fields"] = ["tags"]
        series.metadata_json = metadata
        self._record_admin_audit(
            action="metadata.series_tags_update",
            entity_type="series",
            entity_id=series.id,
            details={
                "kind": series.kind,
                "fields": ["tags"],
                "before": {"tags": before},
                "after": {"tags": normalized_tags},
            },
        )
        await self.db.commit()

        from app.services.metadata import MetadataService

        return await MetadataService(self.db).get_series(series.id)

    async def update_bundle_release(
        self,
        bundle_release_id: UUID,
        payload: AdminBundleReleaseCorrectionRequest,
    ) -> BundleReleaseDetailResponse:
        bundle = await MetadataRepository(self.db).get_bundle_release(bundle_release_id)
        if bundle is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="bundle_release_not_found",
                detail="Bundle release not found",
            )
        update_data = payload.model_dump(exclude_unset=True)
        bundle_items = list(bundle.items or [])
        before = {
            "title": bundle.title,
            "bundle_type": bundle.bundle_type,
            "format": bundle.format,
            "variant_type": bundle.variant_type,
            "packaging_type": bundle.packaging_type,
            "region": bundle.region,
            "language": bundle.language,
            "publisher": bundle.publisher,
            "sku": bundle.sku,
            "barcode": bundle.barcode,
            "release_date": bundle.release_date,
            "cover_image_url": bundle.cover_image_url,
            "thumbnail_image_url": bundle.thumbnail_image_url,
            "primary_item_id": bundle.primary_item_id,
            "members": [
                {
                    "id": member.id,
                    "item_id": member.item_id,
                    "role": member.role,
                    "sequence_number": member.sequence_number,
                    "disc_number": member.disc_number,
                    "disc_label": member.disc_label,
                    "quantity": member.quantity,
                    "is_primary": member.is_primary,
                }
                for member in sorted(bundle_items, key=bundle_release_member_sort_key)
            ],
        }

        for field in (
            "title",
            "bundle_type",
            "format",
            "variant_type",
            "packaging_type",
            "region",
            "language",
            "publisher",
            "sku",
            "barcode",
            "release_date",
            "cover_image_url",
            "thumbnail_image_url",
        ):
            if field in update_data:
                setattr(bundle, field, update_data[field])

        affected_item_ids = {member.item_id for member in bundle_items}
        if "members" in update_data:
            members_payload = payload.members or []
            if not members_payload:
                raise ApiHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="bundle_members_required",
                    detail="Bundle release updates must keep at least one member",
                )
            existing_members = {member.id: member for member in bundle_items}
            payload_existing_ids = [member.id for member in members_payload if member.id is not None]
            if len(payload_existing_ids) != len(set(payload_existing_ids)):
                raise ApiHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="duplicate_bundle_member_reference",
                    detail="Bundle member updates cannot reference the same membership row twice",
                )
            primary_members = [member for member in members_payload if member.is_primary]
            if len(primary_members) != 1:
                raise ApiHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="invalid_bundle_primary_member",
                    detail="Exactly one bundle member must be marked as primary",
                )
            requested_item_ids = {
                member.item_id
                for member in members_payload
                if member.item_id is not None
            }
            requested_item_ids.update(
                existing_members[member_id].item_id
                for member_id in payload_existing_ids
                if member_id in existing_members
            )
            if not requested_item_ids:
                raise ApiHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="bundle_members_required",
                    detail="Bundle release updates must keep at least one member",
                )
            item_result = await self.db.execute(select(Item).where(Item.id.in_(requested_item_ids)))
            available_items = {item.id: item for item in item_result.scalars().all()}
            missing_item_ids = sorted(str(item_id) for item_id in requested_item_ids if item_id not in available_items)
            if missing_item_ids:
                raise ApiHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="bundle_member_item_not_found",
                    detail=f"Bundle member items not found: {', '.join(missing_item_ids)}",
                )

            kept_member_ids: set[UUID] = set()
            member_keys: set[tuple[UUID, str, int | None, int | None]] = set()
            primary_member_model: BundleReleaseItem | None = None
            for member_payload in members_payload:
                if member_payload.id is not None:
                    member = existing_members.get(member_payload.id)
                    if member is None:
                        raise ApiHTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            code="bundle_member_mismatch",
                            detail="Bundle member updates must reference valid membership rows",
                        )
                    kept_member_ids.add(member.id)
                    if member_payload.item_id is not None and member_payload.item_id != member.item_id:
                        member.item_id = member_payload.item_id
                        member.item = available_items[member_payload.item_id]
                else:
                    if member_payload.item_id is None:
                        raise ApiHTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            code="bundle_member_item_required",
                            detail="New bundle members must include item_id",
                        )
                    member = BundleReleaseItem(
                        bundle_release_id=bundle.id,
                        item_id=member_payload.item_id,
                        item=available_items[member_payload.item_id],
                    )
                    self.db.add(member)
                    if bundle.items is None:
                        bundle.items = []
                    bundle.items.append(member)
                member.role = member_payload.role
                member.sequence_number = member_payload.sequence_number
                member.disc_number = member_payload.disc_number
                member.disc_label = member_payload.disc_label
                member.quantity = member_payload.quantity
                member.is_primary = member_payload.is_primary
                member_key = (
                    member.item_id,
                    member.role,
                    member.disc_number,
                    member.sequence_number,
                )
                if member_key in member_keys:
                    raise ApiHTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        code="duplicate_bundle_member",
                        detail="Bundle members must remain unique by item, role, disc, and sequence",
                    )
                member_keys.add(member_key)
                if member.is_primary:
                    primary_member_model = member

            for member_id, member in existing_members.items():
                if member_id in kept_member_ids:
                    continue
                if member in bundle.items:
                    bundle.items.remove(member)
                await self.db.delete(member)

            if primary_member_model is None:
                raise ApiHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="invalid_bundle_primary_member",
                    detail="Exactly one bundle member must be marked as primary",
                )
            primary_member = primary_member_model
            bundle.primary_item_id = primary_member.item_id
            bundle.primary_item = primary_member.item

        metadata = dict(bundle.metadata_json or {})
        metadata["admin_corrected_at"] = datetime.now(UTC).isoformat()
        metadata["admin_corrected_fields"] = sorted(update_data.keys())
        bundle.metadata_json = metadata
        self._record_admin_audit(
            action="metadata.bundle_correction",
            entity_type="bundle_release",
            entity_id=bundle.id,
            details={
                "kind": bundle.kind,
                "fields": sorted(update_data.keys()),
                "before": before,
                "after": update_data,
            },
        )
        await self.db.commit()

        loaded_bundle = await MetadataRepository(self.db).get_bundle_release(bundle.id)
        if loaded_bundle is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="bundle_release_not_found",
                detail="Bundle release not found after update",
            )
        await self._reindex_items(affected_item_ids | {member.item_id for member in loaded_bundle.items})
        return bundle_release_detail_from_model(loaded_bundle)

    def _validated_physical_format(
        self,
        kind: ItemKind,
        physical_format: str | None,
    ) -> PhysicalFormatConfig:
        if not physical_format:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="physical_format_required",
                detail="physical_format is required when updating a video format",
            )
        if not is_video_item_kind(kind):
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="physical_format_unsupported",
                detail="physical_format is only supported for movie and TV catalog items",
            )
        config = physical_format_for_id(physical_format)
        if config is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="invalid_physical_format",
                detail="physical_format must be one of DVD, Blu-ray, 4K UHD, VHS, LaserDisc, or digital",
            )
        return config

    def _apply_physical_format_to_edition(
        self,
        edition: Edition,
        physical_format: PhysicalFormatConfig,
    ) -> None:
        edition.format = physical_format.label
        metadata = self._metadata_with_physical_format(
            edition.metadata_json,
            physical_format,
        )
        edition.metadata_json = metadata

    def _apply_physical_format_to_variant(
        self,
        variant: Variant,
        physical_format: PhysicalFormatConfig,
    ) -> None:
        variant.variant_type = physical_format.variant_type
        metadata = self._metadata_with_physical_format(
            variant.metadata_json,
            physical_format,
        )
        variant.metadata_json = metadata

    def _metadata_with_physical_format(
        self,
        metadata_json: dict[str, Any] | None,
        physical_format: PhysicalFormatConfig,
    ) -> dict[str, Any]:
        metadata = dict(metadata_json or {})
        normalized_source = metadata.get("normalized")
        normalized = dict(normalized_source) if isinstance(normalized_source, dict) else {}
        normalized.update(
            {
                "physical_format": physical_format.id,
                "physical_format_label": physical_format.label,
                "physical_format_media_family": physical_format.media_family,
                "physical_format_variant_type": physical_format.variant_type,
            }
        )
        metadata["normalized"] = normalized
        return metadata

    def _metadata_with_cover(
        self,
        metadata_json: dict[str, Any] | None,
        source_url: str | None,
    ) -> dict[str, Any]:
        metadata = dict(metadata_json or {})
        normalized_source = metadata.get("normalized")
        normalized = dict(normalized_source) if isinstance(normalized_source, dict) else {}
        normalized.update(self._cover_metadata(source_url, None))
        metadata["normalized"] = normalized
        return metadata

    async def duplicate_candidates(self, limit: int = 10) -> list[AdminDuplicateCandidateResponse]:
        count_label = func.count(Item.id).label("count")
        item_ids_label = func.array_agg(Item.id).label("item_ids")
        result = await self.db.execute(
            select(
                Item.kind,
                Item.title,
                Item.item_number,
                count_label,
                item_ids_label,
            )
            .group_by(Item.kind, Item.title, Item.item_number)
            .having(func.count(Item.id) > 1)
            .order_by(count_label.desc(), Item.title.asc())
            .limit(min(limit * 4, 200))
        )
        candidates: list[AdminDuplicateCandidateResponse] = []
        for kind, title, item_number, count, item_ids in result.all():
            ids = list(item_ids or [])
            if await self._duplicate_group_is_ignored(ids):
                continue
            conflicts = await self._duplicate_conflict_flags(ids)
            duplicate_score, recommended_target_item_id = await self._score_duplicate_candidate(
                ids,
                conflicts=conflicts,
            )
            candidates.append(
                AdminDuplicateCandidateResponse(
                    kind=kind.value if hasattr(kind, "value") else str(kind),
                    title=title,
                    item_number=item_number,
                    count=count,
                    item_ids=ids,
                    reason="same title and item number",
                    has_provider_conflicts=conflicts["provider"],
                    has_cover_conflicts=conflicts["cover"],
                    duplicate_score=duplicate_score,
                    recommended_target_item_id=recommended_target_item_id,
                )
            )
        candidates.sort(
            key=lambda candidate: (
                -candidate.duplicate_score,
                -candidate.count,
                candidate.title.lower(),
                (candidate.item_number or "").lower(),
            )
        )
        return candidates[:limit]

    async def ignore_duplicate_candidate(
        self, payload: AdminDuplicateIgnoreRequest
    ) -> AdminDuplicateActionResponse:
        items = await self._items_by_ids(payload.item_ids)
        if len(items) != len(set(payload.item_ids)):
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="duplicate_item_not_found",
                detail="One or more duplicate items were not found",
            )
        self._ensure_same_duplicate_group(items)
        token = self._duplicate_ignore_token([item.id for item in items])
        for item in items:
            metadata = dict(item.metadata_json or {})
            metadata["admin_duplicate_ignore_token"] = token
            metadata["admin_duplicate_ignored_at"] = datetime.now(UTC).isoformat()
            item.metadata_json = metadata
        self._record_admin_audit(
            action="duplicates.ignore",
            entity_type="duplicate_group",
            details={
                "item_ids": [item.id for item in items],
                "kind": items[0].kind if items else None,
                "title": items[0].title if items else None,
                "item_number": items[0].item_number if items else None,
            },
        )
        await self.db.commit()
        return AdminDuplicateActionResponse(ok=True, affected_items=len(items))

    async def merge_duplicate_candidate(
        self, payload: AdminDuplicateMergeRequest
    ) -> AdminDuplicateActionResponse:
        source_ids = [
            item_id for item_id in payload.source_item_ids if item_id != payload.target_item_id
        ]
        if not source_ids:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="duplicate_source_required",
                detail="At least one source item different from target_item_id is required",
            )
        items = await self._items_by_ids([payload.target_item_id, *source_ids])
        if len(items) != len({payload.target_item_id, *source_ids}):
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="duplicate_item_not_found",
                detail="One or more duplicate items were not found",
            )
        target = next(item for item in items if item.id == payload.target_item_id)
        sources = [item for item in items if item.id != payload.target_item_id]
        self._ensure_same_duplicate_group([target, *sources])

        for source in sources:
            await self._move_item_children(source, target)
            await self.db.delete(source)
        self._record_admin_audit(
            action="duplicates.merge",
            entity_type="item",
            entity_id=target.id,
            details={
                "target_item_id": target.id,
                "source_item_ids": [source.id for source in sources],
                "kind": target.kind,
                "title": target.title,
                "item_number": target.item_number,
            },
        )
        await self.db.commit()

        loaded_item = await MetadataRepository(self.db).get_item(target.id)
        if loaded_item is None:
            raise ApiHTTPException(
                status_code=status.HTTP_409_CONFLICT,
                code="merged_target_unavailable",
                detail="Merged target item could not be loaded",
            )
        response_item = await self._item_response(loaded_item)
        return AdminDuplicateActionResponse(
            ok=True,
            affected_items=len(sources),
            item=response_item,
        )

    async def provider_search(self, payload: ProviderSearchRequest) -> list[dict[str, Any]]:
        results = await MetadataService(self.db).search_provider(
            payload.provider,
            payload.query,
            payload.kind,
        )
        return [result.model_dump(mode="json") for result in results]

    async def proposal_summary(self) -> MetadataProposalSummaryResponse:
        result = await self.db.execute(
            select(MetadataProposal.status, func.count(MetadataProposal.id)).group_by(
                MetadataProposal.status
            )
        )
        counts = {status: count for status, count in result.all()}
        pending = counts.get("pending", 0)
        approved = counts.get("approved", 0)
        rejected = counts.get("rejected", 0)
        return MetadataProposalSummaryResponse(
            pending=pending,
            approved=approved,
            rejected=rejected,
            total=pending + approved + rejected,
        )

    async def list_proposals(
        self, status_filter: str = "pending", provider_filter: ExternalProvider | None = None
    ) -> list[MetadataProposalAdminResponse]:
        stmt = select(MetadataProposal).where(MetadataProposal.status == status_filter)
        if provider_filter:
            stmt = stmt.where(MetadataProposal.provider == provider_filter)
        result = await self.db.execute(stmt.order_by(MetadataProposal.created_at.asc()))
        return [
            MetadataProposalAdminResponse.model_validate(proposal) for proposal in result.scalars()
        ]

    async def approve_proposal(self, proposal_id: UUID) -> ProviderIngestResponse:
        proposal = await self.db.get(MetadataProposal, proposal_id)
        if proposal is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="metadata_proposal_not_found",
                detail="Proposal not found",
            )
        if proposal.provider_item_id is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="metadata_proposal_missing_provider_item",
                detail="Proposal does not have a provider item id",
            )
        response = await self.ingest(
            ProviderIngestRequest(
                provider=proposal.provider,
                provider_item_id=proposal.provider_item_id,
            )
        )
        proposal.status = "approved"
        self._record_admin_audit(
            action="metadata_proposal.approve",
            entity_type="metadata_proposal",
            entity_id=proposal.id,
            details={
                "provider": proposal.provider,
                "provider_item_id": proposal.provider_item_id,
                "item_id": response.item_id,
                "created": response.created,
            },
        )
        await self.db.commit()
        return response

    async def approve_proposal_with_provider_item(
        self,
        proposal_id: UUID,
        payload: ProviderIngestRequest,
    ) -> ProviderIngestResponse:
        proposal = await self.db.get(MetadataProposal, proposal_id)
        if proposal is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="metadata_proposal_not_found",
                detail="Proposal not found",
            )
        response = await self.ingest(payload)
        proposal.provider = payload.provider
        proposal.provider_item_id = payload.provider_item_id
        proposal.status = "approved"
        self._record_admin_audit(
            action="metadata_proposal.approve_provider",
            entity_type="metadata_proposal",
            entity_id=proposal.id,
            details={
                "provider": payload.provider,
                "provider_item_id": payload.provider_item_id,
                "item_id": response.item_id,
                "created": response.created,
            },
        )
        await self.db.commit()
        return response

    async def reject_proposal(self, proposal_id: UUID) -> MetadataProposalAdminResponse:
        proposal = await self.db.get(MetadataProposal, proposal_id)
        if proposal is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="metadata_proposal_not_found",
                detail="Proposal not found",
            )
        proposal.status = "rejected"
        self._record_admin_audit(
            action="metadata_proposal.reject",
            entity_type="metadata_proposal",
            entity_id=proposal.id,
            details={
                "provider": proposal.provider,
                "provider_item_id": proposal.provider_item_id,
                "query": proposal.query,
            },
        )
        await self.db.commit()
        await self.db.refresh(proposal)
        return MetadataProposalAdminResponse.model_validate(proposal)

    async def create_ingest_job(
        self,
        payload: ProviderIngestJobCreateRequest,
    ) -> ProviderIngestJobResponse:
        provider = self._provider(payload.provider)
        self._ensure_provider_ingest_supported(provider, payload.provider)
        job = ProviderIngestJob(
            provider=payload.provider,
            provider_item_id=payload.provider_item_id,
            status="queued",
            attempts=0,
            max_attempts=payload.max_attempts,
            next_run_at=datetime.now(UTC),
        )
        self.db.add(job)
        await self.db.flush()
        self._record_admin_audit(
            action="provider_ingest.job_create",
            entity_type="provider_ingest_job",
            entity_id=job.id,
            details={
                "provider": payload.provider,
                "provider_item_id": payload.provider_item_id,
                "max_attempts": payload.max_attempts,
            },
        )
        await self.db.commit()
        await self.db.refresh(job)
        return ProviderIngestJobResponse.model_validate(job)

    async def ingest_jobs(
        self,
        status_filter: str | None = None,
        limit: int = 25,
        provider_filter: ExternalProvider | None = None,
        query: str | None = None,
    ) -> list[ProviderIngestJobResponse]:
        stmt = select(ProviderIngestJob).order_by(
            ProviderIngestJob.created_at.desc(),
            ProviderIngestJob.id.desc(),
        )
        if status_filter:
            stmt = stmt.where(ProviderIngestJob.status == status_filter)
        if provider_filter:
            stmt = stmt.where(ProviderIngestJob.provider == provider_filter)
        normalized_query = " ".join(query.split()) if query else ""
        if normalized_query:
            pattern = f"%{normalized_query}%"
            stmt = stmt.where(
                or_(
                    ProviderIngestJob.provider_item_id.ilike(pattern),
                    ProviderIngestJob.last_error.ilike(pattern),
                )
            )
        result = await self.db.execute(stmt.limit(limit))
        return [ProviderIngestJobResponse.model_validate(job) for job in result.scalars().all()]

    async def ingest_job_summary(self) -> ProviderIngestJobSummaryResponse:
        now = datetime.now(UTC)
        stale_cutoff = now - timedelta(
            seconds=self.settings.worker_provider_ingest_stale_after_seconds
        )
        counts_result = await self.db.execute(
            select(ProviderIngestJob.status, func.count())
            .select_from(ProviderIngestJob)
            .group_by(ProviderIngestJob.status)
        )
        counts = {
            "queued": 0,
            "running": 0,
            "failed": 0,
            "done": 0,
        }
        for status_value, count in counts_result.all():
            if status_value in counts:
                counts[status_value] = int(count)

        due_queued = await self.db.scalar(
            select(func.count())
            .select_from(ProviderIngestJob)
            .where(
                ProviderIngestJob.status == "queued",
                or_(
                    ProviderIngestJob.next_run_at.is_(None),
                    ProviderIngestJob.next_run_at <= now,
                ),
            )
        )
        stale_running = await self.db.scalar(
            select(func.count())
            .select_from(ProviderIngestJob)
            .where(
                ProviderIngestJob.status == "running",
                ProviderIngestJob.updated_at < stale_cutoff,
            )
        )
        oldest_queued_at = await self.db.scalar(
            select(func.min(ProviderIngestJob.created_at)).where(
                ProviderIngestJob.status == "queued"
            )
        )
        next_run_at = await self.db.scalar(
            select(func.min(ProviderIngestJob.next_run_at)).where(
                ProviderIngestJob.status == "queued",
                ProviderIngestJob.next_run_at.is_not(None),
            )
        )
        latest_failure_at = await self.db.scalar(
            select(func.max(ProviderIngestJob.updated_at)).where(
                ProviderIngestJob.status == "failed"
            )
        )
        return ProviderIngestJobSummaryResponse(
            **counts,
            due_queued=int(due_queued or 0),
            stale_running=int(stale_running or 0),
            oldest_queued_at=oldest_queued_at,
            next_run_at=next_run_at,
            latest_failure_at=latest_failure_at,
        )

    async def run_ingest_job(self, job_id: UUID) -> ProviderIngestJobResponse:
        job = await self.db.get(ProviderIngestJob, job_id)
        if job is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="provider_ingest_job_not_found",
                detail="Ingest job not found",
            )
        if job.status == "running":
            raise ApiHTTPException(
                status_code=status.HTTP_409_CONFLICT,
                code="provider_ingest_job_running",
                detail="Ingest job is already running",
            )
        executed = await self._execute_ingest_job(job)
        self._record_admin_audit(
            action="provider_ingest.job_run",
            entity_type="provider_ingest_job",
            entity_id=executed.id,
            details=self._ingest_job_audit_details(executed),
        )
        await self.db.commit()
        return ProviderIngestJobResponse.model_validate(executed)

    async def retry_ingest_job(self, job_id: UUID) -> ProviderIngestJobResponse:
        job = await self.db.get(ProviderIngestJob, job_id)
        if job is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="provider_ingest_job_not_found",
                detail="Ingest job not found",
            )
        if job.status == "running":
            raise ApiHTTPException(
                status_code=status.HTTP_409_CONFLICT,
                code="provider_ingest_job_running",
                detail="Ingest job is already running",
            )
        job.status = "queued"
        job.next_run_at = datetime.now(UTC)
        job.last_error = None
        await self.db.commit()
        await self.db.refresh(job)
        executed = await self._execute_ingest_job(job)
        self._record_admin_audit(
            action="provider_ingest.job_retry",
            entity_type="provider_ingest_job",
            entity_id=executed.id,
            details=self._ingest_job_audit_details(executed),
        )
        await self.db.commit()
        return ProviderIngestJobResponse.model_validate(executed)

    async def run_pending_ingest_jobs(self, limit: int = 5) -> ProviderIngestJobRunResponse:
        recovered = await self.recover_stale_ingest_jobs()
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(ProviderIngestJob)
            .where(
                ProviderIngestJob.status == "queued",
                or_(
                    ProviderIngestJob.next_run_at.is_(None),
                    ProviderIngestJob.next_run_at <= now,
                ),
            )
            .order_by(ProviderIngestJob.created_at.asc())
            .limit(limit)
        )
        processed: list[ProviderIngestJobResponse] = []
        for job in result.scalars().all():
            processed.append(
                ProviderIngestJobResponse.model_validate(await self._execute_ingest_job(job))
            )
        if self.actor_user_id is not None:
            self._record_admin_audit(
                action="provider_ingest.jobs_run_pending",
                entity_type="provider_ingest_queue",
                details={
                    "processed": len(processed),
                    "recovered": recovered,
                    "job_ids": [job.id for job in processed],
                },
            )
            await self.db.commit()
        return ProviderIngestJobRunResponse(
            processed=len(processed),
            jobs=processed,
            recovered=recovered,
        )

    async def recover_stale_ingest_jobs(self) -> int:
        stale_after = self.settings.worker_provider_ingest_stale_after_seconds
        cutoff = datetime.now(UTC) - timedelta(seconds=stale_after)
        result = await self.db.execute(
            update(ProviderIngestJob)
            .where(
                ProviderIngestJob.status == "running",
                ProviderIngestJob.updated_at < cutoff,
            )
            .values(
                status="queued",
                next_run_at=datetime.now(UTC),
                last_error="Recovered stale running ingest job",
            )
            .returning(ProviderIngestJob.id)
        )
        recovered = len(result.scalars().all())
        if recovered:
            await self.db.commit()
            logger.warning("provider_ingest_jobs_recovered count=%s", recovered)
        return recovered

    def ingest_history(self) -> list[ProviderIngestHistoryEntry]:
        return list(_INGEST_HISTORY)

    async def refresh_stale_items(self, limit: int = 10) -> int:
        """Re-fetch provider data for items not updated within the staleness window."""
        stale_days = self.settings.worker_catalog_refresh_stale_days
        cutoff = datetime.now(UTC) - timedelta(days=stale_days)
        result = await self.db.execute(
            select(ExternalProviderId)
            .where(
                ExternalProviderId.entity_type == "item",
                ExternalProviderId.updated_at < cutoff,
            )
            .order_by(ExternalProviderId.updated_at.asc())
            .limit(limit)
        )
        provider_ids = result.scalars().all()
        refreshed = 0
        for pid in provider_ids:
            try:
                await self._refresh_item_from_provider(pid)
                refreshed += 1
            except Exception:
                logger.exception(
                    "catalog_refresh_failed provider=%s provider_item_id=%s entity_id=%s",
                    pid.provider.value,
                    pid.provider_item_id,
                    pid.entity_id,
                )
        if refreshed:
            await self.db.commit()
        return refreshed

    async def _refresh_item_from_provider(self, pid: ExternalProviderId) -> None:
        registry = ProviderRegistry()
        provider_name = pid.provider
        provider = registry.get(provider_name)
        if provider is None or not provider.is_configured:
            pid.updated_at = datetime.now(UTC)
            return

        provider_item = await provider.get_item(pid.provider_item_id)
        normalized = await provider.normalize(provider_item.raw)

        item = await self.db.get(Item, pid.entity_id)
        if item is None:
            return

        item.title = normalized.title
        item.synopsis = normalized.synopsis
        item.runtime_minutes = normalized.runtime_minutes
        item.page_count = normalized.page_count
        metadata = dict(item.metadata_json or {})
        metadata["source"] = provider_item.raw
        metadata["last_refresh"] = datetime.now(UTC).isoformat()
        item.metadata_json = metadata

        pid.updated_at = datetime.now(UTC)
        logger.info(
            "catalog_refresh_ok provider=%s provider_item_id=%s item_id=%s",
            pid.provider.value,
            pid.provider_item_id,
            pid.entity_id,
        )

    async def retry_ingest(self, payload: ProviderIngestRetryRequest) -> ProviderIngestResponse:
        entry = next(
            (entry for entry in _INGEST_HISTORY if entry.id == payload.history_id),
            None,
        )
        if entry is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="provider_ingest_history_not_found",
                detail="Provider ingest history entry not found",
            )
        if entry.status != "failed":
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_ingest_history_not_failed",
                detail="Only failed provider ingest entries can be retried",
            )
        response = await self.ingest(
            ProviderIngestRequest(
                provider=entry.provider,
                provider_item_id=entry.provider_item_id,
            )
        )
        self._record_admin_audit(
            action="provider_ingest.history_retry",
            entity_type="provider_ingest_history",
            details={
                "history_id": entry.id,
                "provider": entry.provider,
                "provider_item_id": entry.provider_item_id,
                "item_id": response.item_id,
                "created": response.created,
            },
        )
        await self.db.commit()
        return response

    async def preview(self, payload: ProviderIngestRequest) -> ProviderPreviewResponse:
        """Fetch and normalize provider data without creating anything in the DB."""
        provider = self._provider(payload.provider)
        self._ensure_provider_ingest_supported(provider, payload.provider)
        self._ensure_provider_kind_supported(provider, payload)
        hydrated = await self._hydrated_provider_preview(payload, provider=provider)
        provider_item = hydrated.provider_item
        normalized = hydrated.normalized
        physical_format = self._physical_format_for_normalized(normalized)
        return ProviderPreviewResponse(
            provider=payload.provider.value,
            provider_item_id=provider_item.provider_item_id,
            kind=normalized.kind,
            title=normalized.title,
            item_number=normalized.item_number,
            synopsis=normalized.synopsis,
            series_title=normalized.series_title,
            volume_name=normalized.volume_name,
            volume_number=normalized.volume_number,
            volume_start_year=normalized.volume_start_year,
            publisher=normalized.publisher,
            imprint=normalized.imprint,
            edition_title=normalized.edition_title,
            edition_format=normalized.edition_format,
            physical_format=physical_format.id if physical_format else None,
            physical_format_label=physical_format.label if physical_format else None,
            release_date=normalized.release_date,
            barcode=normalized.barcode,
            isbn=normalized.isbn,
            variant_name=normalized.variant_name or (
                physical_format.label if physical_format is not None else None
            ),
            cover_image_url=normalized.cover_image_url,
            cover_price_cents=normalized.cover_price_cents,
            currency=normalized.currency,
            country=normalized.country,
            language=normalized.language,
            age_rating=normalized.age_rating,
            subtitle=normalized.subtitle,
            series_group=normalized.series_group,
            page_count=normalized.page_count,
            runtime_minutes=normalized.runtime_minutes,
            track_count=normalized.track_count,
            catalog_number=normalized.catalog_number,
            creators=[
                ProviderPreviewCredit(
                    name=c.name,
                    role=c.role,
                    image_url=c.image_url,
                )
                for c in normalized.creators
            ],
            characters=[c.name for c in normalized.characters],
            story_arcs=[c.name for c in normalized.story_arcs],
            platforms=normalized.platforms,
            genres=normalized.genres,
            release_status=normalized.release_status,
            tracks=[
                ProviderPreviewTrack(
                    position=t.position,
                    title=t.title,
                    duration_seconds=t.duration_seconds,
                    artist=t.artist,
                    disc_number=t.disc_number,
                )
                for t in normalized.tracks
            ],
        )

    async def batch_hydrate(
        self,
        payload: ProviderBatchHydrateRequest,
    ) -> ProviderBatchHydrateResponse:
        """Batch-fetch and normalize provider data without creating anything in the DB."""
        provider = self._provider(payload.provider)
        self._ensure_provider_ingest_supported(provider, payload.provider)
        results: list[ProviderBatchHydrateResultItem] = []
        succeeded = 0
        failed = 0
        for item in payload.items:
            try:
                ingest_req = ProviderIngestRequest(
                    provider=payload.provider,
                    provider_item_id=item.provider_item_id,
                )
                preview = await self.preview(ingest_req)
                results.append(
                    ProviderBatchHydrateResultItem(
                        provider_item_id=item.provider_item_id,
                        success=True,
                        preview=preview,
                    )
                )
                succeeded += 1
            except Exception as exc:
                logger.warning(
                    "batch_hydrate_item_failed provider=%s id=%s error=%s",
                    payload.provider.value,
                    item.provider_item_id,
                    str(exc),
                )
                results.append(
                    ProviderBatchHydrateResultItem(
                        provider_item_id=item.provider_item_id,
                        success=False,
                        error=str(exc),
                    )
                )
                failed += 1
        return ProviderBatchHydrateResponse(
            results=results,
            total=len(payload.items),
            succeeded=succeeded,
            failed=failed,
        )

    async def ingest(self, payload: ProviderIngestRequest) -> ProviderIngestResponse:
        attempts = max(1, self.settings.provider_ingest_retry_attempts + 1)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = await self._ingest_once(payload)
                self._record_ingest_history(
                    payload=payload,
                    status="created" if response.created else "existing",
                    attempts=attempt,
                    item_id=response.item_id,
                )
                logger.info(
                    "provider_ingest_finished provider=%s provider_item_id=%s status=%s "
                    "attempts=%s item_id=%s",
                    payload.provider.value,
                    payload.provider_item_id,
                    "created" if response.created else "existing",
                    attempt,
                    response.item_id,
                )
                await self.provider_preview_state.invalidate(
                    payload.provider.value,
                    payload.provider_item_id,
                    response.item.provider_links[0].provider_item_id if response.item.provider_links else None,
                )
                return response
            except Exception as exc:
                last_error = exc
                await self.db.rollback()
                await self.provider_preview_state.invalidate(
                    payload.provider.value,
                    payload.provider_item_id,
                )
                if attempt >= attempts or not self._is_retryable_ingest_error(exc):
                    self._record_ingest_history(
                        payload=payload,
                        status="failed",
                        attempts=attempt,
                        error=self._error_message(exc),
                    )
                    logger.warning(
                        "provider_ingest_failed provider=%s provider_item_id=%s attempts=%s "
                        "error=%s",
                        payload.provider.value,
                        payload.provider_item_id,
                        attempt,
                        self._error_message(exc),
                    )
                    raise
        raise RuntimeError("Provider ingest retry loop exited unexpectedly") from last_error

    async def _ingest_once(self, payload: ProviderIngestRequest) -> ProviderIngestResponse:
        provider = self._provider(payload.provider)
        self._ensure_provider_ingest_supported(provider, payload.provider)
        self._ensure_provider_kind_supported(provider, payload)
        existing_provider_id = await self._get_provider_id(payload)
        if existing_provider_id:
            return await self._existing_response(existing_provider_id)

        hydrated = await self._hydrated_provider_preview(payload, provider=provider)
        provider_item = hydrated.provider_item
        existing_provider_id = await self._get_provider_id_value(
            payload.provider, provider_item.provider_item_id
        )
        if existing_provider_id:
            return await self._existing_response(existing_provider_id)

        normalized = hydrated.normalized
        if normalized.bundle_release is not None:
            item = await self._ingest_bundle_release(
                provider=provider,
                provider_name=payload.provider,
                provider_item=provider_item,
                normalized=normalized,
            )
        else:
            item, _, _ = await self._create_catalog_item_from_normalized(
                provider=provider,
                provider_name=payload.provider,
                provider_item_id=provider_item.provider_item_id,
                provider_raw=provider_item.raw,
                normalized=normalized,
            )
        await self.db.commit()
        loaded_item = await MetadataRepository(self.db).get_item(item.id)
        if loaded_item:
            await SearchClient().index_documents_best_effort([item_search_document(loaded_item)])
        return ProviderIngestResponse(
            item_id=item.id,
            created=True,
            item=await self._item_response(loaded_item),
        )

    async def _hydrated_provider_preview(
        self,
        payload: ProviderIngestRequest,
        *,
        provider: MetadataProvider,
        use_cache: bool = True,
    ) -> HydratedProviderPreview:
        if use_cache:
            cached = await self.provider_preview_state.cached(
                payload.provider.value,
                payload.provider_item_id,
            )
            if cached is not None:
                return cached
        provider_item = await provider.get_item(payload.provider_item_id)
        normalized = await provider.normalize(provider_item.raw)
        normalized = await self._enrich_missing_comic_cover(normalized)
        if payload.kind is not None and normalized.kind != payload.kind:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_kind_mismatch",
                detail=(
                    f"Provider item '{payload.provider_item_id}' normalized as "
                    f"'{normalized.kind.value}', not '{payload.kind.value}'"
                ),
            )
        hydrated = HydratedProviderPreview(
            provider_item=provider_item,
            normalized=normalized,
        )
        if use_cache:
            await self.provider_preview_state.store(
                payload.provider.value,
                payload.provider_item_id,
                hydrated,
            )
        return hydrated

    def _ensure_provider_kind_supported(
        self,
        provider: MetadataProvider,
        payload: ProviderIngestRequest,
    ) -> None:
        if payload.kind is not None and not provider.capabilities.supports_kind(payload.kind):
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_kind_unsupported",
                detail=(
                    f"Provider '{payload.provider.value}' does not support "
                    f"kind '{payload.kind.value}'"
                ),
            )

    def _physical_format_for_normalized(
        self,
        normalized: NormalizedItem,
    ) -> PhysicalFormatConfig | None:
        if not is_video_item_kind(normalized.kind):
            return None
        candidate = normalized.physical_format or normalized.edition_format
        if not candidate:
            return None
        return physical_format_for_id(candidate)

    async def _comicvine_associated_variants(
        self,
        *,
        provider: MetadataProvider,
        provider_name: ExternalProvider,
        provider_item_id: str,
        normalized: NormalizedItem,
        edition: Edition,
        primary_cover_url: str | None,
    ) -> tuple[list[Variant], list[Any]]:
        if not normalized.variant_covers:
            return [], []

        variants: list[Variant] = []
        mirrored_covers: list[Any] = []
        seen_cover_urls = {primary_cover_url} if primary_cover_url else set()
        for cover in normalized.variant_covers:
            if not cover.cover_image_url or cover.cover_image_url in seen_cover_urls:
                continue
            seen_cover_urls.add(cover.cover_image_url)

            mirrored_cover = None
            if self._should_mirror_provider_images(provider):
                mirrored_cover = await ImageMirror().mirror_cover_best_effort(
                    cover.cover_image_url,
                    provider_name.value,
                    provider_item_id,
                )
            if mirrored_cover is not None:
                mirrored_covers.append(mirrored_cover)

            cover_metadata = self._cover_metadata(cover.cover_image_url, mirrored_cover)
            variants.append(
                Variant(
                    edition=edition,
                    name=self._variant_cover_name(cover, len(variants) + 1),
                    variant_type="variant",
                    cover_image_key=mirrored_cover.key if mirrored_cover else None,
                    cover_image_url=(
                        mirrored_cover.url if mirrored_cover else cover.cover_image_url
                    ),
                    thumbnail_image_key=(mirrored_cover.thumbnail_key if mirrored_cover else None),
                    thumbnail_image_url=(
                        mirrored_cover.thumbnail_url
                        if mirrored_cover
                        else cover.thumbnail_image_url
                    ),
                    description=cover.caption,
                    metadata_json={
                        "provider": provider_name.value,
                        "provider_item_id": cover.provider_item_id or provider_item_id,
                        "normalized": {
                            "name": self._variant_cover_name(cover, len(variants) + 1),
                            "variant_type": "variant",
                            "associated_image_id": cover.source_id,
                            "caption": cover.caption,
                            **cover_metadata,
                        },
                    },
                    is_primary=False,
                )
            )
        return variants, mirrored_covers

    def _variant_cover_name(self, cover: NormalizedVariantCover, index: int) -> str:
        name = cover.name.strip() if cover.name else ""
        return name[:255] if name else f"Variant cover {index}"

    def _cover_metadata(
        self,
        source_url: str | None,
        mirrored_cover: Any | None,
    ) -> dict[str, Any]:
        if mirrored_cover is not None:
            return {
                "cover_status": "mirrored",
                "cover_source_url": source_url,
                "cover_delivery_url": mirrored_cover.url,
                "cover_storage": "object_storage",
                "cover_policy": "minio_mirror",
            }
        if source_url:
            return {
                "cover_status": "external_url",
                "cover_source_url": source_url,
                "cover_delivery_url": source_url,
                "cover_storage": "provider_external_url",
                "cover_policy": "external_url_default",
            }
        return {
            "cover_status": "missing",
            "cover_source_url": None,
            "cover_delivery_url": None,
            "cover_storage": "generated_client_fallback",
            "cover_policy": "generated_cover_fallback",
        }

    async def _enrich_missing_comic_cover(
        self,
        normalized: NormalizedItem,
    ) -> NormalizedItem:
        if normalized.cover_image_url or normalized.kind not in {
            ItemKind.comic,
            ItemKind.manga,
        }:
            return normalized
        if normalized.variant_type == "variant":
            return normalized
        issue_number = normalized.item_number
        series_title = normalized.series_title or normalized.title
        if not issue_number or not series_title:
            return normalized
        try:
            provider = self.providers.get("comicvine")
        except KeyError:
            return normalized
        if not isinstance(provider, ComicVineProvider) or not provider.is_configured:
            return normalized
        try:
            cover = await provider.find_issue_cover(
                series_title=series_title,
                issue_number=issue_number,
                start_year=normalized.volume_start_year,
            )
        except Exception:
            logger.warning(
                "comicvine_cover_enrichment_failed series=%s issue=%s",
                series_title,
                issue_number,
                exc_info=True,
            )
            return normalized
        if cover is None:
            return normalized
        return replace(
            normalized,
            cover_image_url=cover.image_url,
            provider_ids={
                **normalized.provider_ids,
                "comicvine": cover.provider_item_id,
            },
        )

    async def _execute_ingest_job(self, job: ProviderIngestJob) -> ProviderIngestJob:
        job_id = job.id
        provider = job.provider
        provider_item_id = job.provider_item_id
        job.status = "running"
        job.attempts += 1
        job.last_error = None
        job.next_run_at = None
        await self.db.commit()
        try:
            response = await self.ingest(
                ProviderIngestRequest(
                    provider=provider,
                    provider_item_id=provider_item_id,
                )
            )
        except Exception as exc:
            await self.db.rollback()
            refreshed = await self.db.get(ProviderIngestJob, job_id)
            if refreshed is None:
                raise
            refreshed.last_error = self._error_message(exc)
            if refreshed.attempts < refreshed.max_attempts and self._is_retryable_ingest_error(exc):
                refreshed.status = "queued"
                refreshed.next_run_at = datetime.now(UTC) + self._backoff_delay(refreshed.attempts)
            else:
                refreshed.status = "failed"
                refreshed.next_run_at = None
            await self.db.commit()
            await self.db.refresh(refreshed)
            logger.warning(
                "provider_ingest_job_failed job_id=%s provider=%s provider_item_id=%s "
                "status=%s attempts=%s error=%s",
                refreshed.id,
                refreshed.provider.value,
                refreshed.provider_item_id,
                refreshed.status,
                refreshed.attempts,
                refreshed.last_error,
            )
            return refreshed

        refreshed = await self.db.get(ProviderIngestJob, job_id)
        if refreshed is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="provider_ingest_job_not_found",
                detail="Ingest job disappeared during execution",
            )
        refreshed.status = "done"
        refreshed.item_id = response.item_id
        refreshed.last_error = None
        refreshed.next_run_at = None
        await self.db.commit()
        await self.db.refresh(refreshed)
        logger.info(
            "provider_ingest_job_finished job_id=%s provider=%s provider_item_id=%s item_id=%s",
            refreshed.id,
            refreshed.provider.value,
            refreshed.provider_item_id,
            refreshed.item_id,
        )
        return refreshed

    def _provider(self, provider: ExternalProvider) -> MetadataProvider:
        try:
            return self.providers.get(provider.value)
        except KeyError as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_not_configured",
                detail=f"Provider '{provider.value}' is not configured",
            ) from exc

    def _ensure_provider_ingest_supported(
        self,
        provider: MetadataProvider,
        provider_name: ExternalProvider,
    ) -> None:
        if provider.capabilities.supports_ingest:
            return
        raise ApiHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="provider_ingest_unsupported",
            detail=f"Provider '{provider_name.value}' does not support catalog ingest yet",
        )

    def _should_mirror_provider_images(self, provider: MetadataProvider) -> bool:
        if not self.settings.mirror_provider_images:
            return False
        if self.settings.mirror_provider_images_allow_restricted:
            return True
        return provider.capabilities.allows_image_mirroring

    async def _get_provider_id(self, payload: ProviderIngestRequest) -> ExternalProviderId | None:
        return await self._get_provider_id_value(payload.provider, payload.provider_item_id)

    async def _get_provider_id_value(
        self, provider: ExternalProvider, provider_item_id: str
    ) -> ExternalProviderId | None:
        result = await self.db.execute(
            select(ExternalProviderId).where(
                ExternalProviderId.provider == provider,
                ExternalProviderId.provider_item_id == provider_item_id,
            )
        )
        return result.scalar_one_or_none()

    async def _existing_response(self, provider_id: ExternalProviderId) -> ProviderIngestResponse:
        if provider_id.entity_type == "bundle_release":
            bundle = await self.db.get(BundleRelease, provider_id.entity_id)
            item_id = bundle.primary_item_id if bundle is not None else None
            if item_id is None:
                raise ApiHTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    code="provider_link_stale",
                    detail="Provider link is stale",
                )
            item = await MetadataRepository(self.db).get_item(item_id)
        else:
            item = await MetadataRepository(self.db).get_item(provider_id.entity_id)
        if item is None:
            raise ApiHTTPException(
                status_code=status.HTTP_409_CONFLICT,
                code="provider_link_stale",
                detail="Provider link is stale",
            )
        return ProviderIngestResponse(
            item_id=item.id,
            created=False,
            item=await self._item_response(item),
        )

    async def _ingest_bundle_release(
        self,
        *,
        provider: MetadataProvider,
        provider_name: ExternalProvider,
        provider_item: ProviderItem,
        normalized: NormalizedItem,
    ) -> Item:
        bundle_normalized = normalized.bundle_release
        if bundle_normalized is None:
            raise RuntimeError("Bundle ingest called without bundle payload")

        members = self._bundle_members_for_ingest(normalized)
        created_members: list[tuple[NormalizedBundleMember, Item, Volume | None, Series | None]] = []
        for index, member in enumerate(members, start=1):
            member_provider_item_id = self._bundle_member_provider_item_id(
                provider_name,
                provider_item.provider_item_id,
                member,
                index,
            )
            member_item, member_volume, member_series = await self._create_catalog_item_from_normalized(
                provider=provider,
                provider_name=provider_name,
                provider_item_id=member_provider_item_id,
                provider_raw=provider_item.raw,
                normalized=member.item,
                ingest_related_collections=False,
            )
            created_members.append((member, member_item, member_volume, member_series))

        primary_member = next(
            ((member, item, volume, series) for member, item, volume, series in created_members if member.is_primary),
            created_members[0],
        )
        _, primary_item, primary_volume, primary_series = primary_member

        mirrored_cover = None
        if self._should_mirror_provider_images(provider):
            mirrored_cover = await ImageMirror().mirror_cover_best_effort(
                bundle_normalized.cover_image_url,
                provider_name.value,
                provider_item.provider_item_id,
            )
        cover_metadata = self._cover_metadata(bundle_normalized.cover_image_url, mirrored_cover)
        bundle = BundleRelease(
            kind=normalized.kind,
            title=bundle_normalized.title,
            bundle_type=bundle_normalized.bundle_type,
            franchise_id=primary_series.franchise_id if primary_series is not None else None,
            series_id=primary_series.id if primary_series is not None else None,
            volume_id=primary_volume.id if primary_volume is not None else None,
            primary_item_id=primary_item.id,
            format=bundle_normalized.format,
            variant_type=bundle_normalized.variant_type,
            packaging_type=bundle_normalized.packaging_type,
            region=bundle_normalized.region,
            language=bundle_normalized.language,
            publisher=bundle_normalized.publisher or normalized.publisher,
            sku=bundle_normalized.sku,
            barcode=bundle_normalized.barcode,
            release_date=bundle_normalized.release_date,
            cover_image_key=mirrored_cover.key if mirrored_cover else None,
            cover_image_url=mirrored_cover.url if mirrored_cover else bundle_normalized.cover_image_url,
            thumbnail_image_key=mirrored_cover.thumbnail_key if mirrored_cover else None,
            thumbnail_image_url=(
                mirrored_cover.thumbnail_url if mirrored_cover else bundle_normalized.cover_image_url
            ),
            external_ids=bundle_normalized.provider_ids or None,
            metadata_json={
                "provider": provider_name.value,
                "provider_item_id": provider_item.provider_item_id,
                "normalized": {
                    "title": bundle_normalized.title,
                    "bundle_type": bundle_normalized.bundle_type,
                    "format": bundle_normalized.format,
                    "variant_type": bundle_normalized.variant_type,
                    "packaging_type": bundle_normalized.packaging_type,
                    "region": bundle_normalized.region,
                    "language": bundle_normalized.language,
                    "publisher": bundle_normalized.publisher or normalized.publisher,
                    "sku": bundle_normalized.sku,
                    "barcode": bundle_normalized.barcode,
                    "release_date": (
                        bundle_normalized.release_date.isoformat()
                        if bundle_normalized.release_date
                        else None
                    ),
                    **cover_metadata,
                },
                "source": provider_item.raw,
            },
        )
        self.db.add(bundle)
        await self.db.flush()
        if mirrored_cover is not None:
            await ImageCache(self.db).record_mirrored_cover(mirrored_cover)
        for index, (member, member_item, _, _) in enumerate(created_members, start=1):
            self.db.add(
                BundleReleaseItem(
                    bundle_release_id=bundle.id,
                    item_id=member_item.id,
                    role=member.role,
                    sequence_number=member.sequence_number or index,
                    disc_number=member.disc_number,
                    disc_label=member.disc_label,
                    quantity=member.quantity,
                    is_primary=member.is_primary,
                    metadata_json=member.metadata or None,
                )
            )
        await self._add_provider_links(
            provider_name,
            bundle_normalized.provider_ids,
            "bundle_release",
            bundle.id,
            provider_urls=self._provider_link_urls_for_provider(
                provider_name,
                bundle_normalized.provider_ids,
                provider_item.raw,
            ),
        )
        return primary_item

    def _bundle_members_for_ingest(
        self,
        normalized: NormalizedItem,
    ) -> list[NormalizedBundleMember]:
        bundle_normalized = normalized.bundle_release
        if bundle_normalized is None:
            return []
        if bundle_normalized.members:
            return bundle_normalized.members
        return [
            NormalizedBundleMember(
                item=replace(normalized, bundle_release=None),
                role="primary",
                sequence_number=1,
                quantity=1,
                is_primary=True,
            )
        ]

    def _bundle_member_provider_item_id(
        self,
        provider_name: ExternalProvider,
        bundle_provider_item_id: str,
        member: NormalizedBundleMember,
        index: int,
    ) -> str:
        candidate = member.item.provider_ids.get(provider_name.value)
        if candidate:
            return candidate
        return f"{bundle_provider_item_id}#member-{index}"

    async def _create_catalog_item_from_normalized(
        self,
        *,
        provider: MetadataProvider,
        provider_name: ExternalProvider,
        provider_item_id: str,
        provider_raw: Any,
        normalized: NormalizedItem,
        ingest_related_collections: bool = True,
    ) -> tuple[Item, Volume | None, Series | None]:
        physical_format = self._physical_format_for_normalized(normalized)
        edition_format = physical_format.label if physical_format else normalized.edition_format
        variant_name = normalized.variant_name or (
            physical_format.label if physical_format is not None else "Cover A"
        )
        variant_type = normalized.variant_type or (
            physical_format.variant_type if physical_format is not None else None
        )
        mirrored_cover = None
        if self._should_mirror_provider_images(provider):
            mirrored_cover = await ImageMirror().mirror_cover_best_effort(
                normalized.cover_image_url,
                provider_name.value,
                provider_item_id,
            )
        cover_metadata = self._cover_metadata(normalized.cover_image_url, mirrored_cover)
        volume, series = await self._upsert_volume(
            normalized.kind,
            normalized.series_title,
            normalized.volume_name,
            normalized.volume_start_year,
        )
        item = Item(
            volume=volume,
            kind=normalized.kind,
            title=normalized.title,
            item_number=normalized.item_number,
            sort_key=self._sort_key(normalized.kind, normalized.title, normalized.item_number),
            synopsis=normalized.synopsis,
            runtime_minutes=normalized.runtime_minutes,
            page_count=normalized.page_count,
            metadata_json={
                "provider": provider_name.value,
                "provider_item_id": provider_item_id,
                "normalized": {
                    "kind": normalized.kind.value,
                    "series_title": normalized.series_title,
                    "volume_name": normalized.volume_name,
                    "volume_number": normalized.volume_number,
                    "volume_start_year": normalized.volume_start_year,
                    "runtime_minutes": normalized.runtime_minutes,
                    "story_arcs": [credit.name for credit in normalized.story_arcs],
                    **cover_metadata,
                },
            },
        )
        edition = Edition(
            item=item,
            title=normalized.edition_title or "Standard Edition",
            format=edition_format,
            publisher=normalized.publisher,
            isbn=normalized.isbn,
            release_date=normalized.release_date,
            metadata_json={
                "provider": provider_name.value,
                "provider_item_id": provider_item_id,
                "normalized": {
                    "title": normalized.edition_title or "Standard Edition",
                    "format": edition_format,
                    "physical_format": physical_format.id if physical_format else None,
                    "physical_format_label": physical_format.label if physical_format else None,
                    "physical_format_media_family": (
                        physical_format.media_family if physical_format else None
                    ),
                    "physical_format_variant_type": (
                        physical_format.variant_type if physical_format else None
                    ),
                    "publisher": normalized.publisher,
                    "imprint": normalized.imprint,
                    "release_date": (
                        normalized.release_date.isoformat() if normalized.release_date else None
                    ),
                    "isbn": normalized.isbn,
                    "barcode": normalized.barcode,
                    "creators": [
                        {"name": credit.name, "role": credit.role} for credit in normalized.creators
                    ],
                    "characters": [credit.name for credit in normalized.characters],
                    "story_arcs": [credit.name for credit in normalized.story_arcs],
                    "track_count": normalized.track_count,
                    "tracks": [
                        {
                            "position": track.position,
                            "title": track.title,
                            "duration_seconds": track.duration_seconds,
                            "artist": track.artist,
                            "disc_number": track.disc_number,
                        }
                        for track in normalized.tracks
                    ]
                    or None,
                    "catalog_number": normalized.catalog_number,
                    "country": normalized.country,
                    "release_status": normalized.release_status,
                    "platforms": normalized.platforms or None,
                    "genres": normalized.genres or None,
                    "language": normalized.language,
                    "age_rating": normalized.age_rating,
                    "subtitle": normalized.subtitle,
                    "series_group": normalized.series_group,
                    **cover_metadata,
                },
                "source": provider_raw,
            },
        )
        variant = Variant(
            edition=edition,
            name=variant_name,
            variant_type=variant_type,
            barcode=normalized.barcode,
            isbn=normalized.isbn,
            cover_price_cents=normalized.cover_price_cents,
            currency=normalized.currency,
            cover_image_key=mirrored_cover.key if mirrored_cover else None,
            cover_image_url=mirrored_cover.url if mirrored_cover else normalized.cover_image_url,
            thumbnail_image_key=mirrored_cover.thumbnail_key if mirrored_cover else None,
            thumbnail_image_url=mirrored_cover.thumbnail_url if mirrored_cover else None,
            metadata_json={
                "provider": provider_name.value,
                "provider_item_id": provider_item_id,
                "normalized": {
                    "name": variant_name,
                    "variant_type": variant_type,
                    "physical_format": physical_format.id if physical_format else None,
                    "physical_format_label": physical_format.label if physical_format else None,
                    "physical_format_media_family": (
                        physical_format.media_family if physical_format else None
                    ),
                    "physical_format_variant_type": (
                        physical_format.variant_type if physical_format else None
                    ),
                    "barcode": normalized.barcode,
                    "isbn": normalized.isbn,
                    "cover_price_cents": normalized.cover_price_cents,
                    "currency": normalized.currency,
                    **cover_metadata,
                },
            },
            is_primary=True,
        )
        additional_variants, additional_mirrored_covers = await self._comicvine_associated_variants(
            provider=provider,
            provider_name=provider_name,
            provider_item_id=provider_item_id,
            normalized=normalized,
            edition=edition,
            primary_cover_url=normalized.cover_image_url,
        )
        self.db.add_all([item, edition, variant, *additional_variants])
        await self.db.flush()
        if mirrored_cover:
            await ImageCache(self.db).record_mirrored_cover(mirrored_cover)
        for mirrored_variant_cover in additional_mirrored_covers:
            await ImageCache(self.db).record_mirrored_cover(mirrored_variant_cover)
        await self._add_provider_links(
            provider_name,
            normalized.provider_ids,
            "item",
            item.id,
            provider_urls=self._provider_link_urls_for_provider(
                provider_name,
                normalized.provider_ids,
                provider_raw,
            ),
        )
        if volume:
            await self._add_provider_links(provider_name, normalized.volume_provider_ids, "volume", volume.id)
        await self._link_publisher(item.id, normalized.publisher)
        await self._link_imprint(item.id, normalized.imprint, normalized.publisher)
        await self._link_people(item.id, provider_name, normalized.creators)
        await self._link_characters(item.id, provider_name, normalized.characters)
        await self._link_story_arcs(item.id, provider_name, normalized.story_arcs)
        await self._link_tags(item.id, "character", normalized.characters)
        await self._link_tags(item.id, "story_arc", normalized.story_arcs)
        if volume:
            await self._link_relations(series, normalized.relations)
        if ingest_related_collections and series and hasattr(provider, "get_seasons"):
            await self._ingest_seasons(provider, provider_item_id, series, normalized.kind)
        if ingest_related_collections and series and hasattr(provider, "get_volumes"):
            await self._ingest_volumes(provider, provider_item_id, series, normalized.kind)
        return item, volume, series

    async def _upsert_volume(
        self,
        kind: ItemKind,
        series_title: str | None,
        volume_name: str | None,
        volume_start_year: int | None,
    ) -> tuple[Volume | None, Series | None]:
        if not series_title and not volume_name:
            return None, None

        title = series_title or volume_name or "Unknown Series"
        series = await self._get_or_create_series(kind, title)
        name = volume_name or title
        result = await self.db.execute(
            select(Volume).where(Volume.series_id == series.id, Volume.name == name)
        )
        volume = result.scalar_one_or_none()
        if volume is None:
            volume = Volume(series=series, name=name, start_year=volume_start_year)
            self.db.add(volume)
            await self.db.flush()
        elif volume.start_year is None and volume_start_year:
            volume.start_year = volume_start_year
        return volume, series

    async def _get_or_create_series(self, kind: ItemKind, title: str) -> Series:
        result = await self.db.execute(
            select(Series).where(Series.kind == kind, Series.title == title)
        )
        series = result.scalar_one_or_none()
        if series is None:
            series = Series(kind=kind, title=title, slug=self._slug(title))
            self.db.add(series)
            await self.db.flush()
        return series

    async def _add_provider_links(
        self,
        provider: ExternalProvider,
        provider_ids: dict[str, str],
        entity_type: str,
        entity_id: UUID,
        provider_urls: dict[str, dict[str, str | None]] | None = None,
    ) -> None:
        candidate_ids = provider_ids or {}
        if provider.value not in candidate_ids:
            candidate_ids = {provider.value: "", **candidate_ids}
        for provider_name, provider_id in candidate_ids.items():
            if not provider_id:
                continue
            try:
                provider_enum = ExternalProvider(provider_name)
            except ValueError:
                continue
            urls = provider_urls.get(provider_name) if provider_urls else None
            site_url = self._provider_link_url_text(urls.get("site_url")) if urls else None
            api_url = self._provider_link_url_text(urls.get("api_url")) if urls else None
            existing = await self.db.scalar(
                select(ExternalProviderId).where(
                    ExternalProviderId.provider == provider_enum,
                    ExternalProviderId.provider_item_id == provider_id,
                )
            )
            if existing:
                if site_url and site_url != existing.site_url:
                    existing.site_url = site_url
                if api_url and api_url != existing.api_url:
                    existing.api_url = api_url
                continue
            self.db.add(
                ExternalProviderId(
                    provider=provider_enum,
                    provider_item_id=provider_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    site_url=site_url,
                    api_url=api_url,
                )
            )

    async def _link_publisher(self, item_id: UUID, publisher: str | None) -> None:
        if not publisher:
            return
        organization = await self._get_or_create_organization(publisher, "publisher")
        exists = await self.db.scalar(
            select(EntityOrganization.id).where(
                EntityOrganization.entity_type == "item",
                EntityOrganization.entity_id == item_id,
                EntityOrganization.organization_id == organization.id,
                EntityOrganization.role == "publisher",
            )
        )
        if exists:
            return
        self.db.add(
            EntityOrganization(
                entity_type="item",
                entity_id=item_id,
                organization_id=organization.id,
                role="publisher",
            )
        )

    async def _link_imprint(
        self, item_id: UUID, imprint: str | None, publisher: str | None
    ) -> None:
        if not imprint:
            return
        organization = await self._get_or_create_organization(imprint, "imprint")
        # Store the parent publisher in the imprint's metadata for reference.
        if publisher:
            metadata = dict(organization.metadata_json or {})
            if metadata.get("parent_publisher") != publisher:
                metadata["parent_publisher"] = publisher
                organization.metadata_json = metadata
        exists = await self.db.scalar(
            select(EntityOrganization.id).where(
                EntityOrganization.entity_type == "item",
                EntityOrganization.entity_id == item_id,
                EntityOrganization.organization_id == organization.id,
                EntityOrganization.role == "imprint",
            )
        )
        if exists:
            return
        self.db.add(
            EntityOrganization(
                entity_type="item",
                entity_id=item_id,
                organization_id=organization.id,
                role="imprint",
            )
        )

    async def _link_people(
        self,
        item_id: UUID,
        provider: ExternalProvider,
        credits: list[NormalizedCredit],
    ) -> None:
        for credit in credits:
            person = await self._get_or_create_person(credit.name, credit)
            role = credit.role or "creator"
            exists = await self.db.scalar(
                select(EntityPerson.id).where(
                    EntityPerson.entity_type == "item",
                    EntityPerson.entity_id == item_id,
                    EntityPerson.person_id == person.id,
                    EntityPerson.role == role,
                )
            )
            if exists:
                continue
            self.db.add(
                EntityPerson(
                    entity_type="item",
                    entity_id=item_id,
                    person_id=person.id,
                    role=role,
                )
            )
            provider_item_id = self._comicvine_credit_provider_id(credit, resource="person")
            if provider == ExternalProvider.comicvine and provider_item_id:
                await self._add_provider_links(
                    provider,
                    {provider.value: provider_item_id},
                    "person",
                    person.id,
                    provider_urls={provider.value: self._credit_provider_urls(credit) or {}},
                )

    async def _link_story_arcs(
        self,
        item_id: UUID,
        provider: ExternalProvider,
        credits: list[NormalizedCredit],
    ) -> None:
        seen_names: set[str] = set()
        for index, credit in enumerate(credits, start=1):
            name = credit.name.strip()
            if not name:
                continue
            key = name.casefold()
            if key in seen_names:
                continue
            seen_names.add(key)

            story_arc = await self._get_or_create_story_arc(name, credit)
            existing = await self.db.scalar(
                select(StoryArcItem.id).where(
                    StoryArcItem.story_arc_id == story_arc.id,
                    StoryArcItem.item_id == item_id,
                )
            )
            if not existing:
                self.db.add(
                    StoryArcItem(
                        story_arc_id=story_arc.id,
                        item_id=item_id,
                        ordinal=index,
                    )
                )

            provider_item_id = self._comicvine_credit_provider_id(credit, resource="story_arc")
            if provider == ExternalProvider.comicvine and provider_item_id:
                await self._add_provider_links(
                    provider,
                    {provider.value: provider_item_id},
                    "story_arc",
                    story_arc.id,
                    provider_urls={provider.value: self._credit_provider_urls(credit) or {}},
                )

    async def _link_characters(
        self,
        item_id: UUID,
        provider: ExternalProvider,
        credits: list[NormalizedCredit],
    ) -> None:
        seen_names: set[str] = set()
        for credit in credits:
            name = credit.name.strip()
            if not name:
                continue
            key = name.casefold()
            if key in seen_names:
                continue
            seen_names.add(key)

            character = await self._get_or_create_character(name, credit)
            role = self._character_appearance_role(credit.role)
            existing = await self.db.scalar(
                select(CharacterAppearance).where(
                    CharacterAppearance.character_id == character.id,
                    CharacterAppearance.item_id == item_id,
                )
            )
            if existing:
                if self._character_role_rank(role) > self._character_role_rank(existing.role):
                    existing.role = role
            else:
                self.db.add(
                    CharacterAppearance(
                        character_id=character.id,
                        item_id=item_id,
                        role=role,
                    )
                )

            provider_item_id = self._comicvine_credit_provider_id(credit, resource="character")
            if provider == ExternalProvider.comicvine and provider_item_id:
                await self._add_provider_links(
                    provider,
                    {provider.value: provider_item_id},
                    "character",
                    character.id,
                    provider_urls={provider.value: self._credit_provider_urls(credit) or {}},
                )
                await self._enrich_comicvine_character(
                    character,
                    provider_item_id,
                    current_item_id=item_id,
                )
            if character.first_appearance_item_id is None:
                character.first_appearance_item_id = item_id

    async def _link_tags(self, item_id: UUID, kind: str, credits: list[NormalizedCredit]) -> None:
        for credit in credits:
            tag = await self._get_or_create_tag(kind, credit.name)
            exists = await self.db.scalar(
                select(EntityTag.id).where(
                    EntityTag.entity_type == "item",
                    EntityTag.entity_id == item_id,
                    EntityTag.tag_id == tag.id,
                )
            )
            if exists:
                continue
            self.db.add(EntityTag(entity_type="item", entity_id=item_id, tag_id=tag.id))

    async def _link_relations(
        self,
        source_series: Series,
        relations: list[NormalizedRelation],
    ) -> None:
        for rel in relations:
            try:
                relation_type = SeriesRelationType(rel.relation_type)
            except ValueError:
                continue
            target_kind = rel.kind or source_series.kind
            target_series = await self._get_or_create_series(target_kind, rel.title)
            if target_series.id == source_series.id:
                continue
            existing = await self.db.scalar(
                select(SeriesRelation.id).where(
                    SeriesRelation.source_series_id == source_series.id,
                    SeriesRelation.target_series_id == target_series.id,
                    SeriesRelation.relation_type == relation_type,
                )
            )
            if existing:
                continue
            self.db.add(
                SeriesRelation(
                    source_series_id=source_series.id,
                    target_series_id=target_series.id,
                    relation_type=relation_type,
                    metadata_json={
                        "provider": rel.provider,
                        "provider_id": rel.provider_id,
                        "start_year": rel.start_year,
                        "image_url": rel.image_url,
                    },
                )
            )

    async def _ingest_seasons(
        self,
        provider: MetadataProvider,
        provider_item_id: str,
        series: Series,
        kind: ItemKind,
    ) -> None:
        if kind not in (ItemKind.tv, ItemKind.anime):
            return
        if not hasattr(provider, "get_seasons"):
            return
        try:
            seasons: list[NormalizedSeason] = await provider.get_seasons(provider_item_id)
        except Exception:
            logger.warning("Failed to fetch seasons for %s", provider_item_id, exc_info=True)
            return
        for season in seasons:
            volume_name = season.title or f"Season {season.season_number}"
            result = await self.db.execute(
                select(Volume).where(
                    Volume.series_id == series.id,
                    Volume.name == volume_name,
                )
            )
            volume = result.scalar_one_or_none()
            if volume is None:
                volume = Volume(
                    series=series,
                    name=volume_name,
                    volume_number=season.season_number,
                    start_year=season.air_date.year if season.air_date else None,
                )
                self.db.add(volume)
                await self.db.flush()
            for ep in season.episodes:
                existing_ep = await self.db.scalar(
                    select(Item.id).where(
                        Item.volume_id == volume.id,
                        Item.season_number == season.season_number,
                        Item.episode_number == ep.episode_number,
                    )
                )
                if existing_ep:
                    continue
                item = Item(
                    volume=volume,
                    kind=kind,
                    title=ep.title,
                    item_number=str(ep.episode_number),
                    sort_key=self._sort_key(kind, ep.title, str(ep.episode_number)),
                    synopsis=ep.overview,
                    season_number=season.season_number,
                    episode_number=ep.episode_number,
                    runtime_minutes=ep.runtime_minutes,
                    metadata_json={
                        "season_title": season.title,
                        "air_date": ep.air_date.isoformat() if ep.air_date else None,
                    },
                )
                self.db.add(item)
        await self.db.flush()

    async def _ingest_volumes(
        self,
        provider: MetadataProvider,
        provider_item_id: str,
        series: Series,
        kind: ItemKind,
    ) -> None:
        if kind != ItemKind.manga:
            return
        try:
            volumes: list[NormalizedSeason] = await provider.get_volumes(provider_item_id)
        except Exception:
            logger.warning("Failed to fetch volumes for %s", provider_item_id, exc_info=True)
            return
        for vol in volumes:
            volume_name = vol.title or f"Volume {vol.season_number}"
            result = await self.db.execute(
                select(Volume).where(
                    Volume.series_id == series.id,
                    Volume.name == volume_name,
                )
            )
            volume = result.scalar_one_or_none()
            if volume is None:
                volume = Volume(
                    series=series,
                    name=volume_name,
                    volume_number=vol.season_number,
                    start_year=vol.air_date.year if vol.air_date else None,
                )
                self.db.add(volume)
                await self.db.flush()
            for ch in vol.episodes:
                existing_ch = await self.db.scalar(
                    select(Item.id).where(
                        Item.volume_id == volume.id,
                        Item.item_number == str(ch.episode_number),
                    )
                )
                if existing_ch:
                    continue
                item = Item(
                    volume=volume,
                    kind=kind,
                    title=ch.title,
                    item_number=str(ch.episode_number),
                    sort_key=self._sort_key(kind, ch.title, str(ch.episode_number)),
                    synopsis=ch.overview,
                    page_count=ch.runtime_minutes,
                    metadata_json={
                        "volume_title": vol.title,
                        "air_date": ch.air_date.isoformat() if ch.air_date else None,
                    },
                )
                self.db.add(item)
        await self.db.flush()

    async def _get_or_create_organization(self, name: str, organization_type: str) -> Organization:
        result = await self.db.execute(
            select(Organization).where(
                Organization.name == name,
                Organization.type == organization_type,
            )
        )
        organization = result.scalar_one_or_none()
        if organization is None:
            organization = Organization(name=name, type=organization_type)
            self.db.add(organization)
            await self.db.flush()
        return organization

    async def _get_or_create_person(self, name: str, credit: NormalizedCredit) -> Person:
        canonical = normalize_person_name(name)
        display_name = canonical or name
        # Try exact match first, then normalized match.
        result = await self.db.execute(select(Person).where(Person.name == display_name))
        person = result.scalar_one_or_none()
        if person is None and display_name != name:
            result = await self.db.execute(select(Person).where(Person.name == name))
            person = result.scalar_one_or_none()
        if person is None:
            person = Person(
                name=display_name,
                metadata_json={
                    "api_detail_url": credit.api_detail_url,
                    "site_detail_url": credit.site_detail_url,
                    "image_url": credit.image_url,
                },
            )
            self.db.add(person)
            await self.db.flush()
            return person
        metadata = dict(person.metadata_json or {})
        updated = False
        if not metadata.get("api_detail_url") and credit.api_detail_url:
            metadata["api_detail_url"] = credit.api_detail_url
            updated = True
        if not metadata.get("site_detail_url") and credit.site_detail_url:
            metadata["site_detail_url"] = credit.site_detail_url
            updated = True
        if not metadata.get("image_url") and credit.image_url:
            metadata["image_url"] = credit.image_url
            updated = True
        if updated:
            person.metadata_json = metadata
        return person

    async def _get_or_create_story_arc(self, name: str, credit: NormalizedCredit) -> StoryArc:
        # Try exact name first, then fall back to normalized title match.
        result = await self.db.execute(
            select(StoryArc).where(StoryArc.name == name)
        )
        story_arc = result.scalars().first()
        if story_arc is None:
            normalized = normalize_arc_title(name)
            if normalized:
                all_arcs = (await self.db.execute(select(StoryArc))).scalars().all()
                for candidate in all_arcs:
                    if normalize_arc_title(candidate.name) == normalized:
                        story_arc = candidate
                        break
        if story_arc is None:
            story_arc = StoryArc(
                name=name,
                metadata_json={
                    "api_detail_url": credit.api_detail_url,
                    "site_detail_url": credit.site_detail_url,
                },
            )
            self.db.add(story_arc)
            await self.db.flush()
            return story_arc
        metadata = dict(story_arc.metadata_json or {})
        updated = False
        if not metadata.get("api_detail_url") and credit.api_detail_url:
            metadata["api_detail_url"] = credit.api_detail_url
            updated = True
        if not metadata.get("site_detail_url") and credit.site_detail_url:
            metadata["site_detail_url"] = credit.site_detail_url
            updated = True
        if updated:
            story_arc.metadata_json = metadata
        return story_arc

    async def _get_or_create_character(self, name: str, credit: NormalizedCredit) -> Character:
        result = await self.db.execute(select(Character).where(Character.name == name))
        character = result.scalar_one_or_none()
        if character is None:
            character = Character(
                name=name,
                metadata_json={
                    "api_detail_url": credit.api_detail_url,
                    "site_detail_url": credit.site_detail_url,
                },
            )
            self.db.add(character)
            await self.db.flush()
            return character
        metadata = dict(character.metadata_json or {})
        updated = False
        if not metadata.get("api_detail_url") and credit.api_detail_url:
            metadata["api_detail_url"] = credit.api_detail_url
            updated = True
        if not metadata.get("site_detail_url") and credit.site_detail_url:
            metadata["site_detail_url"] = credit.site_detail_url
            updated = True
        if updated:
            character.metadata_json = metadata
        return character

    async def _enrich_comicvine_character(
        self,
        character: Character,
        provider_item_id: str,
        *,
        current_item_id: UUID,
    ) -> None:
        if (
            character.description
            and character.image_url
            and character.aliases
            and character.first_appearance_item_id
        ):
            return
        detail = await self._comicvine_character_detail(provider_item_id)
        if detail is None:
            return

        if not character.description and detail.description:
            character.description = detail.description
        if not character.image_url and detail.image_url:
            character.image_url = detail.image_url
        character.aliases = self._merge_aliases(
            character.aliases or [],
            detail.aliases,
            primary_name=character.name,
        )
        metadata = dict(character.metadata_json or {})
        metadata.setdefault("api_detail_url", detail.api_detail_url)
        metadata.setdefault("site_detail_url", detail.site_detail_url)
        metadata["comicvine_character_id"] = detail.provider_item_id
        if detail.first_appeared_in_issue_id:
            metadata["comicvine_first_appeared_in_issue_id"] = detail.first_appeared_in_issue_id
            first_item_id = await self._local_item_id_for_provider_id(
                ExternalProvider.comicvine,
                detail.first_appeared_in_issue_id,
            )
            if first_item_id is not None:
                character.first_appearance_item_id = first_item_id
            elif detail.first_appeared_in_issue_id == await self._provider_id_for_item(
                ExternalProvider.comicvine,
                current_item_id,
            ):
                character.first_appearance_item_id = current_item_id
        character.metadata_json = {
            key: value for key, value in metadata.items() if value is not None
        }

    async def _comicvine_character_detail(
        self,
        provider_item_id: str,
    ) -> ComicVineCharacterDetail | None:
        if provider_item_id in self._comicvine_character_details:
            return self._comicvine_character_details[provider_item_id]
        provider = self.providers.maybe_get(ExternalProvider.comicvine)
        if not isinstance(provider, ComicVineProvider):
            self._comicvine_character_details[provider_item_id] = None
            return None
        try:
            detail = await provider.get_character_detail(provider_item_id)
        except ApiHTTPException:
            logger.info("ComicVine character enrichment failed for %s", provider_item_id)
            detail = None
        self._comicvine_character_details[provider_item_id] = detail
        return detail

    async def _local_item_id_for_provider_id(
        self,
        provider: ExternalProvider,
        provider_item_id: str,
    ) -> UUID | None:
        return await self.db.scalar(
            select(ExternalProviderId.entity_id).where(
                ExternalProviderId.provider == provider,
                ExternalProviderId.provider_item_id == provider_item_id,
                ExternalProviderId.entity_type == "item",
            )
        )

    async def _provider_id_for_item(
        self,
        provider: ExternalProvider,
        item_id: UUID,
    ) -> str | None:
        return await self.db.scalar(
            select(ExternalProviderId.provider_item_id).where(
                ExternalProviderId.provider == provider,
                ExternalProviderId.entity_type == "item",
                ExternalProviderId.entity_id == item_id,
            )
        )

    def _merge_aliases(
        self,
        existing: list[str],
        incoming: list[str],
        *,
        primary_name: str,
    ) -> list[str]:
        aliases: list[str] = []
        seen = {primary_name.casefold()}
        for value in [*existing, *incoming]:
            text = " ".join(str(value or "").split()).strip()
            key = text.casefold()
            if not text or key in seen:
                continue
            aliases.append(text)
            seen.add(key)
        return aliases

    async def _get_or_create_tag(self, kind: str, name: str) -> Tag:
        result = await self.db.execute(select(Tag).where(Tag.kind == kind, Tag.name == name))
        tag = result.scalar_one_or_none()
        if tag is None:
            tag = Tag(kind=kind, name=name)
            self.db.add(tag)
            await self.db.flush()
        return tag

    async def _entity_tag_names(
        self,
        entity_type: str,
        entity_id: UUID,
        tag_kind: str | None = None,
    ) -> list[str]:
        stmt = (
            select(Tag.name)
            .join(EntityTag, EntityTag.tag_id == Tag.id)
            .where(
                EntityTag.entity_type == entity_type,
                EntityTag.entity_id == entity_id,
            )
            .order_by(Tag.name.asc())
        )
        if tag_kind is not None:
            stmt = stmt.where(Tag.kind == tag_kind)
        rows = await self.db.scalars(stmt)
        return [name for name in rows if isinstance(name, str) and name.strip()]

    async def _replace_entity_tags(
        self,
        entity_type: str,
        entity_id: UUID,
        tag_kind: str,
        names: list[str],
    ) -> None:
        existing_links = list(
            (
                await self.db.execute(
                    select(EntityTag)
                    .join(Tag, Tag.id == EntityTag.tag_id)
                    .where(
                        EntityTag.entity_type == entity_type,
                        EntityTag.entity_id == entity_id,
                        Tag.kind == tag_kind,
                    )
                )
            ).scalars()
        )
        for link in existing_links:
            await self.db.delete(link)
        await self.db.flush()
        for name in names:
            tag = await self._get_or_create_tag(tag_kind, name)
            self.db.add(EntityTag(entity_type=entity_type, entity_id=entity_id, tag_id=tag.id))
        await self.db.flush()

    def _normalize_admin_tags(self, tags: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in tags:
            value = " ".join(str(raw or "").split()).strip()
            if not value:
                continue
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(value)
        return normalized

    def _series_tag_kind(self, kind: ItemKind) -> str:
        return f"series_tag:{kind.value}"

    def _character_appearance_role(self, source_role: str | None) -> str:
        normalized = (source_role or "").strip().casefold()
        if "cameo" in normalized or "guest" in normalized:
            return "cameo"
        if "support" in normalized:
            return "supporting"
        if "main" in normalized or "lead" in normalized or "protagonist" in normalized:
            return "main"
        return "main"

    def _character_role_rank(self, role: str) -> int:
        if role == "main":
            return 3
        if role == "supporting":
            return 2
        if role == "cameo":
            return 1
        return 0

    def _comicvine_credit_provider_id(
        self,
        credit: NormalizedCredit,
        *,
        resource: str,
    ) -> str | None:
        for url in (credit.api_detail_url, credit.site_detail_url):
            if not url:
                continue
            match = re.search(rf"/{resource}/(?P<id>\d+-\d+)(?:/|$)", url)
            if match:
                return match.group("id")
        return None

    def _sort_key(self, kind: ItemKind, title: str, item_number: str | None) -> str:
        media_type = media_type_for_kind(kind)
        padding = media_type.item_number_sort_padding if media_type else None
        normalized_number = item_number or ""
        if padding and normalized_number:
            normalized_number = normalized_number.zfill(padding)
        return f"{self._slug(title)}-{normalized_number}".strip("-")

    def _slug(self, value: str) -> str:
        return "-".join("".join(char.lower() if char.isalnum() else " " for char in value).split())

    async def _count(self, model: type) -> int:
        return int(await self.db.scalar(select(func.count()).select_from(model)) or 0)

    async def _item_counts_by_kind(self) -> dict[str, int]:
        result = await self.db.execute(select(Item.kind, func.count(Item.id)).group_by(Item.kind))
        counts = {kind.value: 0 for kind in ItemKind}
        for kind, count in result.all():
            key = kind.value if isinstance(kind, ItemKind) else str(kind)
            counts[key] = int(count)
        return counts

    async def _count_image_assets(self) -> int:
        return await self._count(ImageAsset)

    async def _count_pending_proposals(self) -> int:
        return int(
            await self.db.scalar(
                select(func.count())
                .select_from(MetadataProposal)
                .where(MetadataProposal.status == "pending")
            )
            or 0
        )

    async def _count_missing_cover_items(self) -> int:
        has_cover = (
            select(Variant.id)
            .join(Edition, Variant.edition_id == Edition.id)
            .where(
                Edition.item_id == Item.id,
                or_(
                    Variant.cover_image_url.is_not(None),
                    Variant.thumbnail_image_url.is_not(None),
                    Variant.cover_image_key.is_not(None),
                    Variant.thumbnail_image_key.is_not(None),
                ),
            )
            .exists()
        )
        return int(
            await self.db.scalar(select(func.count()).select_from(Item).where(~has_cover)) or 0
        )

    async def _count_missing_provider_link_items(self) -> int:
        has_provider_link = exists().where(
            ExternalProviderId.entity_type == "item",
            ExternalProviderId.entity_id == Item.id,
        )
        return int(
            await self.db.scalar(select(func.count()).select_from(Item).where(~has_provider_link))
            or 0
        )

    async def _duplicate_group_count(self) -> int:
        return len(await self.duplicate_candidates(limit=200))

    async def _items_by_ids(self, item_ids: list[UUID]) -> list[Item]:
        unique_ids = list(dict.fromkeys(item_ids))
        result = await self.db.execute(
            select(Item)
            .options(
                selectinload(Item.volume).selectinload(Volume.series),
                selectinload(Item.editions).selectinload(Edition.variants),
            )
            .where(Item.id.in_(unique_ids))
        )
        items_by_id = {item.id: item for item in result.scalars().unique()}
        return [items_by_id[item_id] for item_id in unique_ids if item_id in items_by_id]

    def _ensure_same_duplicate_group(self, items: list[Item]) -> None:
        if len(items) < 2:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="duplicate_action_requires_multiple_items",
                detail="Duplicate action requires at least two items",
            )
        first = items[0]
        signature = (first.kind, first.title, first.item_number)
        if any((item.kind, item.title, item.item_number) != signature for item in items[1:]):
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="duplicate_group_mismatch",
                detail="Duplicate action items must belong to the same candidate group",
            )

    async def _duplicate_group_is_ignored(self, item_ids: list[UUID]) -> bool:
        if len(item_ids) < 2:
            return False
        token = self._duplicate_ignore_token(item_ids)
        result = await self.db.execute(select(Item.metadata_json).where(Item.id.in_(item_ids)))
        metadata_rows = list(result.scalars())
        if len(metadata_rows) != len(item_ids):
            return False
        return all(
            isinstance(metadata, dict) and metadata.get("admin_duplicate_ignore_token") == token
            for metadata in metadata_rows
        )

    async def _duplicate_conflict_flags(self, item_ids: list[UUID]) -> dict[str, bool]:
        provider_result = await self.db.execute(
            select(ExternalProviderId.provider, ExternalProviderId.provider_item_id)
            .where(
                ExternalProviderId.entity_type == "item",
                ExternalProviderId.entity_id.in_(item_ids),
            )
            .order_by(ExternalProviderId.provider, ExternalProviderId.provider_item_id)
        )
        provider_ids_by_provider: dict[str, set[str]] = {}
        for provider, provider_item_id in provider_result.all():
            provider_ids_by_provider.setdefault(str(provider), set()).add(provider_item_id)
        has_provider_conflicts = any(len(ids) > 1 for ids in provider_ids_by_provider.values())

        cover_result = await self.db.execute(
            select(
                Variant.cover_image_url,
                Variant.thumbnail_image_url,
                Variant.cover_image_key,
                Variant.thumbnail_image_key,
            )
            .join(Edition, Variant.edition_id == Edition.id)
            .where(Edition.item_id.in_(item_ids))
        )
        cover_signatures = {
            tuple(value for value in row if value) for row in cover_result.all() if any(row)
        }
        return {
            "provider": has_provider_conflicts,
            "cover": len(cover_signatures) > 1,
        }

    async def _score_duplicate_candidate(
        self,
        item_ids: list[UUID],
        *,
        conflicts: dict[str, bool],
    ) -> tuple[int, UUID | None]:
        items = await self._items_by_ids(item_ids)
        if len(items) < 2:
            return 0, None
        provider_counts = await self._provider_link_counts_by_item(item_ids)

        score = 55
        if not conflicts["provider"]:
            score += 12
        if not conflicts["cover"]:
            score += 8
        if provider_counts:
            score += 6
        if len(provider_counts) == len(items):
            score += 4
        if self._duplicate_items_share_publisher(items):
            score += 6
        if self._duplicate_items_share_release_marker(items):
            score += 5

        recommended_target_item_id = max(
            items,
            key=lambda item: self._duplicate_merge_target_score(
                item,
                provider_counts.get(item.id, 0),
            ),
        ).id
        return min(score, 99), recommended_target_item_id

    async def _provider_link_counts_by_item(self, item_ids: list[UUID]) -> dict[UUID, int]:
        result = await self.db.execute(
            select(ExternalProviderId.entity_id, func.count(ExternalProviderId.id))
            .where(
                ExternalProviderId.entity_type == "item",
                ExternalProviderId.entity_id.in_(item_ids),
            )
            .group_by(ExternalProviderId.entity_id)
        )
        return {entity_id: count for entity_id, count in result.all()}

    def _duplicate_merge_target_score(self, item: Item, provider_link_count: int) -> tuple[int, int, int]:
        edition_count = len(item.editions)
        variant_count = sum(len(edition.variants) for edition in item.editions)
        score = provider_link_count * 25
        if self._item_has_cover(item):
            score += 14
        if self._item_has_release_marker(item):
            score += 8
        if self._item_has_publisher(item):
            score += 6
        score += edition_count * 3
        score += min(variant_count, 4)
        return score, provider_link_count, edition_count

    def _duplicate_items_share_publisher(self, items: list[Item]) -> bool:
        publishers = [self._item_primary_publisher(item) for item in items]
        return all(publisher is not None for publisher in publishers) and len(set(publishers)) == 1

    def _duplicate_items_share_release_marker(self, items: list[Item]) -> bool:
        markers = [self._item_release_marker(item) for item in items]
        return all(marker is not None for marker in markers) and len(set(markers)) == 1

    def _item_has_cover(self, item: Item) -> bool:
        for edition in item.editions:
            for variant in edition.variants:
                if any(
                    (
                        variant.cover_image_url,
                        variant.thumbnail_image_url,
                        variant.cover_image_key,
                        variant.thumbnail_image_key,
                    )
                ):
                    return True
        return False

    def _item_has_release_marker(self, item: Item) -> bool:
        return self._item_release_marker(item) is not None

    def _item_has_publisher(self, item: Item) -> bool:
        return self._item_primary_publisher(item) is not None

    def _item_primary_publisher(self, item: Item) -> str | None:
        for edition in item.editions:
            if edition.publisher and edition.publisher.strip():
                return edition.publisher.strip().lower()
        return None

    def _item_release_marker(self, item: Item) -> str | None:
        for edition in item.editions:
            if edition.release_date is not None:
                return edition.release_date.isoformat()
        return None

    def _duplicate_ignore_token(self, item_ids: list[UUID]) -> str:
        return "|".join(sorted(str(item_id) for item_id in item_ids))

    async def _move_item_children(self, source_item: Item, target_item: Item) -> None:
        editions = await self.db.scalars(
            select(Edition).where(Edition.item_id == source_item.id)
        )
        for edition in editions:
            edition.item = target_item

        await self.db.execute(
            update(ExternalProviderId)
            .where(
                ExternalProviderId.entity_type == "item",
                ExternalProviderId.entity_id == source_item.id,
            )
            .values(entity_id=target_item.id)
        )

        await self._move_organization_links(source_item.id, target_item.id)
        await self._move_person_links(source_item.id, target_item.id)
        await self._move_story_arc_links(source_item.id, target_item.id)
        await self._move_character_appearance_links(source_item.id, target_item.id)
        await self._move_tag_links(source_item.id, target_item.id)

        await self.db.execute(
            update(ImageAsset)
            .where(
                ImageAsset.entity_type == "item",
                ImageAsset.entity_id == source_item.id,
            )
            .values(entity_id=target_item.id)
        )

    async def _move_organization_links(self, source_item_id: UUID, target_item_id: UUID) -> None:
        links = await self.db.scalars(
            select(EntityOrganization).where(
                EntityOrganization.entity_type == "item",
                EntityOrganization.entity_id == source_item_id,
            )
        )
        for link in links:
            exists = await self.db.scalar(
                select(EntityOrganization.id).where(
                    EntityOrganization.entity_type == "item",
                    EntityOrganization.entity_id == target_item_id,
                    EntityOrganization.organization_id == link.organization_id,
                    EntityOrganization.role == link.role,
                )
            )
            if exists:
                await self.db.delete(link)
            else:
                link.entity_id = target_item_id

    async def _move_person_links(self, source_item_id: UUID, target_item_id: UUID) -> None:
        links = await self.db.scalars(
            select(EntityPerson).where(
                EntityPerson.entity_type == "item",
                EntityPerson.entity_id == source_item_id,
            )
        )
        for link in links:
            exists = await self.db.scalar(
                select(EntityPerson.id).where(
                    EntityPerson.entity_type == "item",
                    EntityPerson.entity_id == target_item_id,
                    EntityPerson.person_id == link.person_id,
                    EntityPerson.role == link.role,
                )
            )
            if exists:
                await self.db.delete(link)
            else:
                link.entity_id = target_item_id

    async def _move_story_arc_links(self, source_item_id: UUID, target_item_id: UUID) -> None:
        links = await self.db.scalars(
            select(StoryArcItem).where(StoryArcItem.item_id == source_item_id)
        )
        for link in links:
            exists = await self.db.scalar(
                select(StoryArcItem.id).where(
                    StoryArcItem.story_arc_id == link.story_arc_id,
                    StoryArcItem.item_id == target_item_id,
                )
            )
            if exists:
                await self.db.delete(link)
            else:
                link.item_id = target_item_id

    async def _move_character_appearance_links(
        self,
        source_item_id: UUID,
        target_item_id: UUID,
    ) -> None:
        links = await self.db.scalars(
            select(CharacterAppearance).where(CharacterAppearance.item_id == source_item_id)
        )
        for link in links:
            existing = await self.db.scalar(
                select(CharacterAppearance).where(
                    CharacterAppearance.character_id == link.character_id,
                    CharacterAppearance.item_id == target_item_id,
                )
            )
            if existing:
                if self._character_role_rank(link.role) > self._character_role_rank(existing.role):
                    existing.role = link.role
                await self.db.delete(link)
            else:
                link.item_id = target_item_id

    async def _move_tag_links(self, source_item_id: UUID, target_item_id: UUID) -> None:
        links = await self.db.scalars(
            select(EntityTag).where(
                EntityTag.entity_type == "item",
                EntityTag.entity_id == source_item_id,
            )
        )
        for link in links:
            exists = await self.db.scalar(
                select(EntityTag.id).where(
                    EntityTag.entity_type == "item",
                    EntityTag.entity_id == target_item_id,
                    EntityTag.tag_id == link.tag_id,
                )
            )
            if exists:
                await self.db.delete(link)
            else:
                link.entity_id = target_item_id

    async def _search_documents(self) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(Item).options(
                selectinload(Item.volume).selectinload(Volume.series),
                selectinload(Item.primary_bundle_releases),
                selectinload(Item.editions).selectinload(Edition.variants),
            )
        )
        return [item_search_document(item) for item in result.scalars().unique()]

    def _record_search_history(self, response: AdminSearchReindexResponse) -> None:
        _SEARCH_HISTORY.appendleft(
            AdminSearchHistoryEntry(
                timestamp=datetime.now(UTC),
                ok=response.ok,
                index_name=response.index_name,
                indexed_documents=response.indexed_documents,
                error=response.error,
            )
        )

    def _record_ingest_history(
        self,
        *,
        payload: ProviderIngestRequest,
        status: str,
        attempts: int,
        item_id: UUID | None = None,
        error: str | None = None,
    ) -> None:
        global _INGEST_HISTORY_SEQUENCE
        _INGEST_HISTORY_SEQUENCE += 1
        _INGEST_HISTORY.appendleft(
            ProviderIngestHistoryEntry(
                id=_INGEST_HISTORY_SEQUENCE,
                timestamp=datetime.now(UTC),
                provider=payload.provider,
                provider_item_id=payload.provider_item_id,
                status=status,
                attempts=attempts,
                item_id=item_id,
                error=error,
            )
        )

    async def _provider_ingest_success_count(self) -> int:
        job_count = await self._count_ingest_jobs("done")
        memory_count = sum(
            1 for entry in _INGEST_HISTORY if entry.status in {"created", "existing"}
        )
        return job_count + memory_count

    async def _provider_ingest_failure_count(self) -> int:
        job_count = await self._count_ingest_jobs("failed")
        memory_count = sum(1 for entry in _INGEST_HISTORY if entry.status == "failed")
        return job_count + memory_count

    async def _count_ingest_jobs(self, status_filter: str) -> int:
        return int(
            await self.db.scalar(
                select(func.count())
                .select_from(ProviderIngestJob)
                .where(ProviderIngestJob.status == status_filter)
            )
            or 0
        )

    def _primary_edition_model(self, item: Item) -> Edition | None:
        editions = list(item.editions or [])
        return editions[0] if editions else None

    def _primary_variant_model(self, item: Item) -> Variant | None:
        for edition in item.editions or []:
            variants = list(edition.variants or [])
            primary = next((variant for variant in variants if variant.is_primary), None)
            if primary is not None:
                return primary
            if variants:
                return variants[0]
        return None

    def _record_admin_audit(
        self,
        action: str,
        entity_type: str,
        entity_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.db.add(
            AdminAuditLog(
                action=action,
                actor_user_id=self.actor_user_id,
                actor_email=self.actor_email,
                entity_type=entity_type,
                entity_id=entity_id,
                details_json=self._audit_json_safe(details or {}),
            )
        )

    def _ingest_job_audit_details(self, job: ProviderIngestJob) -> dict[str, Any]:
        return {
            "provider": job.provider,
            "provider_item_id": job.provider_item_id,
            "status": job.status,
            "attempts": job.attempts,
            "max_attempts": job.max_attempts,
            "item_id": job.item_id,
            "last_error": job.last_error,
        }

    def _audit_json_safe(self, value: Any) -> Any:
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, datetime | date):
            return value.isoformat()
        if isinstance(value, PythonEnum):
            return value.value
        if isinstance(value, dict):
            return {str(key): self._audit_json_safe(item) for key, item in value.items()}
        if isinstance(value, list | tuple | set):
            return [self._audit_json_safe(item) for item in value]
        return value

    async def _reindex_items(self, item_ids: set[UUID]) -> None:
        documents: list[dict[str, Any]] = []
        repository = MetadataRepository(self.db)
        for item_id in item_ids:
            loaded_item = await repository.get_item(item_id)
            if loaded_item is not None:
                documents.append(item_search_document(loaded_item))
        if documents:
            await SearchClient().index_documents_best_effort(documents)

    def _backoff_delay(self, attempts: int) -> timedelta:
        return timedelta(seconds=min(300, 5 * (2 ** max(0, attempts - 1))))

    def _is_retryable_ingest_error(self, error: Exception) -> bool:
        if isinstance(error, HTTPException):
            return error.status_code in {
                status.HTTP_429_TOO_MANY_REQUESTS,
                status.HTTP_502_BAD_GATEWAY,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                status.HTTP_504_GATEWAY_TIMEOUT,
            }
        return False

    def _error_message(self, error: Exception) -> str:
        if isinstance(error, HTTPException):
            return str(error.detail)
        return str(error)

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    async def list_users(self) -> list:
        from app.schemas.admin import UserResponse

        result = await self.db.execute(
            select(User).order_by(User.created_at.desc())
        )
        return [UserResponse.model_validate(u) for u in result.scalars()]

    async def get_user(self, user_id: UUID) -> Any:
        from app.schemas.admin import UserResponse

        user = await self.db.get(User, user_id)
        if user is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="user_not_found",
                detail="User not found",
            )
        return UserResponse.model_validate(user)

    async def update_user(self, user_id: UUID, payload: Any) -> Any:
        from app.models.base import UserRole
        from app.schemas.admin import UserResponse

        user = await self.db.get(User, user_id)
        if user is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="user_not_found",
                detail="User not found",
            )
        if payload.role is not None:
            user.role = payload.role
            user.is_admin = payload.role == UserRole.admin
        if payload.is_active is not None:
            user.is_active = payload.is_active
        if payload.display_name is not None:
            user.display_name = payload.display_name
        await self.db.commit()
        await self.db.refresh(user)
        self._record_admin_audit(
            "update_user",
            "user",
            entity_id=user.id,
            details=payload.model_dump(exclude_none=True),
        )
        await self.db.commit()
        return UserResponse.model_validate(user)

    async def image_cache_stats(self) -> Any:
        from sqlalchemy import func, select

        from app.core.config import get_settings
        from app.models.canonical import ImageCacheEntry
        from app.schemas.admin import ImageCacheStatsResponse

        settings = get_settings()
        total_entries = await self.db.scalar(
            select(func.count()).select_from(ImageCacheEntry)
        ) or 0
        total_size = await self.db.scalar(
            select(func.coalesce(func.sum(ImageCacheEntry.size_bytes), 0))
        ) or 0
        max_bytes = settings.image_cache_max_bytes
        usage_pct = (total_size / max_bytes * 100) if max_bytes > 0 else 0.0

        rows = await self.db.execute(
            select(ImageCacheEntry.provider, func.count())
            .group_by(ImageCacheEntry.provider)
        )
        providers = {row[0]: row[1] for row in rows}

        return ImageCacheStatsResponse(
            total_entries=int(total_entries),
            total_size_bytes=int(total_size),
            max_size_bytes=max_bytes,
            usage_percent=round(usage_pct, 1),
            mirroring_enabled=settings.mirror_provider_images,
            providers=providers,
        )

    async def purge_image_cache(self, provider: str | None = None) -> Any:
        from sqlalchemy import delete, select

        from app.models.canonical import ImageCacheEntry
        from app.schemas.admin import ImageCachePurgeResponse
        from app.storage.client import ObjectStorage

        query = select(ImageCacheEntry)
        if provider:
            query = query.where(ImageCacheEntry.provider == provider)
        entries = list((await self.db.scalars(query)).all())
        if not entries:
            return ImageCachePurgeResponse(deleted_entries=0, freed_bytes=0)

        keys = [e.object_key for e in entries]
        freed = sum(e.size_bytes for e in entries)
        try:
            storage = ObjectStorage.shared()
            storage.delete_objects(keys)
        except Exception:
            logger.warning("Failed to delete objects from storage during purge", exc_info=True)

        del_stmt = delete(ImageCacheEntry)
        if provider:
            del_stmt = del_stmt.where(ImageCacheEntry.provider == provider)
        await self.db.execute(del_stmt)

        self._record_admin_audit(
            "purge_image_cache",
            "image_cache",
            details={"provider": provider, "deleted": len(entries), "freed_bytes": freed},
        )
        await self.db.commit()
        return ImageCachePurgeResponse(deleted_entries=len(entries), freed_bytes=freed)
