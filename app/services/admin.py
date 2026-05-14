from collections import deque
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
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
    AdminSearchHistoryEntry,
    AdminSearchReindexResponse,
    AdminSearchStatusResponse,
    ProviderIngestRequest,
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
            candidates.append(
                AdminDuplicateCandidateResponse(
                    kind=kind.value if hasattr(kind, "value") else str(kind),
                    title=title,
                    item_number=item_number,
                    count=count,
                    item_ids=ids,
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

    async def ingest(self, payload: ProviderIngestRequest) -> ProviderIngestResponse:
        provider = self._provider(payload.provider)
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
            is_primary=True,
        )
        release = Release(
            edition=edition,
            region="US",
            release_date=normalized.release_date,
            publisher=normalized.publisher,
            external_ids=normalized.provider_ids,
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

    def _provider(self, provider: ExternalProvider) -> MetadataProvider:
        try:
            return self.providers.get(provider.value)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Provider '{provider.value}' is not configured",
            ) from exc

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
        if kind == ItemKind.comic and item_number:
            return f"{self._slug(title)}-{item_number.zfill(6)}"
        return f"{self._slug(title)}-{item_number or ''}".strip("-")

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
