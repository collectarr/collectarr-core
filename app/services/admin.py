from collections import deque
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.catalog.media_types import media_type_for_kind
from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import (
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
    Release,
    Series,
    Tag,
    Variant,
    Volume,
)
from app.providers.base import MetadataProvider, NormalizedCredit
from app.providers.registry import ProviderRegistry
from app.repositories.metadata import MetadataRepository
from app.schemas.admin import (
    AdminCatalogSummaryResponse,
    AdminDuplicateActionResponse,
    AdminDuplicateCandidateResponse,
    AdminDuplicateIgnoreRequest,
    AdminDuplicateMergeRequest,
    AdminMetadataCorrectionRequest,
    AdminSearchHistoryEntry,
    AdminSearchReindexResponse,
    AdminSearchStatusResponse,
    ProviderIngestHistoryEntry,
    ProviderIngestJobCreateRequest,
    ProviderIngestJobResponse,
    ProviderIngestJobRunResponse,
    ProviderIngestRequest,
    ProviderIngestRetryRequest,
    ProviderIngestResponse,
    MetadataProposalAdminResponse,
    MetadataProposalSummaryResponse,
    ProviderSearchRequest,
    ProviderStatusResponse,
)
from app.schemas.metadata import item_response_from_model
from app.search.client import SearchClient
from app.search.documents import item_search_document
from app.storage.image_cache import ImageCache
from app.storage.images import ImageMirror


_SEARCH_HISTORY: deque[AdminSearchHistoryEntry] = deque(maxlen=20)
_INGEST_HISTORY: deque[ProviderIngestHistoryEntry] = deque(maxlen=50)
_INGEST_HISTORY_SEQUENCE = 0


