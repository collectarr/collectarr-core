import contextlib
import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import selectinload

from app.catalog.physical_formats import (
    PhysicalFormatConfig,
)
from app.catalog.provider_field_states import provider_preview_field_states
from app.core.errors import ApiHTTPException
from app.models import (
    AnimeCharacterAppearance,
    AnimeContribution,
    AnimeEpisode,
    AnimeIdentifier,
    AnimeSeries,
    BoardGameEdition,
    BoardGameWork,
    BookContribution,
    BookEdition,
    BookIdentifier,
    BookSeries,
    BookSeriesMembership,
    BookWork,
    Character,
    ComicCharacterAppearance,
    ComicContribution,
    ComicIdentifier,
    ComicIssue,
    ComicSeries,
    ComicSeriesMembership,
    ComicStoryArcMembership,
    ComicWork,
    EntityOrganization,
    EntityPerson,
    ExternalProviderId,
    GameRelease,
    GameWork,
    MangaChapter,
    MangaCharacterAppearance,
    MangaContribution,
    MangaIdentifier,
    MangaSeries,
    MangaSeriesMembership,
    MangaSeriesRelation,
    MangaWork,
    MetadataProposal,
    MovieRelease,
    MovieReleaseMedia,
    MovieWork,
    MovieWorkContribution,
    MovieWorkIdentifier,
    MusicMedia,
    MusicRelease,
    MusicReleaseContribution,
    MusicReleaseIdentifier,
    MusicTrack,
    Organization,
    Person,
    PhysicalFormatRef,
    ProviderIngestJob,
    ProviderPayloadSnapshot,
    ReleaseStatus,
    StoryArc,
    Tag,
    TVEpisode,
    TVRelease,
    TVReleaseContribution,
    TVReleaseEpisodeMap,
    TVReleaseIdentifier,
    TVReleaseMedia,
    TVSeason,
    TVSeries,
)
from app.models.base import ExternalProvider, ItemKind, SeriesRelationType
from app.proposal_payload import compact_metadata_payload
from app.providers.base import (
    MetadataProvider,
    NormalizedCredit,
    NormalizedEpisode,
    NormalizedItem,
    NormalizedRelation,
    NormalizedSeason,
    NormalizedTrack,
    NormalizedVariantCover,
)
from app.providers.comicvine import ComicVineProvider
from app.providers.normalize import normalize_arc_title, normalize_person_name
from app.providers.registry import ProviderRegistry
from app.schemas.admin import (
    MetadataProposalAdminResponse,
    MetadataProposalAdminUpdateRequest,
    MetadataProposalSummaryResponse,
    ProviderBatchHydrateRequest,
    ProviderBatchHydrateResponse,
    ProviderBatchHydrateResultItem,
    ProviderIngestHistoryEntry,
    ProviderIngestJobCreateRequest,
    ProviderIngestJobResponse,
    ProviderIngestJobRunResponse,
    ProviderIngestJobSummaryResponse,
    ProviderIngestRequest,
    ProviderIngestResponse,
    ProviderIngestRetryRequest,
    ProviderPreviewCredit,
    ProviderPreviewResponse,
    ProviderPreviewTrack,
    ProviderSearchRequest,
)
from app.search.client import SearchClient
from app.search.documents import (
    anime_series_search_document,
    boardgame_search_document,
    book_work_search_document,
    comic_work_search_document,
    game_work_search_document,
    manga_work_search_document,
    movie_work_search_document,
    tv_release_search_document,
)
from app.services.admin_domains.provider_ingest_helpers import (
    book_identifier_type,
    comic_identifier_type,
    cover_metadata,
    normalized_identifier,
    normalized_language,
    normalized_region,
    normalized_release_status,
    physical_format_for_normalized,
    provider_metadata_json,
    variant_cover_name,
)
from app.services.admin_domains.shared import (
    character_appearance_role,
    comicvine_credit_provider_id,
    credit_provider_urls,
    provider_link_url_text,
    provider_link_urls_for_provider,
    slug,
    sort_key,
)
from app.services.facade import MetadataFacade as MetadataService
from app.services.provider_preview_state import HydratedProviderPreview
from app.storage.image_cache import ImageCache
from app.storage.images import ImageMirror

logger = logging.getLogger(__name__)
_SNAPSHOT_TTL = timedelta(days=30)


@dataclass(frozen=True)
class CatalogExternalProviderIdRef:
    entity_type: str
    entity_id: UUID
    provider_item_id: str


