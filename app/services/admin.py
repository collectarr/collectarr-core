from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import (
    Edition,
    EntityOrganization,
    EntityPerson,
    EntityTag,
    ExternalProviderId,
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
from app.storage.images import ImageMirror


class AdminMetadataService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.providers = ProviderRegistry()
        self.settings = get_settings()

    async def provider_statuses(self) -> list[ProviderStatusResponse]:
        return [
            ProviderStatusResponse(
                name="comicvine",
                kind=ItemKind.comic.value,
                status="live" if self.settings.comicvine_api_key else "stub",
                is_configured=bool(self.settings.comicvine_api_key),
                message=(
                    "ComicVine API key configured."
                    if self.settings.comicvine_api_key
                    else "Set COMICVINE_API_KEY to enable live ComicVine metadata."
                ),
            ),
            ProviderStatusResponse(
                name="igdb",
                kind=ItemKind.game.value,
                status="stub",
                is_configured=False,
                message="IGDB live metadata is planned after the comics MVP.",
            ),
            ProviderStatusResponse(
                name="tmdb",
                kind=ItemKind.bluray.value,
                status="stub",
                is_configured=False,
                message="TMDb live metadata is planned after the comics MVP.",
            ),
        ]

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
            release_date=normalized.release_date,
            metadata_json={
                "provider": payload.provider.value,
                "provider_item_id": provider_item.provider_item_id,
                "source": provider_item.raw,
            },
        )
        mirrored_cover = await ImageMirror().mirror_cover_best_effort(
            normalized.cover_image_url,
            payload.provider.value,
            provider_item.provider_item_id,
        )
        variant = Variant(
            edition=edition,
            name="Cover A",
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
        self._add_provider_links(payload.provider, normalized.provider_ids, "item", item.id)
        if volume:
            self._add_provider_links(
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

    def _add_provider_links(
        self,
        provider: ExternalProvider,
        provider_ids: dict[str, str],
        entity_type: str,
        entity_id: UUID,
    ) -> None:
        provider_id = provider_ids.get(provider.value)
        if not provider_id:
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