class AdminMetadataService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.providers = ProviderRegistry()
        self.settings = get_settings()

    async def provider_statuses(self) -> list[ProviderStatusResponse]:
        statuses: list[ProviderStatusResponse] = []
        for provider in self.providers.all():
            capabilities = provider.capabilities
            statuses.append(
                ProviderStatusResponse(
                    name=provider.name,
                    display_name=capabilities.display_name,
                    kind=capabilities.kind.value,
                    status="live" if provider.is_configured else "stub",
                    is_configured=provider.is_configured,
                    supports_search=capabilities.supports_search,
                    supports_ingest=capabilities.supports_ingest,
                    requires_user_key=capabilities.requires_user_key,
                    non_commercial_only=capabilities.non_commercial_only,
                    allows_redistribution=capabilities.allows_redistribution,
                    requires_attribution=capabilities.requires_attribution,
                    license_name=capabilities.license_name,
                    terms_url=capabilities.terms_url,
                    attribution_url=capabilities.attribution_url,
                    rate_limit=capabilities.rate_limit,
                    cache_policy=capabilities.cache_policy,
                    message=provider.status_message,
                )
            )
        return statuses

    async def catalog_summary(self) -> AdminCatalogSummaryResponse:
        duplicate_groups = await self._duplicate_group_count()
        return AdminCatalogSummaryResponse(
            items=await self._count(Item),
            series=await self._count(Series),
            volumes=await self._count(Volume),
            editions=await self._count(Edition),
            variants=await self._count(Variant),
            releases=await self._count(Release),
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
        except Exception as exc:
            return AdminSearchStatusResponse(
                ok=False,
                index_name=SearchClient.index_name,
                error=str(exc),
            )
        document_count = stats.get("numberOfDocuments")
        if isinstance(document_count, str):
            try:
                document_count = int(document_count)
            except ValueError:
                document_count = None
        if not isinstance(document_count, int):
            document_count = None
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
        return [item_response_from_model(item) for item in items]

    async def update_catalog_item(
        self,
        item_id: UUID,
        payload: AdminMetadataCorrectionRequest,
        kind: ItemKind | None = None,
    ) -> Any:
        item = await MetadataRepository(self.db).get_item(item_id, kind)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        update_data = payload.model_dump(exclude_unset=True)
        if "title" in update_data and payload.title is not None:
            item.title = payload.title
        if "item_number" in update_data:
            item.item_number = payload.item_number
        if "synopsis" in update_data:
            item.synopsis = payload.synopsis
        if "page_count" in update_data:
            item.page_count = payload.page_count
        item.sort_key = self._sort_key(item.kind, item.title, item.item_number)

        edition = self._primary_edition_model(item)
        if edition is not None:
            if "publisher" in update_data:
                edition.publisher = payload.publisher
            if "release_date" in update_data:
                edition.release_date = payload.release_date

        variant = self._primary_variant_model(item)
        if variant is not None:
            if "variant_name" in update_data and payload.variant_name is not None:
                variant.name = payload.variant_name
            if "barcode" in update_data:
                variant.barcode = payload.barcode
            if "cover_image_url" in update_data:
                variant.cover_image_url = payload.cover_image_url
            if "thumbnail_image_url" in update_data:
                variant.thumbnail_image_url = payload.thumbnail_image_url

        metadata = dict(item.metadata_json or {})
        metadata["admin_corrected_at"] = datetime.now(UTC).isoformat()
        metadata["admin_corrected_fields"] = sorted(update_data.keys())
        item.metadata_json = metadata
        await self.db.commit()
        loaded_item = await MetadataRepository(self.db).get_item(item.id)
        if loaded_item:
            await SearchClient().index_documents_best_effort([item_search_document(loaded_item)])
        return item_response_from_model(loaded_item)

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
                )
            )
            if len(candidates) >= limit:
                break
        return candidates

    async def ignore_duplicate_candidate(
        self, payload: AdminDuplicateIgnoreRequest
    ) -> AdminDuplicateActionResponse:
        items = await self._items_by_ids(payload.item_ids)
        if len(items) != len(set(payload.item_ids)):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more duplicate items were not found",
            )
        self._ensure_same_duplicate_group(items)
        token = self._duplicate_ignore_token([item.id for item in items])
        for item in items:
            metadata = dict(item.metadata_json or {})
            metadata["admin_duplicate_ignore_token"] = token
            metadata["admin_duplicate_ignored_at"] = datetime.now(UTC).isoformat()
            item.metadata_json = metadata
        await self.db.commit()
        return AdminDuplicateActionResponse(ok=True, affected_items=len(items))

    async def merge_duplicate_candidate(
        self, payload: AdminDuplicateMergeRequest
    ) -> AdminDuplicateActionResponse:
        source_ids = [
            item_id for item_id in payload.source_item_ids if item_id != payload.target_item_id
        ]
        if not source_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one source item different from target_item_id is required",
            )
        items = await self._items_by_ids([payload.target_item_id, *source_ids])
        if len(items) != len({payload.target_item_id, *source_ids}):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more duplicate items were not found",
            )
        target = next(item for item in items if item.id == payload.target_item_id)
        sources = [item for item in items if item.id != payload.target_item_id]
        self._ensure_same_duplicate_group([target, *sources])

        for source in sources:
            await self._move_item_children(source.id, target.id)
            await self.db.delete(source)
        await self.db.commit()

        loaded_item = await MetadataRepository(self.db).get_item(target.id)
        if loaded_item is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Merged target item could not be loaded",
            )
        return AdminDuplicateActionResponse(
            ok=True,
            affected_items=len(sources),
            item=item_response_from_model(loaded_item),
        )

    async def provider_search(self, payload: ProviderSearchRequest) -> list[dict[str, Any]]:
        provider = self._provider(payload.provider)
        if not provider.capabilities.supports_search:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Provider '{payload.provider.value}' does not support search",
            )
        if payload.kind is not None and provider.capabilities.kind != payload.kind:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Provider '{payload.provider.value}' does not support "
                    f"kind '{payload.kind.value}'"
                ),
            )
        results = await provider.search(payload.query)
        return [result.__dict__ for result in results]

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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
        if proposal.provider_item_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Proposal does not have a provider item id",
            )
        response = await self.ingest(
            ProviderIngestRequest(
                provider=proposal.provider,
                provider_item_id=proposal.provider_item_id,
            )
        )
        proposal.status = "approved"
        await self.db.commit()
        return response

    async def approve_proposal_with_provider_item(
        self,
        proposal_id: UUID,
        payload: ProviderIngestRequest,
    ) -> ProviderIngestResponse:
        proposal = await self.db.get(MetadataProposal, proposal_id)
        if proposal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
        response = await self.ingest(payload)
        proposal.provider = payload.provider
        proposal.provider_item_id = payload.provider_item_id
        proposal.status = "approved"
        await self.db.commit()
        return response

    async def reject_proposal(self, proposal_id: UUID) -> MetadataProposalAdminResponse:
        proposal = await self.db.get(MetadataProposal, proposal_id)
        if proposal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
        proposal.status = "rejected"
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
        await self.db.commit()
        await self.db.refresh(job)
        return ProviderIngestJobResponse.model_validate(job)

    async def ingest_jobs(
        self,
        status_filter: str | None = None,
        limit: int = 25,
    ) -> list[ProviderIngestJobResponse]:
        stmt = select(ProviderIngestJob).order_by(
            ProviderIngestJob.created_at.desc(),
            ProviderIngestJob.id.desc(),
        )
        if status_filter:
            stmt = stmt.where(ProviderIngestJob.status == status_filter)
        result = await self.db.execute(stmt.limit(limit))
        return [ProviderIngestJobResponse.model_validate(job) for job in result.scalars().all()]

    async def run_ingest_job(self, job_id: UUID) -> ProviderIngestJobResponse:
        job = await self.db.get(ProviderIngestJob, job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Ingest job not found"
            )
        if job.status == "running":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ingest job is already running",
            )
        return ProviderIngestJobResponse.model_validate(await self._execute_ingest_job(job))

    async def retry_ingest_job(self, job_id: UUID) -> ProviderIngestJobResponse:
        job = await self.db.get(ProviderIngestJob, job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Ingest job not found"
            )
        if job.status == "running":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ingest job is already running",
            )
        job.status = "queued"
        job.next_run_at = datetime.now(UTC)
        job.last_error = None
        await self.db.commit()
        await self.db.refresh(job)
        return ProviderIngestJobResponse.model_validate(await self._execute_ingest_job(job))

    async def run_pending_ingest_jobs(self, limit: int = 5) -> ProviderIngestJobRunResponse:
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
        return ProviderIngestJobRunResponse(processed=len(processed), jobs=processed)

    def ingest_history(self) -> list[ProviderIngestHistoryEntry]:
        return list(_INGEST_HISTORY)

    async def retry_ingest(self, payload: ProviderIngestRetryRequest) -> ProviderIngestResponse:
        entry = next(
            (entry for entry in _INGEST_HISTORY if entry.id == payload.history_id),
            None,
        )
        if entry is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider ingest history entry not found",
            )
        if entry.status != "failed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only failed provider ingest entries can be retried",
            )
        return await self.ingest(
            ProviderIngestRequest(
                provider=entry.provider,
                provider_item_id=entry.provider_item_id,
            )
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
                return response
            except Exception as exc:
                last_error = exc
                await self.db.rollback()
                if attempt >= attempts or not self._is_retryable_ingest_error(exc):
                    self._record_ingest_history(
                        payload=payload,
                        status="failed",
                        attempts=attempt,
                        error=self._error_message(exc),
                    )
                    raise
        raise RuntimeError("Provider ingest retry loop exited unexpectedly") from last_error

    async def _ingest_once(self, payload: ProviderIngestRequest) -> ProviderIngestResponse:
        provider = self._provider(payload.provider)
        self._ensure_provider_ingest_supported(provider, payload.provider)
        existing_provider_id = await self._get_provider_id(payload)
        if existing_provider_id:
            return await self._existing_response(existing_provider_id)

        provider_item = await provider.get_item(payload.provider_item_id)
        existing_provider_id = await self._get_provider_id_value(
            payload.provider, provider_item.provider_item_id
        )
        if existing_provider_id:
            return await self._existing_response(existing_provider_id)

        normalized = await provider.normalize(
            dict(provider_item.raw) | {"id": provider_item.provider_item_id}
        )
        volume = await self._upsert_volume(
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
            page_count=normalized.page_count,
            metadata_json={
                "provider": payload.provider.value,
                "provider_item_id": provider_item.provider_item_id,
                "normalized": {
                    "kind": normalized.kind.value,
                    "series_title": normalized.series_title,
                    "volume_name": normalized.volume_name,
                    "volume_number": normalized.volume_number,
                    "volume_start_year": normalized.volume_start_year,
                    "story_arcs": [credit.name for credit in normalized.story_arcs],
                },
            },
        )
        edition = Edition(
            item=item,
            title=normalized.edition_title or "Standard Edition",
            format=normalized.edition_format,
            publisher=normalized.publisher,
            isbn=normalized.isbn,
            release_date=normalized.release_date,
            metadata_json={
                "provider": payload.provider.value,
                "provider_item_id": provider_item.provider_item_id,
                "normalized": {
                    "title": normalized.edition_title or "Standard Edition",
                    "format": normalized.edition_format,
                    "publisher": normalized.publisher,
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
                },
                "source": provider_item.raw,
            },
        )
        mirrored_cover = None
        if self.settings.mirror_provider_images:
            mirrored_cover = await ImageMirror().mirror_cover_best_effort(
                normalized.cover_image_url,
                payload.provider.value,
                provider_item.provider_item_id,
            )
        variant = Variant(
            edition=edition,
            name=normalized.variant_name or "Cover A",
            variant_type=normalized.variant_type,
            barcode=normalized.barcode,
            isbn=normalized.isbn,
            cover_price_cents=normalized.cover_price_cents,
            currency=normalized.currency,
            cover_image_key=mirrored_cover.key if mirrored_cover else None,
            cover_image_url=mirrored_cover.url if mirrored_cover else normalized.cover_image_url,
            thumbnail_image_key=mirrored_cover.thumbnail_key if mirrored_cover else None,
            thumbnail_image_url=mirrored_cover.thumbnail_url if mirrored_cover else None,
            metadata_json={
                "provider": payload.provider.value,
                "provider_item_id": provider_item.provider_item_id,
                "normalized": {
                    "name": normalized.variant_name or "Cover A",
                    "variant_type": normalized.variant_type,
                    "barcode": normalized.barcode,
                    "isbn": normalized.isbn,
                    "cover_price_cents": normalized.cover_price_cents,
                    "currency": normalized.currency,
                    "cover_image_url": normalized.cover_image_url,
                },
            },
            is_primary=True,
        )
        release = Release(
            edition=edition,
            region="US",
            release_date=normalized.release_date,
            publisher=normalized.publisher,
            external_ids=normalized.provider_ids,
            metadata_json={
                "provider": payload.provider.value,
                "provider_item_id": provider_item.provider_item_id,
                "normalized": {
                    "release_date": (
                        normalized.release_date.isoformat() if normalized.release_date else None
                    ),
                    "publisher": normalized.publisher,
                    "external_ids": normalized.provider_ids,
                },
            },
        )
        self.db.add_all([item, edition, variant, release])
        await self.db.flush()
        if mirrored_cover:
            await ImageCache(self.db).record_mirrored_cover(mirrored_cover)
        await self._add_provider_links(payload.provider, normalized.provider_ids, "item", item.id)
        if volume:
            await self._add_provider_links(
                payload.provider, normalized.volume_provider_ids, "volume", volume.id
            )
        await self._link_publisher(item.id, normalized.publisher)
        await self._link_people(item.id, normalized.creators)
        await self._link_tags(item.id, "character", normalized.characters)
        await self._link_tags(item.id, "story_arc", normalized.story_arcs)
        await self.db.commit()
        loaded_item = await MetadataRepository(self.db).get_item(item.id)
        if loaded_item:
            await SearchClient().index_documents_best_effort([item_search_document(loaded_item)])
        return ProviderIngestResponse(
            item_id=item.id,
            created=True,
            item=item_response_from_model(loaded_item),
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
            return refreshed

        refreshed = await self.db.get(ProviderIngestJob, job_id)
        if refreshed is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ingest job disappeared during execution",
            )
        refreshed.status = "done"
        refreshed.item_id = response.item_id
        refreshed.last_error = None
        refreshed.next_run_at = None
        await self.db.commit()
        await self.db.refresh(refreshed)
        return refreshed

    def _provider(self, provider: ExternalProvider) -> MetadataProvider:
        try:
            return self.providers.get(provider.value)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Provider '{provider.value}' is not configured",
            ) from exc

    def _ensure_provider_ingest_supported(
        self,
        provider: MetadataProvider,
        provider_name: ExternalProvider,
    ) -> None:
        if provider.capabilities.supports_ingest:
            return
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{provider_name.value}' does not support catalog ingest yet",
        )

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
        item = await MetadataRepository(self.db).get_item(provider_id.entity_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Provider link is stale"
            )
        return ProviderIngestResponse(
            item_id=item.id,
            created=False,
            item=item_response_from_model(item),
        )

    async def _upsert_volume(
        self,
        kind: ItemKind,
        series_title: str | None,
        volume_name: str | None,
        volume_start_year: int | None,
    ) -> Volume | None:
        if not series_title and not volume_name:
            return None

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
        return volume

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
    ) -> None:
        provider_id = provider_ids.get(provider.value)
        if not provider_id:
            return
        exists = await self.db.scalar(
            select(ExternalProviderId.id).where(
                ExternalProviderId.provider == provider,
                ExternalProviderId.provider_item_id == provider_id,
            )
        )
        if exists:
            return
        self.db.add(
            ExternalProviderId(
                provider=provider,
                provider_item_id=provider_id,
                entity_type=entity_type,
                entity_id=entity_id,
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

    async def _link_people(self, item_id: UUID, credits: list[NormalizedCredit]) -> None:
        for credit in credits:
            person = await self._get_or_create_person(credit.name)
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

    async def _get_or_create_person(self, name: str) -> Person:
        result = await self.db.execute(select(Person).where(Person.name == name))
        person = result.scalar_one_or_none()
        if person is None:
            person = Person(name=name)
            self.db.add(person)
            await self.db.flush()
        return person

    async def _get_or_create_tag(self, kind: str, name: str) -> Tag:
        result = await self.db.execute(select(Tag).where(Tag.kind == kind, Tag.name == name))
        tag = result.scalar_one_or_none()
        if tag is None:
            tag = Tag(kind=kind, name=name)
            self.db.add(tag)
            await self.db.flush()
        return tag

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
            )
            .where(Item.id.in_(unique_ids))
        )
        return list(result.scalars().unique())

    def _ensure_same_duplicate_group(self, items: list[Item]) -> None:
        if len(items) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate action requires at least two items",
            )
        first = items[0]
        signature = (first.kind, first.title, first.item_number)
        if any((item.kind, item.title, item.item_number) != signature for item in items[1:]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
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

    def _duplicate_ignore_token(self, item_ids: list[UUID]) -> str:
        return "|".join(sorted(str(item_id) for item_id in item_ids))

    async def _move_item_children(self, source_item_id: UUID, target_item_id: UUID) -> None:
        await self.db.execute(
            update(Edition).where(Edition.item_id == source_item_id).values(item_id=target_item_id)
        )

        await self.db.execute(
            update(ExternalProviderId)
            .where(
                ExternalProviderId.entity_type == "item",
                ExternalProviderId.entity_id == source_item_id,
            )
            .values(entity_id=target_item_id)
        )

        await self._move_organization_links(source_item_id, target_item_id)
        await self._move_person_links(source_item_id, target_item_id)
        await self._move_tag_links(source_item_id, target_item_id)

        await self.db.execute(
            update(ImageAsset)
            .where(
                ImageAsset.entity_type == "item",
                ImageAsset.entity_id == source_item_id,
            )
            .values(entity_id=target_item_id)
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
                selectinload(Item.editions).selectinload(Edition.variants),
                selectinload(Item.editions).selectinload(Edition.releases),
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