class AdminProviderIngestService:
    def __init__(
        self,
        *,
        db: Any,
        settings: Any,
        providers: Any,
        provider_preview_state: Any,
        history_reader: Any,
        audit_recorder: Any,
        ingest_job_audit_details: Any,
        record_ingest_history: Any,
        is_retryable_ingest_error: Any,
        error_message: Any,
        reindex_items: Any,
        item_response_loader: Any,
        backoff_delay: Any,
        actor_user_id: UUID | None,
        comicvine_character_details: dict[str, Any],
    ) -> None:
        self.db = db
        self.settings = settings
        self.providers = providers
        self.provider_preview_state = provider_preview_state
        self._history_reader = history_reader
        self._audit_recorder = audit_recorder
        self._ingest_job_audit_details = ingest_job_audit_details
        self._record_ingest_history = record_ingest_history
        self._is_retryable_ingest_error = is_retryable_ingest_error
        self._error_message = error_message
        self._reindex_items = reindex_items
        self._item_response = item_response_loader
        self._backoff_delay = backoff_delay
        self.actor_user_id = actor_user_id
        self._comicvine_character_details = comicvine_character_details

    async def provider_search(self, payload: ProviderSearchRequest) -> list[dict[str, Any]]:
        results = await MetadataService(self.db).search_provider(
            payload.provider,
            payload.query,
            payload.kind,
        )
        return [result.model_dump(mode="json") for result in results]

    async def purge_expired_provider_snapshots(self, *, limit: int = 5000) -> int:
        now = datetime.now(UTC)
        snapshot_ids = list(
            (
                await self.db.execute(
                    select(ProviderPayloadSnapshot.id)
                    .where(
                        ProviderPayloadSnapshot.purged_at.is_(None),
                        ProviderPayloadSnapshot.expires_at.is_not(None),
                        ProviderPayloadSnapshot.expires_at <= now,
                    )
                    .order_by(ProviderPayloadSnapshot.expires_at.asc())
                    .limit(limit)
                )
            ).scalars()
        )
        if not snapshot_ids:
            return 0
        await self.db.execute(
            update(ProviderPayloadSnapshot)
            .where(ProviderPayloadSnapshot.id.in_(snapshot_ids))
            .values(
                source_payload=None,
                normalized_payload=None,
                purged_at=now,
            )
        )
        await self.db.flush()
        return len(snapshot_ids)

    async def proposal_summary(self) -> MetadataProposalSummaryResponse:
        result = await self.db.execute(
            select(MetadataProposal.status, func.count(MetadataProposal.id)).group_by(
                MetadataProposal.status
            )
        )
        counts = dict(result.all())
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
        self,
        status_filter: str = "pending",
        provider_filter: ExternalProvider | None = None,
    ) -> list[MetadataProposalAdminResponse]:
        stmt = select(MetadataProposal).where(MetadataProposal.status == status_filter)
        if provider_filter:
            stmt = stmt.where(MetadataProposal.provider == provider_filter)
        result = await self.db.execute(stmt.order_by(MetadataProposal.created_at.asc()))
        responses: list[MetadataProposalAdminResponse] = []
        for proposal in result.scalars():
            response = MetadataProposalAdminResponse.model_validate(proposal)
            compacted_payload = compact_metadata_payload(response.metadata_payload)
            if compacted_payload != response.metadata_payload:
                response = response.model_copy(update={"metadata_payload": compacted_payload})
            responses.append(response)
        return responses

    async def update_proposal(
        self,
        proposal_id: UUID,
        payload: MetadataProposalAdminUpdateRequest,
    ) -> MetadataProposalAdminResponse:
        proposal = await self.db.get(MetadataProposal, proposal_id)
        if proposal is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="metadata_proposal_not_found",
                detail="Proposal not found",
            )
        if proposal.status != "pending":
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="metadata_proposal_not_pending",
                detail="Only pending proposals can be edited",
            )

        changed_fields: list[str] = []

        def _trimmed(value: str | None) -> str | None:
            if value is None:
                return None
            normalized = value.strip()
            return normalized if normalized else None

        query = _trimmed(payload.query)
        if query is not None and query != proposal.query:
            proposal.query = query
            changed_fields.append("query")

        provider_item_id = _trimmed(payload.provider_item_id)
        if payload.provider_item_id is not None and provider_item_id != proposal.provider_item_id:
            proposal.provider_item_id = provider_item_id
            changed_fields.append("provider_item_id")

        title = _trimmed(payload.title)
        if payload.title is not None and title != proposal.title:
            proposal.title = title
            changed_fields.append("title")

        summary = _trimmed(payload.summary)
        if payload.summary is not None and summary != proposal.summary:
            proposal.summary = summary
            changed_fields.append("summary")

        image_url = _trimmed(payload.image_url)
        if payload.image_url is not None and image_url != proposal.image_url:
            proposal.image_url = image_url
            changed_fields.append("image_url")

        if payload.metadata_payload is not None:
            from app.proposal_payload import validate_metadata_payload

            validate_metadata_payload(payload.metadata_payload)
            compacted_payload = compact_metadata_payload(payload.metadata_payload)
            if compacted_payload != proposal.metadata_payload:
                proposal.metadata_payload = compacted_payload
                changed_fields.append("metadata_payload")

        if changed_fields:
            self._audit_recorder(
                action="metadata_proposal.update",
                entity_type="metadata_proposal",
                entity_id=proposal.id,
                details={
                    "provider": proposal.provider,
                    "provider_item_id": proposal.provider_item_id,
                    "changed_fields": changed_fields,
                },
            )
            await self.db.commit()
            await self.db.refresh(proposal)
        return MetadataProposalAdminResponse.model_validate(proposal)

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
        self._audit_recorder(
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
        self._audit_recorder(
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
        self._audit_recorder(
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
            resolved_entity_type=None,
            resolved_entity_id=None,
        )
        self.db.add(job)
        await self.db.flush()
        self._audit_recorder(
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
        counts = {"queued": 0, "running": 0, "failed": 0, "done": 0}
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
            select(func.min(ProviderIngestJob.created_at)).where(ProviderIngestJob.status == "queued")
        )
        next_run_at = await self.db.scalar(
            select(func.min(ProviderIngestJob.next_run_at)).where(
                ProviderIngestJob.status == "queued",
                ProviderIngestJob.next_run_at.is_not(None),
            )
        )
        latest_failure_at = await self.db.scalar(
            select(func.max(ProviderIngestJob.updated_at)).where(ProviderIngestJob.status == "failed")
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
        self._audit_recorder(
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
        self._audit_recorder(
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
            processed.append(ProviderIngestJobResponse.model_validate(await self._execute_ingest_job(job)))
        if self.actor_user_id is not None:
            self._audit_recorder(
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
        return recovered

    def ingest_history(self) -> list[ProviderIngestHistoryEntry]:
        return list(self._history_reader())

    async def refresh_stale_items(self, limit: int = 10) -> int:
        stale_days = self.settings.worker_catalog_refresh_stale_days
        cutoff = datetime.now(UTC) - timedelta(days=stale_days)
        result = await self.db.execute(
            select(ExternalProviderId)
            .where(
                ExternalProviderId.updated_at < cutoff,
            )
            .order_by(ExternalProviderId.updated_at.asc())
            .limit(limit)
        )
        provider_ids = result.scalars().all()
        refreshed = 0
        for pid in provider_ids:
            try:
                await self._refresh_external_provider_id(pid)
                refreshed += 1
            except Exception:
                pass
        if refreshed:
            await self.db.commit()
        return refreshed

    async def _refresh_external_provider_id(self, pid: ExternalProviderId) -> None:
        """Refresh metadata for an external provider ID by re-ingesting and updating fields."""
        registry = ProviderRegistry()
        provider = registry.get(pid.provider)
        if provider is None or not provider.is_configured:
            pid.updated_at = datetime.now(UTC)
            return
         
        # Get the entity and refresh its data
        if pid.entity_type == "comic_issue":
            issue = await self.db.get(ComicIssue, pid.entity_id)
            if issue is None:
                return
            provider_item = await provider.get_item(pid.provider_item_id)
            normalized = await provider.normalize(provider_item.raw)
            # Update issue fields from provider data
            issue.display_title = normalized.edition_title or normalized.title
            issue.publication_date = normalized.release_date
            issue.release_date = normalized.release_date
            issue.publisher = normalized.publisher
            issue.imprint = normalized.imprint
            issue.page_count = normalized.page_count
            issue.cover_price_cents = normalized.cover_price_cents
            issue.currency = (normalized.currency or "").upper()[:8] or None
            issue.description = normalized.synopsis
        else:
            # For other entity types, re-ingest
            await self.ingest(
                ProviderIngestRequest(
                    provider=pid.provider,
                    provider_item_id=pid.provider_item_id,
                )
            )
         
        pid.updated_at = datetime.now(UTC)

    async def retry_ingest(self, payload: ProviderIngestRetryRequest) -> ProviderIngestResponse:
        entry = next((entry for entry in self._history_reader() if entry.id == payload.history_id), None)
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
            ProviderIngestRequest(provider=entry.provider, provider_item_id=entry.provider_item_id)
        )
        self._audit_recorder(
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
            audience_rating=normalized.audience_rating,
            subtitle=normalized.subtitle,
            series_group=normalized.series_group,
            page_count=normalized.page_count,
            runtime_minutes=normalized.runtime_minutes,
            track_count=normalized.track_count,
            catalog_number=normalized.catalog_number,
            creators=[ProviderPreviewCredit(name=c.name, role=c.role, image_url=c.image_url) for c in normalized.creators],
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
            field_states=provider_preview_field_states(
                normalized,
                physical_format_id=physical_format.id if physical_format else None,
                physical_format_label=physical_format.label if physical_format else None,
            ),
        )

    async def batch_hydrate(
        self,
        payload: ProviderBatchHydrateRequest,
    ) -> ProviderBatchHydrateResponse:
        provider = self._provider(payload.provider)
        self._ensure_provider_ingest_supported(provider, payload.provider)
        results: list[ProviderBatchHydrateResultItem] = []
        succeeded = 0
        failed = 0
        for item in payload.items:
            try:
                preview = await self.preview(
                    ProviderIngestRequest(
                        provider=payload.provider,
                        provider_item_id=item.provider_item_id,
                    )
                )
                results.append(
                    ProviderBatchHydrateResultItem(
                        provider_item_id=item.provider_item_id,
                        success=True,
                        preview=preview,
                    )
                )
                succeeded += 1
            except Exception as exc:
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
                    resolved_entity_type=self._resolved_entity_type_for_response(response.item),
                    resolved_entity_id=response.item_id,
                )
                await self.provider_preview_state.invalidate(
                    payload.provider.value,
                    payload.provider_item_id,
                    response.item.provider_links[0].provider_item_id
                    if hasattr(response.item, "provider_links") and getattr(response.item, "provider_links", None)
                    else None,
                )
                return response
            except Exception as exc:
                last_error = exc
                await self.db.rollback()
                await self.provider_preview_state.invalidate(payload.provider.value, payload.provider_item_id)
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
        if normalized.kind == ItemKind.comic:
            work, work_created = await self._create_comic_work_from_normalized(
                provider=provider,
                provider_name=payload.provider,
                provider_item_id=provider_item.provider_item_id,
                provider_raw=provider_item.raw,
                normalized=normalized,
            )
            await self.db.commit()
            await self._reindex_comic_work(work.id)
            return ProviderIngestResponse(
                item_id=work.id,
                created=work_created,
                item=await MetadataService(self.db).get_comic_work(work.id),
            )
        if normalized.kind == ItemKind.manga:
            work = await self._create_manga_work_from_normalized(
                provider=provider,
                provider_name=payload.provider,
                provider_item_id=provider_item.provider_item_id,
                provider_raw=provider_item.raw,
                normalized=normalized,
            )
            await self.db.commit()
            await self._reindex_manga_work(work.id)
            return ProviderIngestResponse(
                item_id=work.id,
                created=True,
                item=await MetadataService(self.db).get_manga_work(work.id),
            )
        if normalized.kind == ItemKind.anime:
            series = await self._create_anime_series_from_normalized(
                provider=provider,
                provider_name=payload.provider,
                provider_item_id=provider_item.provider_item_id,
                provider_raw=provider_item.raw,
                normalized=normalized,
            )
            await self.db.commit()
            await self._reindex_anime_series(series.id)
            return ProviderIngestResponse(
                item_id=series.id,
                created=True,
                item=await MetadataService(self.db).get_anime_series(series.id),
            )
        if normalized.kind == ItemKind.movie:
            work = await self._create_movie_work_from_normalized(
                provider=provider,
                provider_name=payload.provider,
                provider_item_id=provider_item.provider_item_id,
                provider_raw=provider_item.raw,
                normalized=normalized,
            )
            await self.db.commit()
            await self._reindex_movie_work(work.id)
            return ProviderIngestResponse(
                item_id=work.id,
                created=True,
                item=await MetadataService(self.db).get_movie_work(work.id),
            )
        if normalized.kind == ItemKind.tv:
            series = await self._create_tv_series_from_normalized(
                provider=provider,
                provider_name=payload.provider,
                provider_item_id=provider_item.provider_item_id,
                provider_raw=provider_item.raw,
                normalized=normalized,
            )
            await self.db.commit()
            await self._reindex_tv_series(series.id)
            return ProviderIngestResponse(
                item_id=series.id,
                created=True,
                item=await MetadataService(self.db).get_tv_series(series.id),
            )
        if normalized.kind == ItemKind.book:
            work = await self._create_book_work_from_normalized(
                provider=provider,
                provider_name=payload.provider,
                provider_item_id=provider_item.provider_item_id,
                provider_raw=provider_item.raw,
                normalized=normalized,
            )
            await self.db.commit()
            await self._reindex_book_work(work.id)
            return ProviderIngestResponse(
                item_id=work.id,
                created=True,
                item=await MetadataService(self.db).get_book_work(work.id),
            )
        if normalized.kind == ItemKind.music:
           release = await self._create_music_release_from_normalized(
               provider=provider,
               provider_name=payload.provider,
               provider_item_id=provider_item.provider_item_id,
               provider_raw=provider_item.raw,
               normalized=normalized,
           )
           await self.db.commit()
           return ProviderIngestResponse(
               item_id=release.id,
               created=True,
               item=await MetadataService(self.db).get_music_release(release.id),
           )
        if normalized.kind == ItemKind.game:
           work = await self._create_game_work_from_normalized(
               provider=provider,
               provider_name=payload.provider,
               provider_item_id=provider_item.provider_item_id,
               provider_raw=provider_item.raw,
               normalized=normalized,
           )
           await self.db.commit()
           await self._reindex_game_work(work.id)
           return ProviderIngestResponse(
               item_id=work.id,
               created=True,
               item=await MetadataService(self.db).get_game_work(work.id),
           )
        if normalized.kind == ItemKind.boardgame:
           work = await self._create_boardgame_work_from_normalized(
               provider=provider,
               provider_name=payload.provider,
               provider_item_id=provider_item.provider_item_id,
               provider_raw=provider_item.raw,
               normalized=normalized,
           )
           await self.db.commit()
           await self._reindex_boardgame_work(work.id)
           return ProviderIngestResponse(
               item_id=work.id,
               created=True,
               item=await MetadataService(self.db).get_boardgame_work(work.id),
           )
        raise ApiHTTPException(
           status_code=status.HTTP_400_BAD_REQUEST,
           code="provider_ingest_unsupported",
           detail=(
               f"Provider '{payload.provider.value}' does not support "
               f"ingest for kind '{normalized.kind.value}'"
           ),
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
        hydrated = HydratedProviderPreview(provider_item=provider_item, normalized=normalized)
        if use_cache:
            await self.provider_preview_state.store(
                payload.provider.value,
                payload.provider_item_id,
                hydrated,
            )
        return hydrated

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

    def _should_mirror_provider_images(self, provider: MetadataProvider) -> bool:
        if not self.settings.mirror_provider_images:
            return False
        if self.settings.mirror_provider_images_allow_restricted:
            return True
        return provider.capabilities.allows_image_mirroring

    async def _get_provider_id(self, payload: ProviderIngestRequest) -> CatalogExternalProviderIdRef | None:
        return await self._get_provider_id_value(payload.provider, payload.provider_item_id)

    async def _get_provider_id_value(
        self,
        provider: ExternalProvider,
        provider_item_id: str,
    ) -> CatalogExternalProviderIdRef | None:
        # Query ExternalProviderId (v0 and v1 entity types)
        external_ref = await self.db.execute(
            select(ExternalProviderId.entity_type, ExternalProviderId.entity_id).where(
                ExternalProviderId.provider == provider,
                ExternalProviderId.provider_item_id == provider_item_id,
                ExternalProviderId.entity_type.in_(
                    [
                        "game_work",
                        "boardgame_work",
                        "book_work",
                        "comic_work",
                        "manga_work",
                        "anime_series",
                        "movie_work",
                        "tv_series",
                        "music_release",
                    ]
                ),
            )
        )
        external_row = external_ref.first()
        if external_row is not None:
            return CatalogExternalProviderIdRef(
                entity_type=str(external_row[0]),
                entity_id=external_row[1],
                provider_item_id=provider_item_id,
            )
        return None

    async def _existing_response(self, provider_id: CatalogExternalProviderIdRef) -> ProviderIngestResponse:
        if provider_id.entity_type == "game_work":
            game_work = await self.db.get(GameWork, provider_id.entity_id)
            if game_work is None:
                raise ApiHTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    code="provider_link_stale",
                    detail="Provider link is stale",
                )
            return ProviderIngestResponse(
                item_id=game_work.id,
                created=False,
                item=await MetadataService(self.db).get_game_work(game_work.id),
            )
        elif provider_id.entity_type == "boardgame_work":
            boardgame_work = await self.db.get(BoardGameWork, provider_id.entity_id)
            if boardgame_work is None:
                raise ApiHTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    code="provider_link_stale",
                    detail="Provider link is stale",
                )
            return ProviderIngestResponse(
                item_id=boardgame_work.id,
                created=False,
                item=await MetadataService(self.db).get_boardgame_work(boardgame_work.id),
            )
        elif provider_id.entity_type == "book_work":
            book_work = await self.db.get(BookWork, provider_id.entity_id)
            if book_work is None:
                raise ApiHTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    code="provider_link_stale",
                    detail="Provider link is stale",
                )
            return ProviderIngestResponse(
                item_id=book_work.id,
                created=False,
                item=await MetadataService(self.db).get_book_work(book_work.id),
            )
        elif provider_id.entity_type == "comic_work":
            comic_work = await self.db.get(ComicWork, provider_id.entity_id)
            if comic_work is None:
                raise ApiHTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    code="provider_link_stale",
                    detail="Provider link is stale",
                )
            return ProviderIngestResponse(
                item_id=comic_work.id,
                created=False,
                item=await MetadataService(self.db).get_comic_work(comic_work.id),
            )
        elif provider_id.entity_type == "manga_work":
            manga_work = await self.db.get(MangaWork, provider_id.entity_id)
            if manga_work is None:
                raise ApiHTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    code="provider_link_stale",
                    detail="Provider link is stale",
                )
            return ProviderIngestResponse(
                item_id=manga_work.id,
                created=False,
                item=await MetadataService(self.db).get_manga_work(manga_work.id),
            )
        else:
            raise ApiHTTPException(
                status_code=status.HTTP_409_CONFLICT,
                code="provider_link_stale",
                detail="Provider link is stale or unsupported",
            )

    def _resolved_entity_type_for_response(self, item: Any) -> str | None:
        name = item.__class__.__name__
        return {
            "BookWorkV1Response": "book_work",
            "ComicWorkV1Response": "comic_work",
            "GameWorkV1Response": "game_work",
            "BoardGameWorkV1Response": "boardgame_work",
            "MangaWorkV1Response": "manga_work",
            "AnimeSeriesV1Response": "anime_series",
            "MovieWorkV1Response": "movie_work",
            "MusicReleaseV1Response": "music_release",
            "TVSeriesV1Response": "tv_series",
        }.get(name)

    def _physical_format_for_normalized(
        self,
        normalized: NormalizedItem,
    ) -> PhysicalFormatConfig | None:
        return physical_format_for_normalized(normalized)

    def _variant_cover_name(self, cover: NormalizedVariantCover, index: int) -> str:
        return variant_cover_name(cover, index)

    def _cover_metadata(
        self,
        source_url: str | None,
        mirrored_cover: Any | None,
    ) -> dict[str, Any]:
        return cover_metadata(source_url, mirrored_cover)

    def _provider_metadata_json(
        self,
        provider_name: ExternalProvider,
        provider_item_id: str,
        *,
        kind: ItemKind,
        normalized: dict[str, Any] | None = None,
        source: Any | None = None,
    ) -> dict[str, Any]:
        return provider_metadata_json(
            provider_name,
            provider_item_id,
            kind=kind,
            normalized=normalized,
            source=source,
        )

    def _normalized_release_status(self, value: str | None) -> str | None:
        return normalized_release_status(value)

    def _normalized_language(self, value: str | None) -> str | None:
        return normalized_language(value)

    def _normalized_region(self, value: str | None) -> str | None:
        return normalized_region(value)

    async def _ensure_release_status(self, status_value: str) -> None:
        existing = await self.db.scalar(
            select(ReleaseStatus).where(ReleaseStatus.code == status_value)
        )
        if existing is not None:
            return
        self.db.add(ReleaseStatus(code=status_value, label=status_value))

    async def _ensure_physical_format_ref(self, config: PhysicalFormatConfig) -> None:
        existing = await self.db.get(PhysicalFormatRef, config.id)
        if existing is not None:
            return
        self.db.add(
            PhysicalFormatRef(
                id=config.id,
                label=config.label,
                media_family=config.media_family,
                variant_type=config.variant_type,
            )
        )

    async def _record_provider_snapshot(
        self,
        *,
        provider: ExternalProvider,
        provider_item_id: str,
        entity_type: str,
        entity_id: UUID,
        source: Any | None,
        normalized: dict[str, Any] | None,
    ) -> None:
        self.db.add(
            ProviderPayloadSnapshot(
                provider=provider,
                provider_item_id=provider_item_id,
                entity_type=entity_type,
                entity_id=entity_id,
                source_payload=source if isinstance(source, dict) else None,
                normalized_payload=normalized if isinstance(normalized, dict) else None,
                expires_at=datetime.now(UTC) + _SNAPSHOT_TTL,
            )
        )

    async def _enrich_missing_comic_cover(
        self,
        normalized: NormalizedItem,
    ) -> NormalizedItem:
        if normalized.cover_image_url or normalized.kind not in {ItemKind.comic}:
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
            provider_ids={**normalized.provider_ids, "comicvine": cover.provider_item_id},
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
                ProviderIngestRequest(provider=provider, provider_item_id=provider_item_id)
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
                "provider_ingest_job_failed job_id=%s provider=%s provider_item_id=%s status=%s attempts=%s error=%s",
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
        refreshed.resolved_entity_type = self._resolved_entity_type_for_response(response.item)
        refreshed.resolved_entity_id = response.item_id
        refreshed.last_error = None
        refreshed.next_run_at = None
        await self.db.commit()
        await self.db.refresh(refreshed)
        logger.info(
            "provider_ingest_job_finished job_id=%s provider=%s provider_item_id=%s resolved_entity_type=%s resolved_entity_id=%s",
            refreshed.id,
            refreshed.provider.value,
            refreshed.provider_item_id,
            refreshed.resolved_entity_type,
            refreshed.resolved_entity_id,
        )
        return refreshed

    async def _upsert_book_series(
        self,
        series_title: str | None,
        *,
        provider: ExternalProvider,
        provider_item_id: str,
        normalized: NormalizedItem,
        provider_raw: Any | None,
    ) -> BookSeries | None:
        if not series_title:
            return None
        existing = await self.db.scalar(select(BookSeries).where(BookSeries.title == series_title))
        if existing is not None:
            return existing
        series = BookSeries(
            title=series_title,
            slug=slug(series_title),
            metadata_json=self._provider_metadata_json(
                provider,
                provider_item_id,
                kind=ItemKind.book,
                normalized={
                    "series_title": series_title,
                    "release_date": normalized.release_date.isoformat() if normalized.release_date else None,
                },
                source=provider_raw,
            ),
        )
        self.db.add(series)
        await self.db.flush()
        return series



    async def _get_or_create_manga_series(self, title: str) -> MangaSeries:
        result = await self.db.execute(select(MangaSeries).where(MangaSeries.title == title))
        series = result.scalar_one_or_none()
        if series is None:
            series = MangaSeries(title=title, slug=slug(title))
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
            site_url = provider_link_url_text(urls.get("site_url")) if urls else None
            api_url = provider_link_url_text(urls.get("api_url")) if urls else None
            existing = await self.db.scalar(
                select(ExternalProviderId).where(
                    ExternalProviderId.provider == provider_enum,
                    ExternalProviderId.provider_item_id == provider_id,
                    ExternalProviderId.entity_type == entity_type,
                    ExternalProviderId.entity_id == entity_id,
                )
            )
            if existing:
                if site_url and site_url != existing.site_url:
                    existing.site_url = site_url
                if api_url and api_url != existing.api_url:
                    existing.api_url = api_url
                continue
            
            # Check if any entry with same provider/provider_item_id already exists
            # (could be for a different entity_type, which violates unique constraint)
            existing_any = await self.db.scalar(
                select(ExternalProviderId).where(
                    ExternalProviderId.provider == provider_enum,
                    ExternalProviderId.provider_item_id == provider_id,
                )
            )
            if existing_any:
                # Entry exists for different entity, skip to avoid unique constraint violation
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

    async def _replace_entity_provider_links(
        self,
        entity_type: str,
        entity_id: UUID,
        provider: ExternalProvider,
        provider_ids: dict[str, str],
        provider_urls: dict[str, dict[str, str | None]] | None = None,
    ) -> None:
        await self._replace_catalog_provider_links(
            entity_type=entity_type,
            owner_id=entity_id,
            provider=provider,
            provider_ids=provider_ids,
            provider_urls=provider_urls,
        )

    async def _replace_catalog_provider_links(
        self,
        *,
        entity_type: str,
        owner_id: UUID,
        provider: ExternalProvider,
        provider_ids: dict[str, str],
        provider_urls: dict[str, dict[str, str | None]] | None = None,
    ) -> None:
        candidate_ids = provider_ids or {}
        replacement_providers: set[ExternalProvider] = {provider}
        rows: list[dict[str, Any]] = []
        for provider_name, provider_id in candidate_ids.items():
            try:
                provider_enum = ExternalProvider(provider_name)
            except ValueError:
                continue
            replacement_providers.add(provider_enum)
            if not provider_id:
                continue
            urls = provider_urls.get(provider_name) if provider_urls else None
            rows.append(
                {
                    "provider": provider_enum,
                    "provider_item_id": provider_id,
                    "entity_type": entity_type,
                    "site_url": provider_link_url_text(urls.get("site_url")) if urls else None,
                    "api_url": provider_link_url_text(urls.get("api_url")) if urls else None,
                }
            )
        await self.db.execute(
            delete(ExternalProviderId).where(
                ExternalProviderId.entity_id == owner_id,
                ExternalProviderId.entity_type == entity_type,
                ExternalProviderId.provider.in_(sorted(replacement_providers, key=lambda value: value.value)),
            )
        )
        for row in rows:
            existing_any = await self.db.scalar(
                select(ExternalProviderId).where(
                    ExternalProviderId.provider == row["provider"],
                    ExternalProviderId.provider_item_id == row["provider_item_id"],
                )
            )
            if existing_any:
                continue
            self.db.add(
                ExternalProviderId(
                    provider=row["provider"],
                    provider_item_id=row["provider_item_id"],
                    entity_type=row["entity_type"],
                    entity_id=owner_id,
                    site_url=row["site_url"],
                    api_url=row["api_url"],
                )
            )

    async def _link_organization_for_entity(
        self,
        entity_type: str,
        entity_id: UUID,
        name: str | None,
        role: str,
    ) -> None:
        if not name:
            return
        organization = await self._get_or_create_organization(name, role)
        exists = await self.db.scalar(
            select(EntityOrganization.id).where(
                EntityOrganization.entity_type == entity_type,
                EntityOrganization.entity_id == entity_id,
                EntityOrganization.organization_id == organization.id,
                EntityOrganization.role == role,
            )
        )
        if exists:
            return
        self.db.add(
            EntityOrganization(
                entity_type=entity_type,
                entity_id=entity_id,
                organization_id=organization.id,
                role=role,
            )
        )

    async def _link_person_for_entity(
        self,
        entity_type: str,
        entity_id: UUID,
        name: str | None,
        role: str,
    ) -> None:
        if not name:
            return
        person = await self._get_or_create_person(name, NormalizedCredit(name=name, role=role))
        exists = await self.db.scalar(
            select(EntityPerson.id).where(
                EntityPerson.entity_type == entity_type,
                EntityPerson.entity_id == entity_id,
                EntityPerson.person_id == person.id,
                EntityPerson.role == role,
            )
        )
        if exists:
            return
        self.db.add(
            EntityPerson(
                entity_type=entity_type,
                entity_id=entity_id,
                person_id=person.id,
                role=role,
            )
        )

    async def _create_game_work_from_normalized(
        self,
        *,
        provider: MetadataProvider,
        provider_name: ExternalProvider,
        provider_item_id: str,
        provider_raw: Any | None,
        normalized: NormalizedItem,
    ) -> GameWork:
        mirrored_cover = None
        if normalized.cover_image_url and self._should_mirror_provider_images(provider):
            mirrored_cover = await ImageMirror(self.db).mirror_cover_best_effort(
                source_url=normalized.cover_image_url,
                provider=provider_name,
                provider_item_id=provider_item_id,
            )

        cover_metadata = self._cover_metadata(normalized.cover_image_url, mirrored_cover)
        work = GameWork(
            title=normalized.title,
            sort_title=sort_key(ItemKind.game, normalized.title, normalized.item_number),
            subtitle=normalized.subtitle,
            description=normalized.synopsis,
            release_date=normalized.release_date,
            original_language=self._normalized_language(normalized.language),
            age_rating=normalized.age_rating,
            audience_rating=normalized.audience_rating,
            cover_image_url=mirrored_cover.url if mirrored_cover else normalized.cover_image_url,
            cover_image_key=mirrored_cover.key if mirrored_cover else None,
            metadata_json={
                **cover_metadata,
                "genres": normalized.genres or None,
                "platforms": normalized.platforms or None,
            },
        )
        self.db.add(work)
        await self.db.flush()

        release = GameRelease(
            work_id=work.id,
            release_title=normalized.edition_title or normalized.title,
            platform=normalized.platforms[0] if normalized.platforms else normalized.edition_format,
            release_date=normalized.release_date,
            region_code=self._normalized_region(normalized.country),
            format=normalized.edition_format,
            publisher=normalized.publisher,
            catalog_number=normalized.catalog_number,
            barcode=normalized.barcode,
            release_status=self._normalized_release_status(normalized.release_status),
            language=self._normalized_language(normalized.language),
            cover_image_url=mirrored_cover.url if mirrored_cover else normalized.cover_image_url,
            cover_image_key=mirrored_cover.key if mirrored_cover else None,
            metadata_json=self._provider_metadata_json(
                provider_name,
                provider_item_id,
                kind=ItemKind.game,
                normalized={
                    **cover_metadata,
                    "platforms": normalized.platforms,
                    "genres": normalized.genres,
                },
                source=provider_raw,
            ),
        )
        self.db.add(release)

        for credit in normalized.creators:
            await self._link_organization_for_entity(
                "game_work",
                work.id,
                credit.name,
                (credit.role or "developer").strip().lower() or "developer",
            )

        if normalized.publisher:
            await self._link_organization_for_entity("game_work", work.id, normalized.publisher, "publisher")

        provider_ids = dict(normalized.provider_ids or {})
        provider_ids[provider_name.value] = provider_item_id
        await self._replace_entity_provider_links(
            "game_work",
            work.id,
            provider_name,
            provider_ids,
            provider_urls=provider_link_urls_for_provider(
                provider_name,
                provider_ids,
                provider_raw,
            ),
        )
        await self._record_provider_snapshot(
            provider=provider_name,
            provider_item_id=provider_item_id,
            entity_type="game_work",
            entity_id=work.id,
            source=provider_raw,
            normalized={
                "title": work.title,
                "release_date": release.release_date.isoformat() if release.release_date else None,
                "platforms": normalized.platforms,
                "genres": normalized.genres,
                **cover_metadata,
            },
        )
        if mirrored_cover:
            await ImageCache(self.db).record_mirrored_cover(mirrored_cover)
        return work

    async def _create_boardgame_work_from_normalized(
        self,
        *,
        provider: MetadataProvider,
        provider_name: ExternalProvider,
        provider_item_id: str,
        provider_raw: Any | None,
        normalized: NormalizedItem,
    ) -> BoardGameWork:
        mirrored_cover = None
        if normalized.cover_image_url and self._should_mirror_provider_images(provider):
            mirrored_cover = await ImageMirror(self.db).mirror_cover_best_effort(
                source_url=normalized.cover_image_url,
                provider=provider_name,
                provider_item_id=provider_item_id,
            )

        cover_metadata = self._cover_metadata(normalized.cover_image_url, mirrored_cover)
        work = BoardGameWork(
            title=normalized.title,
            sort_title=sort_key(ItemKind.boardgame, normalized.title, normalized.item_number),
            subtitle=normalized.subtitle,
            description=normalized.synopsis,
            release_date=normalized.release_date,
            age_rating=normalized.age_rating,
            audience_rating=normalized.audience_rating,
            cover_image_url=mirrored_cover.url if mirrored_cover else normalized.cover_image_url,
            cover_image_key=mirrored_cover.key if mirrored_cover else None,
            metadata_json={
                **cover_metadata,
                "genres": normalized.genres or None,
                "platforms": normalized.platforms or None,
                "categories": [credit.name for credit in normalized.characters] or None,
                "families": [credit.name for credit in normalized.story_arcs] or None,
            },
        )
        self.db.add(work)
        await self.db.flush()

        edition = BoardGameEdition(
            work_id=work.id,
            edition_title=normalized.edition_title or normalized.title,
            format=normalized.edition_format or "Board Game",
            publisher=normalized.publisher,
            catalog_number=normalized.catalog_number,
            barcode=normalized.barcode,
            release_status=self._normalized_release_status(normalized.release_status),
            release_date=normalized.release_date,
            language=self._normalized_language(normalized.language),
            country=self._normalized_region(normalized.country),
            age_rating=normalized.age_rating,
            audience_rating=normalized.audience_rating,
            min_players=normalized.min_players,
            max_players=normalized.max_players,
            playing_time_minutes=normalized.playing_time_minutes,
            min_age=normalized.min_age,
            cover_image_url=mirrored_cover.url if mirrored_cover else normalized.cover_image_url,
            cover_image_key=mirrored_cover.key if mirrored_cover else None,
            description=normalized.synopsis,
            metadata_json=self._provider_metadata_json(
                provider_name,
                provider_item_id,
                kind=ItemKind.boardgame,
                normalized={
                    **cover_metadata,
                    "genres": normalized.genres,
                    "platforms": normalized.platforms,
                    "min_players": normalized.min_players,
                    "max_players": normalized.max_players,
                    "playing_time_minutes": normalized.playing_time_minutes,
                    "min_age": normalized.min_age,
                },
                source=provider_raw,
            ),
        )
        self.db.add(edition)

        for credit in normalized.creators:
            await self._link_person_for_entity(
                "boardgame_work",
                work.id,
                credit.name,
                (credit.role or "designer").strip().lower() or "designer",
            )

        if normalized.publisher:
            await self._link_organization_for_entity("boardgame_work", work.id, normalized.publisher, "publisher")

        provider_ids = dict(normalized.provider_ids or {})
        provider_ids[provider_name.value] = provider_item_id
        await self._replace_entity_provider_links(
            "boardgame_work",
            work.id,
            provider_name,
            provider_ids,
            provider_urls=provider_link_urls_for_provider(
                provider_name,
                provider_ids,
                provider_raw,
            ),
        )
        await self._record_provider_snapshot(
            provider=provider_name,
            provider_item_id=provider_item_id,
            entity_type="boardgame_work",
            entity_id=work.id,
            source=provider_raw,
            normalized={
                "title": work.title,
                "release_date": edition.release_date.isoformat() if edition.release_date else None,
                "genres": normalized.genres,
                "platforms": normalized.platforms,
                "min_players": normalized.min_players,
                "max_players": normalized.max_players,
                "playing_time_minutes": normalized.playing_time_minutes,
                "min_age": normalized.min_age,
                **cover_metadata,
            },
        )
        if mirrored_cover:
            await ImageCache(self.db).record_mirrored_cover(mirrored_cover)
        return work

    async def _create_comic_work_from_normalized(
        self,
        *,
        provider: MetadataProvider,
        provider_name: ExternalProvider,
        provider_item_id: str,
        provider_raw: Any | None,
        normalized: NormalizedItem,
    ) -> tuple[ComicWork, bool]:
        """
        Create or reuse a ComicWork from normalized provider data.
        Returns: (work, created) where created=True if work was newly created, False if reused.
        """
        series_title = normalized.series_title or normalized.volume_name
        series = await self._get_or_create_comic_series(series_title) if series_title else None

        work_title = normalized.series_title or normalized.title
        work = await self.db.scalar(select(ComicWork).where(ComicWork.title == work_title))

        mirrored_cover = None
        if normalized.cover_image_url and self._should_mirror_provider_images(provider):
            mirrored_cover = await ImageMirror(self.db).mirror_cover_best_effort(
                source_url=normalized.cover_image_url,
                provider=provider_name,
                provider_item_id=provider_item_id,
            )

        work_created = False
        if work is None:
            work = ComicWork(
                title=work_title,
                sort_title=sort_key(ItemKind.comic, work_title, None),
                subtitle=normalized.subtitle,
                description=normalized.synopsis,
                original_language=self._normalized_language(normalized.language),
                first_publication_date=normalized.release_date,
                metadata_json=self._provider_metadata_json(
                    provider_name,
                    provider_item_id,
                    kind=ItemKind.comic,
                    normalized={"series_title": normalized.series_title},
                ),
            )
            self.db.add(work)
            await self.db.flush()
            work_created = True

        release_status = self._normalized_release_status(normalized.release_status)
        if release_status is not None:
            await self._ensure_release_status(release_status)
        
        # Check if issue already exists by any provider id associated with this raw issue.
        issue = None
        issue_provider_ids = {
            provider_item_id,
            *(provider_value for provider_value in normalized.provider_ids.values() if provider_value),
        }
        existing_provider_id = None
        if issue_provider_ids:
            existing_provider_id = await self.db.scalar(
                select(ExternalProviderId).where(
                    ExternalProviderId.provider == provider_name,
                    ExternalProviderId.entity_type == "comic_issue",
                    ExternalProviderId.provider_item_id.in_(issue_provider_ids),
                )
            )
        if existing_provider_id:
            issue = await self.db.scalar(
                select(ComicIssue).where(ComicIssue.id == existing_provider_id.entity_id)
            )
        
        # Only create new issue if one doesn't already exist
        if issue is None:
            issue = ComicIssue(
                work_id=work.id,
                issue_number=normalized.item_number,
                display_title=normalized.edition_title or normalized.title,
                publication_date=normalized.release_date,
                release_date=normalized.release_date,
                publisher=normalized.publisher,
                imprint=normalized.imprint,
                language=self._normalized_language(normalized.language),
                region=self._normalized_region(normalized.country),
                page_count=normalized.page_count,
                cover_price_cents=normalized.cover_price_cents,
                currency=(normalized.currency or "").upper()[:8] or None,
                release_status=release_status,
                cover_image_url=mirrored_cover.url if mirrored_cover else normalized.cover_image_url,
                cover_image_key=mirrored_cover.key if mirrored_cover else None,
                description=normalized.synopsis,
                metadata_json=self._provider_metadata_json(
                    provider_name,
                    provider_item_id,
                    kind=ItemKind.comic,
                    normalized={"cover_storage": "mirror" if mirrored_cover else "provider"},
                ),
            )
            self.db.add(issue)
            await self.db.flush()

        # Only add contributions, identifiers, and other relations if issue was newly created
        if issue and not existing_provider_id:
            for index, credit in enumerate(normalized.creators, start=1):
                person = await self._get_or_create_person(credit.name, credit)
                self.db.add(
                    ComicContribution(
                        issue_id=issue.id,
                        person_id=person.id,
                        role=(credit.role or "creator").strip().lower(),
                        sequence=index,
                    )
                )

            identifiers: list[tuple[str, str, bool]] = []
            if normalized.isbn:
                identifiers.append(
                    (self._comic_identifier_type("isbn", normalized.isbn), normalized.isbn, True)
                )
            if normalized.barcode:
                identifiers.append(
                    (self._comic_identifier_type("upc", normalized.barcode), normalized.barcode, False)
                )
            identifiers.append(("provider_item_id", provider_item_id, False))
            for _, provider_value in normalized.provider_ids.items():
                if provider_value:
                    identifiers.append(("provider_item_id", provider_value, False))
            seen_identifier_keys: set[tuple[str, str]] = set()
            for identifier_type, value, is_primary in identifiers:
                normalized_value = self._normalized_identifier(value)
                if not normalized_value:
                    continue
                dedupe_key = (identifier_type, normalized_value)
                if dedupe_key in seen_identifier_keys:
                    continue
                seen_identifier_keys.add(dedupe_key)
                self.db.add(
                    ComicIdentifier(
                        issue_id=issue.id,
                        identifier_type=identifier_type,
                        value=value,
                        normalized_value=normalized_value,
                        is_primary=is_primary,
                        source_provider=provider_name,
                    )
                )

            seen_story_arcs: set[str] = set()
            for index, credit in enumerate(normalized.story_arcs, start=1):
                name = credit.name.strip()
                if not name:
                    continue
                key = name.casefold()
                if key in seen_story_arcs:
                    continue
                seen_story_arcs.add(key)
                story_arc = await self._get_or_create_story_arc(name, credit)
                self.db.add(
                    ComicStoryArcMembership(
                        issue_id=issue.id,
                        story_arc_id=story_arc.id,
                        ordinal=index,
                    )
                )
                story_arc_provider_id = comicvine_credit_provider_id(credit, resource="story_arc")
                if provider_name == ExternalProvider.comicvine and story_arc_provider_id:
                    await self._add_provider_links(
                        provider_name,
                        {provider_name.value: story_arc_provider_id},
                        "story_arc",
                        story_arc.id,
                        provider_urls={provider_name.value: credit_provider_urls(credit) or {}},
                    )

            seen_characters: set[tuple[str, str]] = set()
            for credit in normalized.characters:
                name = credit.name.strip()
                if not name:
                    continue
                role = character_appearance_role(credit.role)
                dedupe_key = (name.casefold(), role.casefold())
                if dedupe_key in seen_characters:
                    continue
                seen_characters.add(dedupe_key)
                character_provider_id = comicvine_credit_provider_id(credit, resource="character")
                character = await self._get_or_create_character(
                    name,
                    credit,
                    provider=provider_name,
                    provider_item_id=character_provider_id,
                )
                self.db.add(
                    ComicCharacterAppearance(
                        issue_id=issue.id,
                        character_id=character.id,
                        role=role,
                    )
                )

            if series is not None:
                # Check if series membership already exists
                existing_membership = await self.db.scalar(
                    select(ComicSeriesMembership).where(
                        ComicSeriesMembership.work_id == work.id,
                        ComicSeriesMembership.series_id == series.id,
                    )
                )
                if existing_membership is None:
                    sequence: float | None = None
                    if normalized.item_number:
                        try:
                            sequence = float(normalized.item_number)
                        except ValueError:
                            sequence = None
                    self.db.add(
                        ComicSeriesMembership(
                            work_id=work.id,
                            series_id=series.id,
                            sequence=sequence,
                            display_number=normalized.item_number,
                        )
                    )

        normalized_provider_item_id = (normalized.provider_ids or {}).get(provider_name.value)
        provider_ids = dict(normalized.provider_ids or {})
        provider_ids[provider_name.value] = provider_item_id

        # Provider links should be for the issue (the actual ingested item), not the work
        # We only store one entry per provider_item_id, so store it for the issue which is more specific
        await self._add_provider_links(
            provider_name,
            provider_ids,
            "comic_issue",
            issue.id,
            provider_urls=provider_link_urls_for_provider(
                provider_name,
                provider_ids,
                provider_raw,
            ),
        )
        if normalized_provider_item_id and normalized_provider_item_id != provider_item_id:
            await self._add_provider_links(
                provider_name,
                {provider_name.value: normalized_provider_item_id},
                "comic_issue",
                issue.id,
                provider_urls=provider_link_urls_for_provider(
                    provider_name,
                    {provider_name.value: normalized_provider_item_id},
                    provider_raw,
                ),
            )
        await self._record_provider_snapshot(
            provider=provider_name,
            provider_item_id=provider_item_id,
            entity_type="comic_work",
            entity_id=work.id,
            source=provider_raw,
            normalized={
                "title": work.title,
                "series_title": normalized.series_title,
                "original_language": work.original_language,
            },
        )
        await self._record_provider_snapshot(
            provider=provider_name,
            provider_item_id=provider_item_id,
            entity_type="comic_issue",
            entity_id=issue.id,
            source=provider_raw,
            normalized={
                "issue_number": issue.issue_number,
                "release_date": str(issue.release_date) if issue.release_date else None,
                "publisher": issue.publisher,
                "page_count": issue.page_count,
            },
        )
        if mirrored_cover:
            await ImageCache(self.db).record_mirrored_cover(mirrored_cover)
        
        return work, work_created

    async def _get_or_create_comic_series(self, title: str | None) -> ComicSeries | None:
        if not title:
            return None
        result = await self.db.execute(select(ComicSeries).where(ComicSeries.title == title))
        series = result.scalar_one_or_none()
        if series is not None:
            return series
        series = ComicSeries(title=title, slug=slug(title))
        self.db.add(series)
        await self.db.flush()
        return series

    async def _create_book_work_from_normalized(
        self,
        *,
        provider: MetadataProvider,
        provider_name: ExternalProvider,
        provider_item_id: str,
        provider_raw: Any | None,
        normalized: NormalizedItem,
    ) -> BookWork:
        mirrored_cover = None
        if normalized.cover_image_url and self._should_mirror_provider_images(provider):
            mirrored_cover = await ImageMirror(self.db).mirror_cover_best_effort(
                source_url=normalized.cover_image_url,
                provider=provider_name,
                provider_item_id=provider_item_id,
            )

        work = BookWork(
            title=normalized.title,
            sort_title=sort_key(ItemKind.book, normalized.title, normalized.item_number),
            subtitle=normalized.subtitle,
            description=normalized.synopsis,
            original_language=self._normalized_language(normalized.language),
            first_publication_date=normalized.release_date,
            metadata_json=self._provider_metadata_json(
                provider_name,
                provider_item_id,
                kind=ItemKind.book,
                normalized={"series_title": normalized.series_title},
            ),
        )
        self.db.add(work)
        await self.db.flush()

        series = await self._upsert_book_series(
            normalized.series_title or normalized.volume_name,
            provider=provider_name,
            provider_item_id=provider_item_id,
            normalized=normalized,
            provider_raw=provider_raw,
        )
        if series is not None:
            sequence: float | None = None
            if normalized.volume_number is not None:
                sequence = normalized.volume_number
            elif normalized.item_number:
                with contextlib.suppress(ValueError, TypeError):
                    sequence = float(normalized.item_number)
            self.db.add(
                BookSeriesMembership(
                    work_id=work.id,
                    series_id=series.id,
                    sequence=sequence,
                    display_number=normalized.item_number or normalized.volume_name,
                    metadata_json={"release_date": normalized.release_date.isoformat() if normalized.release_date else None},
                )
            )

        edition = BookEdition(
            work_id=work.id,
            display_title=normalized.edition_title or normalized.title,
            edition_statement=None,
            format=normalized.edition_format,
            binding=normalized.variant_type,
            publication_date=normalized.release_date,
            publisher=normalized.publisher,
            imprint=normalized.imprint,
            language=self._normalized_language(normalized.language),
            region=self._normalized_region(normalized.country),
            page_count=normalized.page_count,
            audio_length_minutes=(
                normalized.runtime_minutes
                if normalized.edition_format and "audio" in normalized.edition_format.lower()
                else None
            ),
            age_rating=normalized.age_rating,
            release_status=self._normalized_release_status(normalized.release_status),
            cover_image_url=mirrored_cover.url if mirrored_cover else normalized.cover_image_url,
            cover_image_key=mirrored_cover.key if mirrored_cover else None,
            description=normalized.synopsis,
            metadata_json=self._provider_metadata_json(
                provider_name,
                provider_item_id,
                kind=ItemKind.book,
                normalized={
                    "cover_storage": "mirror" if mirrored_cover else "provider",
                },
            ),
        )
        self.db.add(edition)
        await self.db.flush()

        for index, credit in enumerate(normalized.creators, start=1):
            person = await self._get_or_create_person(credit.name, credit)
            self.db.add(
                BookContribution(
                    work_id=None,
                    edition_id=edition.id,
                    person_id=person.id,
                    role=(credit.role or "author").strip().lower(),
                    sequence=index,
                    metadata_json={"role_id": credit.role_id} if credit.role_id else {},
                )
            )

        identifiers: list[tuple[str, str, bool]] = []
        if normalized.isbn:
            identifiers.append((self._book_identifier_type("isbn", normalized.isbn), normalized.isbn, True))
        if normalized.barcode:
            identifiers.append((self._book_identifier_type("upc", normalized.barcode), normalized.barcode, False))
        identifiers.append(("provider_item_id", provider_item_id, False))
        for _, provider_value in normalized.provider_ids.items():
            if provider_value:
                identifiers.append(("provider_item_id", provider_value, False))
        seen_identifier_keys: set[tuple[str, str]] = set()
        for identifier_type, value, is_primary in identifiers:
            normalized_value = self._normalized_identifier(value)
            if not normalized_value:
                continue
            dedupe_key = (identifier_type, normalized_value)
            if dedupe_key in seen_identifier_keys:
                continue
            seen_identifier_keys.add(dedupe_key)
            self.db.add(
                BookIdentifier(
                    edition_id=edition.id,
                    identifier_type=identifier_type,
                    value=value,
                    normalized_value=normalized_value,
                    is_primary=is_primary,
                    source_provider=provider_name,
                )
            )

        provider_ids = dict(normalized.provider_ids or {})
        provider_ids[provider_name.value] = provider_item_id
        await self._add_provider_links(
            provider_name,
            provider_ids,
            "book_work",
            work.id,
            provider_urls=provider_link_urls_for_provider(
                provider_name,
                provider_ids,
                provider_raw,
            ),
        )
        await self._record_provider_snapshot(
            provider=provider_name,
            provider_item_id=provider_item_id,
            entity_type="book_work",
            entity_id=work.id,
            source=provider_raw,
            normalized={
                "title": work.title,
                "series_title": normalized.series_title,
                "original_language": work.original_language,
            },
        )
        await self._record_provider_snapshot(
            provider=provider_name,
            provider_item_id=provider_item_id,
            entity_type="book_edition",
            entity_id=edition.id,
            source=provider_raw,
            normalized={
                "format": edition.format,
                "publication_date": str(edition.publication_date) if edition.publication_date else None,
                "publisher": edition.publisher,
            },
        )
        if mirrored_cover:
            await ImageCache(self.db).record_mirrored_cover(mirrored_cover)
        return work

    async def _create_tv_series_from_normalized(
        self,
        *,
        provider: MetadataProvider,
        provider_name: ExternalProvider,
        provider_item_id: str,
        provider_raw: Any | None,
        normalized: NormalizedItem,
    ) -> TVSeries:
        mirrored_cover = None
        if normalized.cover_image_url and self._should_mirror_provider_images(provider):
            mirrored_cover = await ImageMirror(self.db).mirror_cover_best_effort(
                source_url=normalized.cover_image_url,
                provider=provider_name,
                provider_item_id=provider_item_id,
            )

        season_fetcher = getattr(provider, "get_seasons", None)
        normalized_seasons = await season_fetcher(provider_item_id) if callable(season_fetcher) else []
        release_date = normalized.release_date
        if release_date is None:
            release_date = next((season.air_date for season in normalized_seasons if season.air_date), None)

        series = TVSeries(
            title=normalized.series_title or normalized.title,
            sort_title=sort_key(ItemKind.tv, normalized.series_title or normalized.title, normalized.item_number),
            overview=normalized.synopsis,
            first_air_date=release_date,
            last_air_date=max((season.air_date for season in normalized_seasons if season.air_date), default=None),
            status=normalized.release_status,
            type="tv",
            network=normalized.publisher,
            original_language=self._normalized_language(normalized.language),
            country=self._normalized_region(normalized.country),
            runtime_minutes=normalized.runtime_minutes,
            season_count=len(normalized_seasons) if normalized_seasons else None,
            episode_count=sum(len(season.episodes) for season in normalized_seasons) or None,
            poster_url=mirrored_cover.url if mirrored_cover else normalized.cover_image_url,
            backdrop_url=None,
            metadata_json=self._provider_metadata_json(
                provider_name,
                provider_item_id,
                kind=ItemKind.tv,
                normalized={"series_title": normalized.series_title},
            ),
        )
        self.db.add(series)
        await self.db.flush()

        release = TVRelease(
            series_id=series.id,
            title=normalized.edition_title or normalized.title,
            sort_title=sort_key(ItemKind.tv, normalized.title, None),
            description=normalized.synopsis,
            format=normalized.edition_format or "dvd",
            region_code=self._normalized_region(normalized.country),
            release_date=normalized.release_date,
            publisher=normalized.publisher,
            sku=normalized.barcode,
            runtime_minutes=normalized.runtime_minutes,
            content_rating=normalized.age_rating,
            cover_image_url=mirrored_cover.url if mirrored_cover else normalized.cover_image_url,
            cover_image_key=mirrored_cover.key if mirrored_cover else None,
            metadata_json=self._provider_metadata_json(
                provider_name,
                provider_item_id,
                kind=ItemKind.tv,
                normalized={"series_title": normalized.series_title},
            ),
        )
        self.db.add(release)
        await self.db.flush()

        media = TVReleaseMedia(
            release_id=release.id,
            media_number=1,
            media_type=normalized.edition_format or "dvd",
            title=normalized.edition_title,
            aspect_ratio=normalized.screen_ratio,
            color=normalized.color,
            audio_tracks=normalized.audio_tracks,
            subtitles=normalized.subtitles,
            layers=normalized.layers,
            metadata_json={},
        )
        self.db.add(media)
        await self.db.flush()

        if not normalized_seasons:
            normalized_seasons = [
                NormalizedSeason(
                    season_number=1,
                    title=normalized.series_title or normalized.title,
                    episodes=[
                        NormalizedEpisode(
                            episode_number=1,
                            title=normalized.title,
                            overview=normalized.synopsis,
                            air_date=normalized.release_date,
                            runtime_minutes=normalized.runtime_minutes,
                            still_url=normalized.cover_image_url,
                            image_url=normalized.cover_image_url,
                            large_image_url=normalized.cover_image_url,
                        )
                    ],
                )
            ]

        for season_data in normalized_seasons:
            season = TVSeason(
                series_id=series.id,
                season_number=season_data.season_number,
                title=season_data.title,
                overview=season_data.overview,
                air_date=season_data.air_date,
                episode_count=season_data.episode_count or len(season_data.episodes),
                poster_url=season_data.poster_url,
                metadata_json={
                    "provider_item_id": season_data.provider_item_id,
                },
            )
            self.db.add(season)
            await self.db.flush()

            for seq, episode_data in enumerate(season_data.episodes or [], start=1):
                episode = TVEpisode(
                    series_id=series.id,
                    season_id=season.id,
                    release_id=release.id,
                    media_id=media.id,
                    season_number=season_data.season_number,
                    episode_number=episode_data.episode_number,
                    title=episode_data.title,
                    overview=episode_data.overview,
                    duration_seconds=episode_data.runtime_minutes * 60 if episode_data.runtime_minutes else None,
                    original_air_date=episode_data.air_date,
                    still_url=episode_data.still_url,
                            image_url=episode_data.image_url,
                            large_image_url=episode_data.large_image_url,
                            metadata_json={
                                "provider_item_id": episode_data.provider_item_id,
                            },
                        )
                self.db.add(episode)
                await self.db.flush()
                self.db.add(
                    TVReleaseEpisodeMap(
                        release_id=release.id,
                        media_id=media.id,
                        episode_id=episode.id,
                        disc_number=1,
                        sequence_number=seq,
                        metadata_json={},
                    )
                )

        for index, credit in enumerate(normalized.creators, start=1):
            person = await self._get_or_create_person(credit.name, credit)
            self.db.add(
                TVReleaseContribution(
                    release_id=release.id,
                    person_id=person.id,
                    role=(credit.role or "cast").strip().lower(),
                    sequence=index,
                    metadata_json={"role_id": credit.role_id} if credit.role_id else {},
                )
            )

        identifiers: list[tuple[str, str, bool]] = []
        if normalized.barcode:
            identifiers.append(("barcode", normalized.barcode, True))
        if normalized.isbn:
            identifiers.append(("isbn", normalized.isbn, False))
        identifiers.append(("provider_item_id", provider_item_id, False))
        for _, provider_value in (normalized.provider_ids or {}).items():
            if provider_value:
                identifiers.append(("provider_item_id", provider_value, False))

        seen_identifier_keys: set[tuple[str, str]] = set()
        for identifier_type, value, is_primary in identifiers:
            normalized_value = self._normalized_identifier(value)
            if not normalized_value:
                continue
            dedupe_key = (identifier_type, normalized_value)
            if dedupe_key in seen_identifier_keys:
                continue
            seen_identifier_keys.add(dedupe_key)
            self.db.add(
                TVReleaseIdentifier(
                    release_id=release.id,
                    identifier_type=identifier_type,
                    value=value,
                    normalized_value=normalized_value,
                    is_primary=is_primary,
                    source_provider=provider_name,
                )
            )

        provider_ids = dict(normalized.provider_ids or {})
        provider_ids[provider_name.value] = provider_item_id
        await self._add_provider_links(
            provider_name,
            provider_ids,
            "tv_release",
            release.id,
            provider_urls=provider_link_urls_for_provider(
                provider_name,
                provider_ids,
                provider_raw,
            ),
        )

        await self._record_provider_snapshot(
            provider=provider_name,
            provider_item_id=provider_item_id,
            entity_type="tv_series",
            entity_id=series.id,
            source=provider_raw,
            normalized={
                "title": series.title,
                "series_title": normalized.series_title,
                "release_title": release.title,
            },
        )
        await self._record_provider_snapshot(
            provider=provider_name,
            provider_item_id=provider_item_id,
            entity_type="tv_release",
            entity_id=release.id,
            source=provider_raw,
            normalized={
                "title": release.title,
                "series_title": normalized.series_title,
                "format": release.format,
            },
        )

        if mirrored_cover:
            await ImageCache(self.db).record_mirrored_cover(mirrored_cover)

        return series

    async def _create_manga_work_from_normalized(
        self,
        *,
        provider: MetadataProvider,
        provider_name: ExternalProvider,
        provider_item_id: str,
        provider_raw: Any | None,
        normalized: NormalizedItem,
    ) -> MangaWork:
        """Create MangaWork from normalized item with chapters, contributions, identifiers, and character appearances."""
        mirrored_cover = None
        if normalized.cover_image_url and self._should_mirror_provider_images(provider):
            mirrored_cover = await ImageMirror(self.db).mirror_cover_best_effort(
                source_url=normalized.cover_image_url,
                provider=provider_name,
                provider_item_id=provider_item_id,
            )

        work = MangaWork(
            title=normalized.title,
            sort_title=sort_key(ItemKind.manga, normalized.title, normalized.item_number),
            subtitle=normalized.subtitle,
            description=normalized.synopsis,
            original_language=self._normalized_language(normalized.language),
            first_publication_date=normalized.release_date,
            metadata_json=self._provider_metadata_json(
                provider_name,
                provider_item_id,
                kind=ItemKind.manga,
                normalized={"series_title": normalized.series_title},
            ),
        )
        self.db.add(work)
        await self.db.flush()

        series = None
        if normalized.series_title:
            series = await self._get_or_create_manga_series(normalized.series_title)
            sequence: float | None = None
            if normalized.volume_number is not None:
                sequence = normalized.volume_number
            elif normalized.item_number:
                with contextlib.suppress(ValueError, TypeError):
                    sequence = float(normalized.item_number)
            existing_membership = await self.db.scalar(
                select(MangaSeriesMembership).where(
                    MangaSeriesMembership.work_id == work.id,
                    MangaSeriesMembership.series_id == series.id,
                )
            )
            if existing_membership is None:
                self.db.add(
                    MangaSeriesMembership(
                        work_id=work.id,
                        series_id=series.id,
                        sequence=sequence,
                        display_number=normalized.item_number or normalized.volume_name,
                    )
                )
            if normalized.relations:
                await self._link_manga_relations(series, normalized.relations)

        # Create single chapter from this normalized item
        chapter = MangaChapter(
            work_id=work.id,
            chapter_number=float(normalized.item_number) if normalized.item_number else None,
            chapter_title=normalized.edition_title or normalized.title,
            publication_date=normalized.release_date,
            page_count=normalized.page_count,
            description=normalized.synopsis,
            cover_image_url=mirrored_cover.url if mirrored_cover else normalized.cover_image_url,
            cover_image_key=mirrored_cover.key if mirrored_cover else None,
            metadata_json=self._provider_metadata_json(
                provider_name,
                provider_item_id,
                kind=ItemKind.manga,
                normalized={"chapter_number": normalized.item_number},
            ),
        )
        self.db.add(chapter)
        await self.db.flush()

        for index, credit in enumerate(normalized.creators, start=1):
            person = await self._get_or_create_person(credit.name, credit)
            self.db.add(
                MangaContribution(
                    work_id=work.id,
                    chapter_id=None,
                    person_id=person.id,
                    role=(credit.role or "creator").strip().lower(),
                    sequence=index,
                )
            )

        identifiers: list[tuple[str, str, bool]] = []
        if normalized.isbn:
            identifiers.append(
                (self._book_identifier_type("isbn", normalized.isbn), normalized.isbn, True)
            )
        if normalized.barcode:
            identifiers.append(
                (self._book_identifier_type("upc", normalized.barcode), normalized.barcode, False)
            )
        identifiers.append(("provider_item_id", provider_item_id, False))
        for _, provider_value in normalized.provider_ids.items():
            if provider_value:
                identifiers.append(("provider_item_id", provider_value, False))
        seen_identifier_keys: set[tuple[str, str]] = set()
        for identifier_type, value, is_primary in identifiers:
            normalized_value = self._normalized_identifier(value)
            if not normalized_value:
                continue
            dedupe_key = (identifier_type, normalized_value)
            if dedupe_key in seen_identifier_keys:
                continue
            seen_identifier_keys.add(dedupe_key)
            self.db.add(
                MangaIdentifier(
                    work_id=work.id,
                    identifier_type=identifier_type,
                    value=value,
                    normalized_value=normalized_value,
                    is_primary=is_primary,
                    source_provider=provider_name,
                )
            )

        seen_characters: set[tuple[str, str]] = set()
        for credit in normalized.characters:
            name = credit.name.strip()
            if not name:
                continue
            role = character_appearance_role(credit.role)
            dedupe_key = (name.casefold(), role.casefold())
            if dedupe_key in seen_characters:
                continue
            seen_characters.add(dedupe_key)
            character = await self._get_or_create_character(
                name,
                credit,
                provider=provider_name,
                provider_item_id=None,
            )
            self.db.add(
                MangaCharacterAppearance(
                    work_id=work.id,
                    character_id=character.id,
                    role=role,
                )
            )

        provider_ids = dict(normalized.provider_ids or {})
        provider_ids[provider_name.value] = provider_item_id
        await self._add_provider_links(
            provider_name,
            provider_ids,
            "manga_work",
            work.id,
            provider_urls=provider_link_urls_for_provider(
                provider_name,
                provider_ids,
                provider_raw,
            ),
        )
        await self._record_provider_snapshot(
            provider=provider_name,
            provider_item_id=provider_item_id,
            entity_type="manga_work",
            entity_id=work.id,
            source=provider_raw,
            normalized={
                "title": work.title,
                "series_title": normalized.series_title,
                "original_language": work.original_language,
            },
        )
        if mirrored_cover:
            await ImageCache(self.db).record_mirrored_cover(mirrored_cover)
        return work

    async def _link_manga_relations(
        self,
        source_series: MangaSeries,
        relations: list[NormalizedRelation],
    ) -> None:
        for rel in relations:
            try:
                relation_type = SeriesRelationType(rel.relation_type)
            except ValueError:
                continue
            target_series = await self._get_or_create_manga_series(rel.title)
            if target_series.id == source_series.id:
                continue
            existing = await self.db.scalar(
                select(MangaSeriesRelation.id).where(
                    MangaSeriesRelation.source_series_id == source_series.id,
                    MangaSeriesRelation.target_series_id == target_series.id,
                    MangaSeriesRelation.relation_type == relation_type,
                )
            )
            if existing:
                continue
            self.db.add(
                MangaSeriesRelation(
                    source_series_id=source_series.id,
                    target_series_id=target_series.id,
                    relation_type=relation_type,
                    provider=rel.provider,
                    provider_id=rel.provider_id,
                    start_year=rel.start_year,
                    image_url=rel.image_url,
                )
            )

    async def _create_anime_series_from_normalized(
        self,
        *,
        provider: MetadataProvider,
        provider_name: ExternalProvider,
        provider_item_id: str,
        provider_raw: Any | None,
        normalized: NormalizedItem,
    ) -> AnimeSeries:
        """Create AnimeSeries from normalized item with episodes, contributions, identifiers, and character appearances."""
        mirrored_cover = None
        if normalized.cover_image_url and self._should_mirror_provider_images(provider):
            mirrored_cover = await ImageMirror(self.db).mirror_cover_best_effort(
                source_url=normalized.cover_image_url,
                provider=provider_name,
                provider_item_id=provider_item_id,
            )

        series = AnimeSeries(
            title=normalized.title,
            sort_title=sort_key(ItemKind.anime, normalized.title, None),
            description=normalized.synopsis,
            original_language=self._normalized_language(normalized.language),
            original_air_date=normalized.release_date,
            status=normalized.release_status or "unknown",
            metadata_json=self._provider_metadata_json(
                provider_name,
                provider_item_id,
                kind=ItemKind.anime,
                normalized={},
            ),
        )
        self.db.add(series)
        await self.db.flush()

        # Create single episode from this normalized item
        episode = AnimeEpisode(
            series_id=series.id,
            episode_number=int(normalized.item_number) if normalized.item_number and normalized.item_number.isdigit() else None,
            episode_title=normalized.edition_title or normalized.title,
            air_date=normalized.release_date,
            description=normalized.synopsis,
            cover_image_url=mirrored_cover.url if mirrored_cover else normalized.cover_image_url,
            cover_image_key=mirrored_cover.key if mirrored_cover else None,
            runtime_minutes=normalized.runtime_minutes,
            metadata_json=self._provider_metadata_json(
                provider_name,
                provider_item_id,
                kind=ItemKind.anime,
                normalized={"episode_number": normalized.item_number},
            ),
        )
        self.db.add(episode)
        await self.db.flush()

        for index, credit in enumerate(normalized.creators, start=1):
            person = await self._get_or_create_person(credit.name, credit)
            self.db.add(
                AnimeContribution(
                    series_id=series.id,
                    episode_id=None,
                    person_id=person.id,
                    role=(credit.role or "creator").strip().lower(),
                    sequence=index,
                    metadata_json={"role_id": credit.role_id} if credit.role_id else {},
                )
            )

        identifiers: list[tuple[str, str, bool]] = []
        identifiers.append(("provider_item_id", provider_item_id, False))
        for _, provider_value in normalized.provider_ids.items():
            if provider_value:
                identifiers.append(("provider_item_id", provider_value, False))
        seen_identifier_keys: set[tuple[str, str]] = set()
        for identifier_type, value, is_primary in identifiers:
            normalized_value = self._normalized_identifier(value)
            if not normalized_value:
                continue
            dedupe_key = (identifier_type, normalized_value)
            if dedupe_key in seen_identifier_keys:
                continue
            seen_identifier_keys.add(dedupe_key)
            self.db.add(
                AnimeIdentifier(
                    series_id=series.id,
                    identifier_type=identifier_type,
                    value=value,
                    normalized_value=normalized_value,
                    is_primary=is_primary,
                    source_provider=provider_name,
                )
            )

        seen_characters: set[tuple[str, str]] = set()
        for credit in normalized.characters:
            name = credit.name.strip()
            if not name:
                continue
            role = character_appearance_role(credit.role)
            dedupe_key = (name.casefold(), role.casefold())
            if dedupe_key in seen_characters:
                continue
            seen_characters.add(dedupe_key)
            character = await self._get_or_create_character(
                name,
                credit,
                provider=provider_name,
                provider_item_id=None,
            )
            self.db.add(
                AnimeCharacterAppearance(
                    series_id=series.id,
                    character_id=character.id,
                    role=role,
                )
            )

        provider_ids = dict(normalized.provider_ids or {})
        provider_ids[provider_name.value] = provider_item_id
        await self._add_provider_links(
            provider_name,
            provider_ids,
            "anime_series",
            series.id,
            provider_urls=provider_link_urls_for_provider(
                provider_name,
                provider_ids,
                provider_raw,
            ),
        )
        await self._record_provider_snapshot(
            provider=provider_name,
            provider_item_id=provider_item_id,
            entity_type="anime_series",
            entity_id=series.id,
            source=provider_raw,
            normalized={
                "title": series.title,
                "original_language": series.original_language,
            },
        )
        if mirrored_cover:
            await ImageCache(self.db).record_mirrored_cover(mirrored_cover)
        return series

    async def _create_movie_work_from_normalized(
        self,
        *,
        provider: MetadataProvider,
        provider_name: ExternalProvider,
        provider_item_id: str,
        provider_raw: Any | None,
        normalized: NormalizedItem,
    ) -> MovieWork:
        """Create MovieWork from normalized item with releases, contributions, identifiers, and character appearances."""
        mirrored_cover = None
        if normalized.cover_image_url and self._should_mirror_provider_images(provider):
            mirrored_cover = await ImageMirror(self.db).mirror_cover_best_effort(
                source_url=normalized.cover_image_url,
                provider=provider_name,
                provider_item_id=provider_item_id,
            )

        work = MovieWork(
            title=normalized.title,
            sort_title=sort_key(ItemKind.movie, normalized.title, None),
            subtitle=normalized.subtitle,
            description=normalized.synopsis,
            original_language=self._normalized_language(normalized.language),
            original_release_date=normalized.release_date,
            runtime_minutes=normalized.runtime_minutes,
            age_rating=normalized.age_rating,
            audience_rating=normalized.audience_rating,
            metadata_json=self._provider_metadata_json(
                provider_name,
                provider_item_id,
                kind=ItemKind.movie,
                normalized={
                    "trailer_urls": normalized.trailer_urls,
                    "external_links": normalized.external_links,
                },
            ),
        )
        if normalized.trailer_urls or normalized.external_links:
            metadata = dict(work.metadata_json or {})
            metadata["trailer_urls"] = normalized.trailer_urls
            metadata["external_links"] = normalized.external_links
            work.metadata_json = metadata
        self.db.add(work)
        await self.db.flush()

        # Create single release from this normalized item
        release = MovieRelease(
            work_id=work.id,
            format=normalized.physical_format or normalized.edition_format or "digital",
            region_code=self._normalized_region(normalized.country),
            release_date=normalized.release_date,
            release_type=normalized.edition_format,
            color=normalized.color,
            distributor=normalized.distributor,
            cover_image_url=mirrored_cover.url if mirrored_cover else normalized.cover_image_url,
            cover_image_key=mirrored_cover.key if mirrored_cover else None,
            metadata_json=self._provider_metadata_json(
                provider_name,
                provider_item_id,
                kind=ItemKind.movie,
                normalized={"format": normalized.physical_format},
            ),
        )
        self.db.add(release)
        await self.db.flush()

        media = MovieReleaseMedia(
            release_id=release.id,
            media_number=1,
            media_type=normalized.physical_format or normalized.edition_format or "digital",
            title=normalized.edition_title,
            aspect_ratio=normalized.screen_ratio,
            color=normalized.color,
            num_discs=normalized.nr_discs,
            nr_layers=normalized.nr_discs,
            layers=normalized.layers,
            audio_tracks=normalized.audio_tracks,
            subtitles=normalized.subtitles,
            metadata_json=self._provider_metadata_json(
                provider_name,
                provider_item_id,
                kind=ItemKind.movie,
                normalized={
                    "format": normalized.physical_format,
                    "screen_ratio": normalized.screen_ratio,
                    "color": normalized.color,
                },
            ),
        )
        self.db.add(media)
        await self.db.flush()

        for index, credit in enumerate(normalized.creators, start=1):
            person = await self._get_or_create_person(credit.name, credit)
            self.db.add(
                MovieWorkContribution(
                    work_id=work.id,
                    person_id=person.id,
                    role=(credit.role or "creator").strip().lower(),
                    sequence=index,
                    metadata_json={"role_id": credit.role_id} if credit.role_id else {},
                )
            )
        for index, credit in enumerate(normalized.characters, start=1):
            name = credit.name.strip()
            if not name:
                continue
            person = await self._get_or_create_person(name, credit)
            self.db.add(
                MovieWorkContribution(
                    work_id=work.id,
                    person_id=person.id,
                    role="cast",
                    character_name=credit.role.strip() if credit.role else None,
                    sequence=index,
                    metadata_json={"role_id": credit.role_id} if credit.role_id else {},
                )
            )

        identifiers: list[tuple[str, str, bool]] = []
        identifiers.append(("provider_item_id", provider_item_id, False))
        for identifier_type, value in (normalized.external_ids or {}).items():
            if value:
                identifiers.append((identifier_type, value, identifier_type == "tmdb_id"))
        for _, provider_value in normalized.provider_ids.items():
            if provider_value:
                identifiers.append(("provider_item_id", provider_value, False))
        seen_identifier_keys: set[tuple[str, str]] = set()
        for identifier_type, value, is_primary in identifiers:
            normalized_value = self._normalized_identifier(value)
            if not normalized_value:
                continue
            dedupe_key = (identifier_type, normalized_value)
            if dedupe_key in seen_identifier_keys:
                continue
            seen_identifier_keys.add(dedupe_key)
            self.db.add(
                MovieWorkIdentifier(
                    work_id=work.id,
                    identifier_type=identifier_type,
                    value=value,
                    normalized_value=normalized_value,
                    is_primary=is_primary,
                    source_provider=provider_name,
                )
            )

        seen_characters: set[tuple[str, str]] = set()
        for credit in normalized.characters:
            name = credit.name.strip()
            if not name:
                continue
            role = character_appearance_role(credit.role)
            dedupe_key = (name.casefold(), role.casefold())
            if dedupe_key in seen_characters:
                continue
            seen_characters.add(dedupe_key)
            await self._get_or_create_character(
                name,
                credit,
                provider=provider_name,
                provider_item_id=None,
            )
            # Character appearances not supported in v1 Movie schema
            # self.db.add(
            #     MovieCharacterAppearance(
            #         work_id=work.id,
            #         character_id=character.id,
            #         role=role,
            #     )
            # )

        provider_ids = dict(normalized.provider_ids or {})
        provider_ids[provider_name.value] = provider_item_id
        await self._add_provider_links(
            provider_name,
            provider_ids,
            "movie_work",
            work.id,
            provider_urls=provider_link_urls_for_provider(
                provider_name,
                provider_ids,
                provider_raw,
            ),
        )
        await self._record_provider_snapshot(
            provider=provider_name,
            provider_item_id=provider_item_id,
            entity_type="movie_work",
            entity_id=work.id,
            source=provider_raw,
            normalized={
                "title": work.title,
                "original_language": work.original_language,
                "runtime_minutes": work.runtime_minutes,
                "trailer_urls": normalized.trailer_urls,
                "external_links": normalized.external_links,
            },
        )
        if mirrored_cover:
            await ImageCache(self.db).record_mirrored_cover(mirrored_cover)
        return work

    async def _create_music_release_from_normalized(
        self,
        *,
        provider: MetadataProvider,
        provider_name: ExternalProvider,
        provider_item_id: str,
        provider_raw: Any | None,
        normalized: NormalizedItem,
    ) -> MusicRelease:
        """Create MusicRelease from normalized item with media, tracks, contributions, identifiers, and provider links."""
        mirrored_cover = None
        if normalized.cover_image_url and self._should_mirror_provider_images(provider):
           mirrored_cover = await ImageMirror(self.db).mirror_cover_best_effort(
               source_url=normalized.cover_image_url,
               provider=provider_name,
               provider_item_id=provider_item_id,
           )

        # Create MusicRelease (represents the published product/album)
        release = MusicRelease(
           title=normalized.title,
           sort_title=sort_key(ItemKind.music, normalized.title, None),
           subtitle=normalized.subtitle,
           release_date=normalized.release_date,
           media_count=len({track.disc_number or 1 for track in (normalized.tracks or [])}) or None,
           track_count=normalized.track_count or (len(normalized.tracks) if normalized.tracks else None),
           catalog_number=normalized.catalog_number,
           release_status=normalized.release_status,
           publisher=normalized.publisher,
           studio=normalized.studio,
           recording_date=normalized.recording_date,
           barcode=normalized.barcode,
           country_code=normalized.country,
           language=self._normalized_language(normalized.language),
           extras=normalized.extras,
           cover_image_url=mirrored_cover.url if mirrored_cover else normalized.cover_image_url,
           cover_image_key=mirrored_cover.key if mirrored_cover else None,
           metadata_json=self._provider_metadata_json(
               provider_name,
               provider_item_id,
               kind=ItemKind.music,
               normalized={},
           ),
        )
        self.db.add(release)
        await self.db.flush()

        # Create MusicMedia (represents physical media, typically discs)
        # Group tracks by disc_number if available
        discs: dict[int | None, list[NormalizedTrack]] = {}
        for track in (normalized.tracks or []):
            disc_num = track.disc_number or 1
            if disc_num not in discs:
                discs[disc_num] = []
            discs[disc_num].append(track)

        # If no tracks, create a single media entry
        if not discs:
            discs = {1: []}

        for media_number, disc_tracks in sorted(discs.items()):
            media = MusicMedia(
                release_id=release.id,
                media_number=media_number,
                media_type=normalized.physical_format or normalized.edition_format or "digital",
                track_count=len(disc_tracks) or None,
                packaging=normalized.packaging,
                media_condition=normalized.media_condition,
                sound_type=normalized.sound_type,
                vinyl_color=normalized.vinyl_color,
                vinyl_weight=normalized.vinyl_weight,
                rpm=normalized.rpm,
                spars=normalized.spars,
                metadata_json=self._provider_metadata_json(
                    provider_name,
                    provider_item_id,
                    kind=ItemKind.music,
                    normalized={"format": normalized.physical_format or normalized.edition_format},
                ),
            )
            self.db.add(media)
            await self.db.flush()

            # Create MusicTrack entities for this disc
            for track_index, track in enumerate(disc_tracks, start=1):
                music_track = MusicTrack(
                   media_id=media.id,
                   release_id=release.id,
                   position=str(track.position or track_index),
                   title=track.title,
                   duration_ms=(track.duration_seconds * 1000) if track.duration_seconds else None,
                   instrument=track.instrument,
                   composition=track.composition,
                   metadata_json={},
                )
                self.db.add(music_track)

        # Add contributions (artists, composers, producers)
        for index, credit in enumerate(normalized.creators, start=1):
            person = await self._get_or_create_person(credit.name, credit)
            self.db.add(
                MusicReleaseContribution(
                    release_id=release.id,
                    person_id=person.id,
                    role=(credit.role or "artist").strip().lower(),
                    sequence=index,
                    metadata_json={"role_id": credit.role_id} if credit.role_id else {},
                )
            )

        # Add identifiers (provider IDs, ISRC, catalog number, barcode)
        identifiers: list[tuple[str, str, bool]] = []
        if normalized.catalog_number:
            identifiers.append(("catalog_number", normalized.catalog_number, True))
        if normalized.barcode:
            identifiers.append(("barcode", normalized.barcode, False))
        identifiers.append(("provider_item_id", provider_item_id, False))
        for _, provider_value in (normalized.provider_ids or {}).items():
            if provider_value:
                identifiers.append(("provider_item_id", provider_value, False))

        seen_identifier_keys: set[tuple[str, str]] = set()
        for identifier_type, value, is_primary in identifiers:
            normalized_value = self._normalized_identifier(value)
            if not normalized_value:
                continue
            dedupe_key = (identifier_type, normalized_value)
            if dedupe_key in seen_identifier_keys:
                continue
            seen_identifier_keys.add(dedupe_key)
            self.db.add(
                MusicReleaseIdentifier(
                    release_id=release.id,
                    identifier_type=identifier_type,
                    value=value,
                    normalized_value=normalized_value,
                    is_primary=is_primary,
                    source_provider=provider_name,
                )
            )

        # Add provider links
        provider_ids = dict(normalized.provider_ids or {})
        provider_ids[provider_name.value] = provider_item_id
        await self._add_provider_links(
           provider_name,
           provider_ids,
           "music_release",
           release.id,
           provider_urls=provider_link_urls_for_provider(
               provider_name,
               provider_ids,
               provider_raw,
           ),
        )

        # Record provider snapshot
        await self._record_provider_snapshot(
           provider=provider_name,
           provider_item_id=provider_item_id,
           entity_type="music_release",
           entity_id=release.id,
           source=provider_raw,
           normalized={
               "title": release.title,
               "language": release.language,
               "track_count": len(normalized.tracks) if normalized.tracks else 0,
           },
        )

        if mirrored_cover:
           await ImageCache(self.db).record_mirrored_cover(mirrored_cover)

        return release

    async def _reindex_comic_work(self, work_id: UUID) -> None:
        work = await self.db.scalar(
            select(ComicWork)
            .where(ComicWork.id == work_id)
            .options(
                selectinload(ComicWork.contributions).selectinload(ComicContribution.person),
                selectinload(ComicWork.issues)
                .selectinload(ComicIssue.contributions)
                .selectinload(ComicContribution.person),
                selectinload(ComicWork.issues).selectinload(ComicIssue.identifiers),
                selectinload(ComicWork.issues)
                .selectinload(ComicIssue.character_appearances)
                .selectinload(ComicCharacterAppearance.character),
                selectinload(ComicWork.issues)
                .selectinload(ComicIssue.story_arc_memberships)
                .selectinload(ComicStoryArcMembership.story_arc),
            )
        )
        if work is None:
            return
        await SearchClient().index_documents_best_effort([comic_work_search_document(work)])

    async def _reindex_game_work(self, work_id: UUID) -> None:
        work = await self.db.scalar(
            select(GameWork)
            .where(GameWork.id == work_id)
            .options(selectinload(GameWork.releases))
        )
        if work is None:
            return
        await SearchClient().index_documents_best_effort([game_work_search_document(work)])

    async def _reindex_book_work(self, work_id: UUID) -> None:
        work = await self.db.scalar(
            select(BookWork)
            .where(BookWork.id == work_id)
            .options(
                selectinload(BookWork.contributions).selectinload(BookContribution.person),
                selectinload(BookWork.series_memberships).selectinload(BookSeriesMembership.series),
                selectinload(BookWork.editions)
                .selectinload(BookEdition.contributions)
                .selectinload(BookContribution.person),
                selectinload(BookWork.editions).selectinload(BookEdition.identifiers),
            )
        )
        if work is None:
            return
        await SearchClient().index_documents_best_effort([book_work_search_document(work)])

    async def _reindex_boardgame_work(self, work_id: UUID) -> None:
        work = await self.db.scalar(
            select(BoardGameWork)
            .where(BoardGameWork.id == work_id)
            .options(selectinload(BoardGameWork.editions))
        )
        if work is None:
            return
        await SearchClient().index_documents_best_effort([boardgame_search_document(work)])

    async def _reindex_manga_work(self, work_id: UUID) -> None:
        work = await self.db.scalar(
            select(MangaWork)
            .where(MangaWork.id == work_id)
            .options(
                selectinload(MangaWork.contributions).selectinload(MangaContribution.person),
                selectinload(MangaWork.chapters),
                selectinload(MangaWork.identifiers),
                selectinload(MangaWork.character_appearances).selectinload(MangaCharacterAppearance.character),
            )
        )
        if work is None:
            return
        await SearchClient().index_documents_best_effort([manga_work_search_document(work)])

    async def _reindex_anime_series(self, series_id: UUID) -> None:
        series = await self.db.scalar(
            select(AnimeSeries)
            .where(AnimeSeries.id == series_id)
            .options(
                selectinload(AnimeSeries.contributions).selectinload(AnimeContribution.person),
                selectinload(AnimeSeries.episodes),
                selectinload(AnimeSeries.identifiers),
                selectinload(AnimeSeries.character_appearances).selectinload(AnimeCharacterAppearance.character),
            )
        )
        if series is None:
            return
        await SearchClient().index_documents_best_effort([anime_series_search_document(series)])

    async def _reindex_movie_work(self, work_id: UUID) -> None:
        work = await self.db.scalar(
            select(MovieWork)
            .where(MovieWork.id == work_id)
            .options(
                selectinload(MovieWork.contributions).selectinload(MovieWorkContribution.person),
                selectinload(MovieWork.releases),
                selectinload(MovieWork.identifiers),
            )
        )
        if work is None:
            return
        await SearchClient().index_documents_best_effort([movie_work_search_document(work)])

    async def _reindex_tv_series(self, series_id: UUID) -> None:
        series = await self.db.scalar(
            select(TVSeries)
            .where(TVSeries.id == series_id)
            .options(
                selectinload(TVSeries.seasons).selectinload(TVSeason.episodes),
                selectinload(TVSeries.releases).selectinload(TVRelease.contributions).selectinload(
                    TVReleaseContribution.person
                ),
                selectinload(TVSeries.releases).selectinload(TVRelease.identifiers),
                selectinload(TVSeries.releases).selectinload(TVRelease.media),
            )
        )
        if series is None:
            return
        await SearchClient().index_documents_best_effort([tv_release_search_document(series)])

    def _comic_identifier_type(self, base_type: str, value: str) -> str:
        return comic_identifier_type(base_type, value)

    def _book_identifier_type(self, base_type: str, value: str) -> str:
        return book_identifier_type(base_type, value)

    def _normalized_identifier(self, value: str) -> str:
        return normalized_identifier(value)

    async def _get_or_create_organization(self, name: str, organization_type: str) -> Organization:
        result = await self.db.execute(
            select(Organization).where(Organization.name == name, Organization.type == organization_type)
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
        result = await self.db.execute(select(Person).where(Person.name == display_name))
        person = result.scalar_one_or_none()
        if person is None and display_name != name:
            result = await self.db.execute(select(Person).where(Person.name == name))
            person = result.scalar_one_or_none()
        if person is None:
            person = Person(
                name=display_name,
                sort_name=credit.sort_name,
                api_detail_url=credit.api_detail_url,
                site_detail_url=credit.site_detail_url,
                image_url=credit.image_url,
                external_ids=dict(credit.external_ids or {}) or None,
            )
            self.db.add(person)
            await self.db.flush()
            return person
        if not person.sort_name and credit.sort_name:
            person.sort_name = credit.sort_name
        if not person.api_detail_url and credit.api_detail_url:
            person.api_detail_url = credit.api_detail_url
        if not person.site_detail_url and credit.site_detail_url:
            person.site_detail_url = credit.site_detail_url
        if not person.image_url and credit.image_url:
            person.image_url = credit.image_url
        if credit.external_ids:
            merged_external_ids = dict(person.external_ids or {})
            for key, value in credit.external_ids.items():
                if value and not merged_external_ids.get(key):
                    merged_external_ids[key] = value
            if merged_external_ids != (person.external_ids or {}):
                person.external_ids = merged_external_ids
        credit_description = getattr(credit, "description", None)
        if not person.description and credit_description:
            person.description = credit_description
        return person

    async def _get_or_create_story_arc(self, name: str, credit: NormalizedCredit) -> StoryArc:
        result = await self.db.execute(select(StoryArc).where(StoryArc.name == name))
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
                api_detail_url=credit.api_detail_url,
                site_detail_url=credit.site_detail_url,
            )
            self.db.add(story_arc)
            await self.db.flush()
            return story_arc
        if not story_arc.api_detail_url and credit.api_detail_url:
            story_arc.api_detail_url = credit.api_detail_url
        if not story_arc.site_detail_url and credit.site_detail_url:
            story_arc.site_detail_url = credit.site_detail_url
        credit_description = getattr(credit, "description", None)
        if not story_arc.description and credit_description:
            story_arc.description = credit_description
        return story_arc

    async def _get_or_create_character(
        self,
        name: str,
        credit: NormalizedCredit,
        *,
        provider: ExternalProvider,
        provider_item_id: str | None,
    ) -> Character:
        character = await self._character_by_provider_link(provider, provider_item_id)
        if character is None:
            character = await self._character_by_identity(name, credit)
        canonical_name = _canonical_character_name(name)
        if character is None:
            character = Character(
                name=name,
                canonical_name=canonical_name,
                api_detail_url=credit.api_detail_url,
                site_detail_url=credit.site_detail_url,
            )
            self.db.add(character)
            await self.db.flush()
            return character
        if not character.canonical_name and canonical_name:
            character.canonical_name = canonical_name
        if not character.api_detail_url and credit.api_detail_url:
            character.api_detail_url = credit.api_detail_url
        if not character.site_detail_url and credit.site_detail_url:
            character.site_detail_url = credit.site_detail_url
        credit_description = getattr(credit, "description", None)
        if not character.description and credit_description:
            character.description = credit_description
        return character

    async def _character_by_provider_link(
        self,
        provider: ExternalProvider,
        provider_item_id: str | None,
    ) -> Character | None:
        if not provider_item_id:
            return None
        character_id = await self.db.scalar(
            select(ExternalProviderId.entity_id).where(
                ExternalProviderId.provider == provider,
                ExternalProviderId.provider_item_id == provider_item_id,
                ExternalProviderId.entity_type == "character",
            )
        )
        if character_id is None:
            return None
        return await self.db.get(Character, character_id)

    async def _character_by_identity(self, name: str, credit: NormalizedCredit) -> Character | None:
        canonical_name = _canonical_character_name(name)
        rows = list(
            (
                await self.db.execute(
                    select(Character).where(
                        or_(
                            Character.name == name,
                            Character.canonical_name == canonical_name,
                        )
                    )
                )
            ).scalars()
        )
        if not rows:
            return None
        matched_by_url = [row for row in rows if self._character_matches_credit_urls(row, credit)]
        if len(matched_by_url) == 1:
            return matched_by_url[0]
        if len(rows) == 1 and not self._credit_has_identity_urls(credit):
            return rows[0]
        return None

    def _character_matches_credit_urls(self, character: Character, credit: NormalizedCredit) -> bool:
        return any(
            value and current == value
            for key, value in (
                ("api_detail_url", credit.api_detail_url),
                ("site_detail_url", credit.site_detail_url),
            )
            for current in [getattr(character, key, None)]
        )

    def _credit_has_identity_urls(self, credit: NormalizedCredit) -> bool:
        return bool(credit.api_detail_url or credit.site_detail_url)

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
            and character.first_appearance_entity_type
            and character.first_appearance_entity_id
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
        if not character.api_detail_url and detail.api_detail_url:
            character.api_detail_url = detail.api_detail_url
        if not character.site_detail_url and detail.site_detail_url:
            character.site_detail_url = detail.site_detail_url
        if detail.first_appeared_in_issue_id:
            first_item_id = await self._local_entity_id_for_provider_id(
                ExternalProvider.comicvine,
                detail.first_appeared_in_issue_id,
                "comic_issue",
            )
            if first_item_id is not None:
                character.first_appearance_entity_type = "comic_issue"
                character.first_appearance_entity_id = first_item_id
            elif detail.first_appeared_in_issue_id == await self._provider_id_for_entity(
                ExternalProvider.comicvine,
                current_item_id,
                "comic_issue",
            ):
                character.first_appearance_entity_type = "comic_issue"
                character.first_appearance_entity_id = current_item_id

    async def _comicvine_character_detail(self, provider_item_id: str) -> Any | None:
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

    async def _local_entity_id_for_provider_id(
        self,
        provider: ExternalProvider,
        provider_item_id: str,
        entity_type: str,
    ) -> UUID | None:
        return await self.db.scalar(
            select(ExternalProviderId.entity_id).where(
                ExternalProviderId.provider == provider,
                ExternalProviderId.provider_item_id == provider_item_id,
                ExternalProviderId.entity_type == entity_type,
            )
        )

    async def _provider_id_for_entity(
        self,
        provider: ExternalProvider,
        entity_id: UUID,
        entity_type: str,
    ) -> str | None:
        return await self.db.scalar(
            select(ExternalProviderId.provider_item_id).where(
                ExternalProviderId.provider == provider,
                ExternalProviderId.entity_id == entity_id,
                ExternalProviderId.entity_type == entity_type,
            )
        )

    def _merge_aliases(
        self,
        existing: list[str],
        incoming: list[str] | None,
        *,
        primary_name: str,
    ) -> list[str]:
        aliases: list[str] = []
        seen = {primary_name.casefold()}
        for value in [*existing, *(incoming or [])]:
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


def _canonical_character_name(name: str) -> str | None:
    value = " ".join(str(name or "").split()).strip()
    if not value:
        return None
    return value.casefold()
