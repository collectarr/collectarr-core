import logging
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import selectinload

from app.catalog.physical_formats import (
    PhysicalFormatConfig,
    is_video_item_kind,
    physical_format_for_id,
)
from app.core.errors import ApiHTTPException
from app.metadata_normalized import clean_normalized_metadata, upsert_item_kind_metadata
from app.models.base import ExternalProvider, ItemKind, SeriesRelationType
from app.models.canonical import (
    BookContribution,
    BookEdition,
    BookIdentifier,
    BookSeriesMembership,
    BookWork,
    BundleRelease,
    BundleReleaseItem,
    BundleReleaseProviderLink,
    Character,
    CharacterAppearance,
    Edition,
    EntityOrganization,
    EntityPerson,
    EntityTag,
    ExternalProviderId,
    Item,
    ItemProviderLink,
    MetadataProposal,
    Organization,
    Person,
    ProviderIngestJob,
    ProviderPayloadSnapshot,
    PhysicalFormatRef,
    ReleaseStatus,
    Series,
    SeriesRelation,
    StoryArc,
    StoryArcItem,
    Tag,
    Variant,
    Volume,
    VolumeProviderLink,
)
from app.proposal_payload import compact_metadata_payload
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
from app.providers.comicvine import ComicVineProvider
from app.providers.normalize import normalize_arc_title, normalize_person_name
from app.providers.registry import ProviderRegistry
from app.repositories.metadata import MetadataRepository
from app.search.client import SearchClient
from app.search.documents import book_work_search_document
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
from app.services.admin_domains.shared import (
    character_appearance_role,
    character_role_rank,
    comicvine_credit_provider_id,
    credit_provider_urls,
    provider_link_url_text,
    provider_link_urls_for_provider,
    slug,
    sort_key,
)
from app.services.metadata import MetadataService
from app.services.provider_preview_state import HydratedProviderPreview
from app.storage.image_cache import ImageCache
from app.storage.images import ImageMirror

logger = logging.getLogger(__name__)
_LANGUAGE_RE = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$")
_REGION_RE = re.compile(r"^[A-Z]{2}(?:-[A-Z0-9]{1,3})?$")
_SNAPSHOT_TTL = timedelta(days=30)


def _normalized_residual(values: dict[str, Any], *, kind: ItemKind) -> dict[str, Any]:
    return clean_normalized_metadata(values, kind=kind)


@dataclass(frozen=True)
class CatalogProviderLinkRef:
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
            select(ItemProviderLink)
            .where(
                ItemProviderLink.updated_at < cutoff,
            )
            .order_by(ItemProviderLink.updated_at.asc())
            .limit(limit)
        )
        provider_ids = result.scalars().all()
        refreshed = 0
        for pid in provider_ids:
            try:
                await self._refresh_item_from_provider(pid)
                refreshed += 1
            except Exception:
                pass
        if refreshed:
            await self.db.commit()
        return refreshed

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
                    item_id=response.item_id,
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
        if normalized.bundle_release is not None:
            item = await self._ingest_bundle_release(
                provider=provider,
                provider_name=payload.provider,
                provider_item=provider_item,
                normalized=normalized,
            )
            await self.db.commit()
            loaded_item = await MetadataRepository(self.db).get_item(item.id)
            if loaded_item:
                await self._reindex_items({item.id})
            return ProviderIngestResponse(
                item_id=item.id,
                created=True,
                item=await self._item_response(loaded_item),
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
            await self._reindex_items({item.id})
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

    async def _get_provider_id(self, payload: ProviderIngestRequest) -> CatalogProviderLinkRef | None:
        return await self._get_provider_id_value(payload.provider, payload.provider_item_id)

    async def _get_provider_id_value(
        self,
        provider: ExternalProvider,
        provider_item_id: str,
    ) -> CatalogProviderLinkRef | None:
        external_ref = await self.db.execute(
            select(ExternalProviderId.entity_type, ExternalProviderId.entity_id).where(
                ExternalProviderId.provider == provider,
                ExternalProviderId.provider_item_id == provider_item_id,
                ExternalProviderId.entity_type.in_(["item", "bundle_release", "book_work"]),
            )
        )
        external_row = external_ref.first()
        if external_row is not None:
            return CatalogProviderLinkRef(
                entity_type=str(external_row[0]),
                entity_id=external_row[1],
                provider_item_id=provider_item_id,
            )
        catalog_tables = (
            ("bundle_release", BundleReleaseProviderLink, BundleReleaseProviderLink.bundle_release_id),
            ("item", ItemProviderLink, ItemProviderLink.item_id),
        )
        for entity_type, model, owner_column in catalog_tables:
            entity_id = await self.db.scalar(
                select(owner_column).where(
                    model.provider == provider,
                    model.provider_item_id == provider_item_id,
                )
            )
            if entity_id is not None:
                return CatalogProviderLinkRef(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    provider_item_id=provider_item_id,
                )
        return None

    async def _existing_response(self, provider_id: CatalogProviderLinkRef) -> ProviderIngestResponse:
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

    def _provider_metadata_json(
        self,
        provider_name: ExternalProvider,
        provider_item_id: str,
        *,
        kind: ItemKind,
        normalized: dict[str, Any] | None = None,
        source: Any | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "provider": provider_name.value,
            "provider_item_id": provider_item_id,
        }
        normalized_payload = _normalized_residual(normalized or {}, kind=kind)
        if normalized_payload:
            metadata["normalized"] = normalized_payload
        if source is not None:
            metadata["source"] = source
        return metadata

    def _normalized_release_status(self, value: str | None) -> str | None:
        text = " ".join(str(value or "").split()).strip().lower()
        return text or None

    def _normalized_language(self, value: str | None) -> str | None:
        text = " ".join(str(value or "").split()).strip().lower()
        if not text:
            return None
        return text if _LANGUAGE_RE.match(text) else None

    def _normalized_region(self, value: str | None) -> str | None:
        text = " ".join(str(value or "").split()).strip().upper()
        if not text:
            return None
        return text if _REGION_RE.match(text) else None

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

    def _upsert_item_kind_metadata(self, item: Item, normalized_values: dict[str, Any]) -> None:
        upsert_item_kind_metadata(item, normalized_values)

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

    async def _refresh_item_from_provider(self, pid: ItemProviderLink) -> None:
        registry = ProviderRegistry()
        provider = registry.get(pid.provider)
        if provider is None or not provider.is_configured:
            pid.updated_at = datetime.now(UTC)
            return
        provider_item = await provider.get_item(pid.provider_item_id)
        normalized = await provider.normalize(provider_item.raw)
        item = await self.db.get(Item, pid.item_id)
        if item is None:
            return
        item.title = normalized.title
        item.synopsis = normalized.synopsis
        item.runtime_minutes = normalized.runtime_minutes
        item.page_count = normalized.page_count
        primary_edition = await self.db.scalar(
            select(Edition)
            .where(Edition.item_id == item.id)
            .order_by(
                Edition.release_date.desc().nullslast(),
                Edition.created_at.asc(),
                Edition.id.asc(),
            )
            .limit(1)
        )
        if primary_edition is not None:
            refresh_release_status = self._normalized_release_status(normalized.release_status)
            if refresh_release_status is not None:
                await self._ensure_release_status(refresh_release_status)
            primary_edition.nr_discs = normalized.nr_discs
            primary_edition.screen_ratio = normalized.screen_ratio
            primary_edition.audio_tracks = normalized.audio_tracks
            primary_edition.subtitles = normalized.subtitles
            primary_edition.layers = normalized.layers
            primary_edition.release_status = refresh_release_status
            primary_edition.language = self._normalized_language(normalized.language)
            primary_edition.region = self._normalized_region(normalized.country)
        metadata = dict(item.metadata_json or {})
        metadata["source"] = provider_item.raw
        metadata["last_refresh"] = datetime.now(UTC).isoformat()
        item.metadata_json = metadata
        await self._record_provider_snapshot(
            provider=pid.provider,
            provider_item_id=pid.provider_item_id,
            entity_type="item",
            entity_id=item.id,
            source=provider_item.raw,
            normalized={
                "audience_rating": normalized.audience_rating,
                "genres": normalized.genres,
                "platforms": normalized.platforms,
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
                ],
                "color": normalized.color,
                "release_status": normalized.release_status,
            },
        )
        self._upsert_item_kind_metadata(
            item,
            {
                "audience_rating": normalized.audience_rating,
                "genres": normalized.genres or None,
                "platforms": normalized.platforms or None,
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
                "color": normalized.color,
            },
        )
        pid.updated_at = datetime.now(UTC)

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
                    cover_image_url=mirrored_cover.url if mirrored_cover else cover.cover_image_url,
                    thumbnail_image_key=mirrored_cover.thumbnail_key if mirrored_cover else None,
                    thumbnail_image_url=(
                        mirrored_cover.thumbnail_url if mirrored_cover else cover.thumbnail_image_url
                    ),
                    description=cover.caption,
                    metadata_json=self._provider_metadata_json(
                        provider_name,
                        cover.provider_item_id or provider_item_id,
                        kind=normalized.kind,
                        normalized={
                            "associated_image_id": cover.source_id,
                            **cover_metadata,
                        },
                    ),
                    is_primary=False,
                )
            )
        return variants, mirrored_covers

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
        metadata_repo = MetadataRepository(self.db)
        created_members: list[tuple[NormalizedBundleMember, Item, Volume | None, Series | None]] = []
        for index, member in enumerate(members, start=1):
            member_provider_item_id = self._bundle_member_provider_item_id(
                provider_name,
                provider_item.provider_item_id,
                member,
                index,
            )
            existing_ref = await self._get_provider_id_value(
                provider_name,
                member_provider_item_id,
            )
            member_item: Item | None = None
            member_volume: Volume | None = None
            member_series: Series | None = None
            if existing_ref is not None:
                if existing_ref.entity_type != "item":
                    raise ApiHTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        code="provider_link_stale",
                        detail="Provider link is stale",
                    )
                member_item = await metadata_repo.get_item(existing_ref.entity_id)
                if member_item is None:
                    raise ApiHTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        code="provider_link_stale",
                        detail="Provider link is stale",
                    )
                member_volume = member_item.volume
                member_series = member_volume.series if member_volume is not None else None
            else:
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
            (
                (member, item, volume, series)
                for member, item, volume, series in created_members
                if member.is_primary
            ),
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
            region=self._normalized_region(bundle_normalized.region),
            language=self._normalized_language(bundle_normalized.language),
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
            metadata_json=self._provider_metadata_json(
                provider_name,
                provider_item.provider_item_id,
                kind=normalized.kind,
                normalized=cover_metadata,
                source=provider_item.raw,
            ),
        )
        self.db.add(bundle)
        await self.db.flush()
        await self._record_provider_snapshot(
            provider=provider_name,
            provider_item_id=provider_item.provider_item_id,
            entity_type="bundle_release",
            entity_id=bundle.id,
            source=provider_item.raw,
            normalized=cover_metadata,
        )
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
        await self._replace_bundle_release_provider_links(
            bundle.id,
            provider_name,
            bundle_normalized.provider_ids,
            provider_urls=provider_link_urls_for_provider(
                provider_name,
                bundle_normalized.provider_ids,
                provider_item.raw,
            ),
        )
        return primary_item

    def _bundle_members_for_ingest(self, normalized: NormalizedItem) -> list[NormalizedBundleMember]:
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
        if physical_format is not None:
            await self._ensure_physical_format_ref(physical_format)
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
            normalized.volume_number,
            normalized.volume_start_year,
        )
        item = Item(
            volume=volume,
            kind=normalized.kind,
            title=normalized.title,
            item_number=normalized.item_number,
            sort_key=sort_key(normalized.kind, normalized.title, normalized.item_number),
            synopsis=normalized.synopsis,
            runtime_minutes=normalized.runtime_minutes,
            page_count=normalized.page_count,
            metadata_json=self._provider_metadata_json(
                provider_name,
                provider_item_id,
                kind=normalized.kind,
                normalized=cover_metadata,
            ),
        )
        release_status = self._normalized_release_status(normalized.release_status)
        if release_status is not None:
            await self._ensure_release_status(release_status)
        edition = Edition(
            item=item,
            title=normalized.edition_title or "Standard Edition",
            format=edition_format,
            physical_format=physical_format.id if physical_format else None,
            physical_format_label=physical_format.label if physical_format else None,
            physical_format_media_family=physical_format.media_family if physical_format else None,
            physical_format_variant_type=physical_format.variant_type if physical_format else None,
            publisher=normalized.publisher,
            isbn=normalized.isbn,
            imprint=normalized.imprint,
            subtitle=normalized.subtitle,
            series_group=normalized.series_group,
            age_rating=normalized.age_rating,
            catalog_number=normalized.catalog_number,
            release_status=release_status,
            nr_discs=normalized.nr_discs,
            screen_ratio=normalized.screen_ratio,
            audio_tracks=normalized.audio_tracks,
            subtitles=normalized.subtitles,
            layers=normalized.layers,
            language=self._normalized_language(normalized.language),
            region=self._normalized_region(normalized.country),
            release_date=normalized.release_date,
            metadata_json=self._provider_metadata_json(
                provider_name,
                provider_item_id,
                kind=normalized.kind,
                normalized={
                    "physical_format": physical_format.id if physical_format else None,
                    "physical_format_label": physical_format.label if physical_format else None,
                    "physical_format_media_family": physical_format.media_family if physical_format else None,
                    "physical_format_variant_type": physical_format.variant_type if physical_format else None,
                    **cover_metadata,
                },
                source=provider_raw,
            ),
        )
        variant = Variant(
            edition=edition,
            name=variant_name,
            variant_type=variant_type,
            physical_format=physical_format.id if physical_format else None,
            physical_format_label=physical_format.label if physical_format else None,
            physical_format_media_family=physical_format.media_family if physical_format else None,
            physical_format_variant_type=physical_format.variant_type if physical_format else None,
            barcode=normalized.barcode,
            isbn=normalized.isbn,
            cover_price_cents=normalized.cover_price_cents,
            currency=normalized.currency,
            cover_image_key=mirrored_cover.key if mirrored_cover else None,
            cover_image_url=mirrored_cover.url if mirrored_cover else normalized.cover_image_url,
            thumbnail_image_key=mirrored_cover.thumbnail_key if mirrored_cover else None,
            thumbnail_image_url=mirrored_cover.thumbnail_url if mirrored_cover else None,
            metadata_json=self._provider_metadata_json(
                provider_name,
                provider_item_id,
                kind=normalized.kind,
                normalized={
                    "physical_format": physical_format.id if physical_format else None,
                    "physical_format_label": physical_format.label if physical_format else None,
                    "physical_format_media_family": physical_format.media_family if physical_format else None,
                    "physical_format_variant_type": physical_format.variant_type if physical_format else None,
                    **cover_metadata,
                },
            ),
            is_primary=True,
        )
        self._upsert_item_kind_metadata(
            item,
            {
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
                "platforms": normalized.platforms or None,
                "genres": normalized.genres or None,
                "audience_rating": normalized.audience_rating,
                "color": normalized.color,
            },
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
        await self._record_provider_snapshot(
            provider=provider_name,
            provider_item_id=provider_item_id,
            entity_type="item",
            entity_id=item.id,
            source=provider_raw,
            normalized={
                "kind": normalized.kind.value,
                "title": normalized.title,
                "item_number": normalized.item_number,
                "genres": normalized.genres,
                "platforms": normalized.platforms,
                "track_count": normalized.track_count,
                "release_status": normalized.release_status,
            },
        )
        await self._record_provider_snapshot(
            provider=provider_name,
            provider_item_id=provider_item_id,
            entity_type="edition",
            entity_id=edition.id,
            source=provider_raw,
            normalized={
                "format": edition.format,
                "physical_format": edition.physical_format,
                "release_status": edition.release_status,
                "release_date": str(edition.release_date) if edition.release_date else None,
                **cover_metadata,
            },
        )
        await self._record_provider_snapshot(
            provider=provider_name,
            provider_item_id=provider_item_id,
            entity_type="variant",
            entity_id=variant.id,
            source=provider_raw,
            normalized={
                "name": variant.name,
                "variant_type": variant.variant_type,
                "physical_format": variant.physical_format,
                "barcode": variant.barcode,
                **cover_metadata,
            },
        )
        if mirrored_cover:
            await ImageCache(self.db).record_mirrored_cover(mirrored_cover)
        for mirrored_variant_cover in additional_mirrored_covers:
            await ImageCache(self.db).record_mirrored_cover(mirrored_variant_cover)
        await self._replace_item_provider_links(
            item.id,
            provider_name,
            normalized.provider_ids,
            provider_urls=provider_link_urls_for_provider(
                provider_name,
                normalized.provider_ids,
                provider_raw,
            ),
        )
        if volume:
            await self._replace_volume_provider_links(
                volume.id,
                provider_name,
                normalized.volume_provider_ids,
            )
        await self._link_publisher(item.id, normalized.publisher)
        await self._link_imprint(item.id, normalized.imprint, normalized.publisher)
        await self._link_people(item.id, provider_name, normalized.creators)
        await self._link_characters(item.id, provider_name, normalized.characters)
        await self._link_story_arcs(item.id, provider_name, normalized.story_arcs)
        await self._link_tags(item.id, "character", normalized.characters)
        await self._link_tags(item.id, "story_arc", normalized.story_arcs)
        if volume and series is not None:
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
        volume_number: float | None,
        volume_start_year: int | None,
    ) -> tuple[Volume | None, Series | None]:
        if not series_title and not volume_name:
            return None, None
        title = series_title or volume_name or "Unknown Series"
        series = await self._get_or_create_series(kind, title)
        name = volume_name or title
        result = await self.db.execute(select(Volume).where(Volume.series_id == series.id, Volume.name == name))
        volume = result.scalar_one_or_none()
        if volume is None:
            volume = Volume(
                series=series,
                name=name,
                volume_number=volume_number,
                start_year=volume_start_year,
            )
            self.db.add(volume)
            await self.db.flush()
        elif volume.start_year is None and volume_start_year:
            volume.start_year = volume_start_year
        if volume.volume_number is None and volume_number is not None:
            volume.volume_number = volume_number
        return volume, series

    async def _get_or_create_series(self, kind: ItemKind, title: str) -> Series:
        result = await self.db.execute(select(Series).where(Series.kind == kind, Series.title == title))
        series = result.scalar_one_or_none()
        if series is None:
            series = Series(kind=kind, title=title, slug=slug(title))
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

    async def _replace_item_provider_links(
        self,
        item_id: UUID,
        provider: ExternalProvider,
        provider_ids: dict[str, str],
        provider_urls: dict[str, dict[str, str | None]] | None = None,
    ) -> None:
        await self._replace_catalog_provider_links(
            model=ItemProviderLink,
            owner_column=ItemProviderLink.item_id,
            owner_id=item_id,
            provider=provider,
            provider_ids=provider_ids,
            provider_urls=provider_urls,
        )

    async def _replace_volume_provider_links(
        self,
        volume_id: UUID,
        provider: ExternalProvider,
        provider_ids: dict[str, str],
        provider_urls: dict[str, dict[str, str | None]] | None = None,
    ) -> None:
        await self._replace_catalog_provider_links(
            model=VolumeProviderLink,
            owner_column=VolumeProviderLink.volume_id,
            owner_id=volume_id,
            provider=provider,
            provider_ids=provider_ids,
            provider_urls=provider_urls,
        )

    async def _replace_bundle_release_provider_links(
        self,
        bundle_release_id: UUID,
        provider: ExternalProvider,
        provider_ids: dict[str, str],
        provider_urls: dict[str, dict[str, str | None]] | None = None,
    ) -> None:
        await self._replace_catalog_provider_links(
            model=BundleReleaseProviderLink,
            owner_column=BundleReleaseProviderLink.bundle_release_id,
            owner_id=bundle_release_id,
            provider=provider,
            provider_ids=provider_ids,
            provider_urls=provider_urls,
        )

    async def _replace_catalog_provider_links(
        self,
        *,
        model: Any,
        owner_column: Any,
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
                    "site_url": provider_link_url_text(urls.get("site_url")) if urls else None,
                    "api_url": provider_link_url_text(urls.get("api_url")) if urls else None,
                }
            )
        await self.db.execute(
            delete(model).where(
                owner_column == owner_id,
                model.provider.in_(sorted(replacement_providers, key=lambda value: value.value)),
            )
        )
        owner_field = owner_column.key
        for row in rows:
            self.db.add(model(**{owner_field: owner_id, **row}))

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

    async def _link_imprint(self, item_id: UUID, imprint: str | None, publisher: str | None) -> None:
        if not imprint:
            return
        organization = await self._get_or_create_organization(imprint, "imprint")
        if publisher:
            normalized_parent = " ".join(str(publisher).split()).strip() or None
            if organization.parent_publisher != normalized_parent:
                organization.parent_publisher = normalized_parent
            metadata = dict(organization.metadata_json or {})
            if metadata.get("parent_publisher") != normalized_parent:
                metadata["parent_publisher"] = normalized_parent
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
                EntityPerson(entity_type="item", entity_id=item_id, person_id=person.id, role=role)
            )
            provider_item_id = comicvine_credit_provider_id(credit, resource="person")
            if provider == ExternalProvider.comicvine and provider_item_id:
                await self._add_provider_links(
                    provider,
                    {provider.value: provider_item_id},
                    "person",
                    person.id,
                    provider_urls={provider.value: credit_provider_urls(credit) or {}},
                )

    async def _create_book_work_from_normalized(
        self,
        *,
        provider: MetadataProvider,
        provider_name: ExternalProvider,
        provider_item_id: str,
        provider_raw: Any | None,
        normalized: NormalizedItem,
    ) -> BookWork:
        volume, series = await self._upsert_volume(
            ItemKind.book,
            normalized.series_title,
            normalized.volume_name,
            normalized.volume_number,
            normalized.volume_start_year,
        )

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

        if series is not None:
            sequence: float | None = None
            if normalized.item_number:
                try:
                    sequence = float(normalized.item_number)
                except ValueError:
                    sequence = None
            self.db.add(
                BookSeriesMembership(
                    work_id=work.id,
                    series_id=series.id,
                    sequence=sequence if sequence is not None else normalized.volume_number,
                    display_number=normalized.item_number,
                    metadata_json={"volume_id": str(volume.id)} if volume is not None else None,
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

    async def _reindex_book_work(self, work_id: UUID) -> None:
        work = await self.db.scalar(
            select(BookWork)
            .where(BookWork.id == work_id)
            .options(
                selectinload(BookWork.contributions).selectinload(BookContribution.person),
                selectinload(BookWork.editions)
                .selectinload(BookEdition.contributions)
                .selectinload(BookContribution.person),
                selectinload(BookWork.editions).selectinload(BookEdition.identifiers),
            )
        )
        if work is None:
            return
        await SearchClient().index_documents_best_effort([book_work_search_document(work)])

    def _book_identifier_type(self, base_type: str, value: str) -> str:
        normalized = self._normalized_identifier(value)
        if base_type == "isbn":
            if len(normalized) == 10:
                return "isbn10"
            if len(normalized) == 13:
                return "isbn13"
            return "isbn13"
        if base_type == "upc":
            if len(normalized) == 13:
                return "ean"
            return "upc"
        return base_type

    def _normalized_identifier(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())

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
                self.db.add(StoryArcItem(story_arc_id=story_arc.id, item_id=item_id, ordinal=index))
            provider_item_id = comicvine_credit_provider_id(credit, resource="story_arc")
            if provider == ExternalProvider.comicvine and provider_item_id:
                await self._add_provider_links(
                    provider,
                    {provider.value: provider_item_id},
                    "story_arc",
                    story_arc.id,
                    provider_urls={provider.value: credit_provider_urls(credit) or {}},
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
            provider_item_id = comicvine_credit_provider_id(credit, resource="character")
            character = await self._get_or_create_character(
                name,
                credit,
                provider=provider,
                provider_item_id=provider_item_id,
            )
            role = character_appearance_role(credit.role)
            existing = await self.db.scalar(
                select(CharacterAppearance).where(
                    CharacterAppearance.character_id == character.id,
                    CharacterAppearance.item_id == item_id,
                )
            )
            if existing:
                if character_role_rank(role) > character_role_rank(existing.role):
                    existing.role = role
            else:
                self.db.add(CharacterAppearance(character_id=character.id, item_id=item_id, role=role))
            if provider == ExternalProvider.comicvine and provider_item_id:
                await self._add_provider_links(
                    provider,
                    {provider.value: provider_item_id},
                    "character",
                    character.id,
                    provider_urls={provider.value: credit_provider_urls(credit) or {}},
                )
                await self._enrich_comicvine_character(character, provider_item_id, current_item_id=item_id)
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

    async def _link_relations(self, source_series: Series, relations: list[NormalizedRelation]) -> None:
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
                    provider=rel.provider,
                    provider_id=rel.provider_id,
                    start_year=rel.start_year,
                    image_url=rel.image_url,
                )
            )

    async def _ingest_seasons(
        self,
        provider: MetadataProvider,
        provider_item_id: str,
        series: Series,
        kind: ItemKind,
    ) -> None:
        if kind not in (ItemKind.tv, ItemKind.movie):
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
            volume: Volume | None = None
            if season.provider_item_id:
                volume = await self.db.scalar(
                    select(Volume)
                    .join(VolumeProviderLink, VolumeProviderLink.volume_id == Volume.id)
                    .where(
                        Volume.series_id == series.id,
                        VolumeProviderLink.provider == ExternalProvider(provider.name),
                        VolumeProviderLink.provider_item_id == season.provider_item_id,
                    )
                )
            if volume is None:
                result = await self.db.execute(
                    select(Volume).where(Volume.series_id == series.id, Volume.name == volume_name)
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
            if season.provider_item_id:
                await self._replace_volume_provider_links(
                    volume.id,
                    ExternalProvider(provider.name),
                    {provider.name: season.provider_item_id},
                )
            for episode in season.episodes:
                episode_item_id: UUID | None = None
                if episode.provider_item_id:
                    episode_item_id = await self.db.scalar(
                        select(Item.id)
                        .join(ItemProviderLink, ItemProviderLink.item_id == Item.id)
                        .where(
                            Item.volume_id == volume.id,
                            ItemProviderLink.provider == ExternalProvider(provider.name),
                            ItemProviderLink.provider_item_id == episode.provider_item_id,
                        )
                    )
                if episode_item_id is None:
                    episode_item_id = await self.db.scalar(
                        select(Item.id).where(
                            Item.volume_id == volume.id,
                            Item.season_number == season.season_number,
                            Item.episode_number == episode.episode_number,
                        )
                    )
                if episode_item_id is None:
                    episode_item = Item(
                        volume=volume,
                        kind=kind,
                        title=episode.title,
                        item_number=str(episode.episode_number),
                        sort_key=sort_key(kind, episode.title, str(episode.episode_number)),
                        synopsis=episode.overview,
                        season_number=season.season_number,
                        episode_number=episode.episode_number,
                        air_date=episode.air_date,
                        runtime_minutes=episode.runtime_minutes,
                    )
                    self.db.add(episode_item)
                    await self.db.flush()
                    episode_item_id = episode_item.id
                if episode.provider_item_id:
                    await self._replace_item_provider_links(
                        episode_item_id,
                        ExternalProvider(provider.name),
                        {provider.name: episode.provider_item_id},
                    )
        await self.db.flush()

    async def _ingest_volumes(
        self,
        provider: MetadataProvider,
        provider_item_id: str,
        series: Series,
        kind: ItemKind,
    ) -> None:
        if kind != ItemKind.comic:
            return
        try:
            volumes: list[NormalizedSeason] = await provider.get_volumes(provider_item_id)
        except Exception:
            logger.warning("Failed to fetch volumes for %s", provider_item_id, exc_info=True)
            return
        for volume_payload in volumes:
            volume_name = volume_payload.title or f"Volume {volume_payload.season_number}"
            result = await self.db.execute(
                select(Volume).where(Volume.series_id == series.id, Volume.name == volume_name)
            )
            volume = result.scalar_one_or_none()
            if volume is None:
                volume = Volume(
                    series=series,
                    name=volume_name,
                    volume_number=volume_payload.season_number,
                    start_year=volume_payload.air_date.year if volume_payload.air_date else None,
                )
                self.db.add(volume)
                await self.db.flush()
            for chapter in volume_payload.episodes:
                existing_chapter = await self.db.scalar(
                    select(Item.id).where(
                        Item.volume_id == volume.id,
                        Item.item_number == str(chapter.episode_number),
                    )
                )
                if existing_chapter:
                    continue
                self.db.add(
                    Item(
                        volume=volume,
                        kind=kind,
                        title=chapter.title,
                        item_number=str(chapter.episode_number),
                        sort_key=sort_key(kind, chapter.title, str(chapter.episode_number)),
                        synopsis=chapter.overview,
                        air_date=chapter.air_date,
                        page_count=chapter.runtime_minutes,
                    )
                )
        await self.db.flush()

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
                api_detail_url=credit.api_detail_url,
                site_detail_url=credit.site_detail_url,
                image_url=credit.image_url,
            )
            self.db.add(person)
            await self.db.flush()
            return person
        updated = False
        if not person.api_detail_url and credit.api_detail_url:
            person.api_detail_url = credit.api_detail_url
            updated = True
        if not person.site_detail_url and credit.site_detail_url:
            person.site_detail_url = credit.site_detail_url
            updated = True
        if not person.image_url and credit.image_url:
            person.image_url = credit.image_url
            updated = True
        credit_description = getattr(credit, "description", None)
        if not person.description and credit_description:
            person.description = credit_description
            updated = True
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
        updated = False
        if not story_arc.api_detail_url and credit.api_detail_url:
            story_arc.api_detail_url = credit.api_detail_url
            updated = True
        if not story_arc.site_detail_url and credit.site_detail_url:
            story_arc.site_detail_url = credit.site_detail_url
            updated = True
        credit_description = getattr(credit, "description", None)
        if not story_arc.description and credit_description:
            story_arc.description = credit_description
            updated = True
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
        updated = False
        if not character.api_detail_url and credit.api_detail_url:
            character.api_detail_url = credit.api_detail_url
            updated = True
        if not character.site_detail_url and credit.site_detail_url:
            character.site_detail_url = credit.site_detail_url
            updated = True
        credit_description = getattr(credit, "description", None)
        if not character.description and credit_description:
            character.description = credit_description
            updated = True
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
        if character.description and character.image_url and character.aliases and character.first_appearance_item_id:
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

    async def _local_item_id_for_provider_id(
        self,
        provider: ExternalProvider,
        provider_item_id: str,
    ) -> UUID | None:
        return await self.db.scalar(
            select(ItemProviderLink.item_id).where(
                ItemProviderLink.provider == provider,
                ItemProviderLink.provider_item_id == provider_item_id,
            )
        )

    async def _provider_id_for_item(self, provider: ExternalProvider, item_id: UUID) -> str | None:
        return await self.db.scalar(
            select(ItemProviderLink.provider_item_id).where(
                ItemProviderLink.provider == provider,
                ItemProviderLink.item_id == item_id,
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