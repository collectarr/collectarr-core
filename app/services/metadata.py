import asyncio
import logging
import re
from dataclasses import replace
from urllib.parse import urlparse
from uuid import UUID

from fastapi import status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalog.physical_formats import is_video_item_kind, physical_format_for_id
from app.core.config import get_settings
from app.core.errors import ApiHTTPException
from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import (
    Character,
    CharacterAppearance,
    Edition,
    EntityTag,
    EntityPerson,
    ExternalProviderId,
    Item,
    MetadataProposal,
    Person,
    Series,
    SeriesRelation,
    StoryArc,
    StoryArcItem,
    Tag,
    Volume,
)
from app.providers.base import MetadataProvider, ProviderSearchResult
from app.providers.comicvine import ComicVineProvider
from app.providers.gcd import GCDProvider
from app.providers.registry import ProviderRegistry
from app.repositories.metadata import MetadataRepository
from app.schemas.metadata import (
    CharacterAppearanceResponse,
    CharacterFacetResponse,
    CharacterResponse,
    BundleReleaseDetailResponse,
    BundleReleaseSummaryResponse,
    CreatorCreditResponse,
    CreatorFacetResponse,
    CreatorResponse,
    EditionResponse,
    ItemResponse,
    MetadataCredit,
    MetadataProposalCreate,
    MetadataProposalResponse,
    ProviderLink,
    ProviderSearchResultResponse,
    SeasonResponse,
    SearchResult,
    SeriesItemResponse,
    SeriesResponse,
    StoryArcFacetResponse,
    StoryArcItemResponse,
    StoryArcResponse,
    SeriesRelationResponse,
    bundle_release_detail_from_model,
    bundle_release_summary_from_model,
    item_response_from_model,
)
from app.search.client import SearchClient
from app.services.provider_search_state import ProviderSearchState
from app.storage.image_cache import ImageCache
from app.storage.images import ImageMirror

logger = logging.getLogger(__name__)

_UPSTREAM_HTTP_STATUS_RE = re.compile(r"\bHTTP\s+(?P<status>\d{3})\b")
_PROVIDER_INTERNAL_RETRY_NAMES = {ExternalProvider.bgg.value, ExternalProvider.comicvine.value}


def _metadata_text(metadata: dict[str, object] | None, key: str) -> str | None:
    if not isinstance(metadata, dict):
        return None
    value = metadata.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class MetadataService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()
        self.metadata = MetadataRepository(db)
        self.search_client = SearchClient()
        self.providers = ProviderRegistry()
        self.provider_search_state = ProviderSearchState(self.settings)

    async def _provider_links_for_item(self, item_id: UUID) -> list[ProviderLink]:
        result = await self.db.execute(
            select(ExternalProviderId)
            .where(
                ExternalProviderId.entity_type == "item",
                ExternalProviderId.entity_id == item_id,
            )
            .order_by(ExternalProviderId.provider, ExternalProviderId.provider_item_id)
        )
        return [
            ProviderLink(
                provider=row.provider,
                entity_type=row.entity_type,
                provider_item_id=row.provider_item_id,
                site_url=row.site_url,
                api_url=row.api_url,
            )
            for row in result.scalars()
        ]

    async def get_item(self, item_id: UUID, kind: ItemKind) -> ItemResponse:
        item = await self.metadata.get_item(item_id, kind)
        if item is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="metadata_item_not_found",
                detail="Item not found",
            )
        response = item_response_from_model(
            item,
            extra_provider_links=await self._provider_links_for_item(item.id),
        )
        series_id = getattr(getattr(getattr(item, "volume", None), "series", None), "id", None)
        await self._enrich_item_metadata_facets(response, item.id, series_id=series_id)
        return response

    async def get_bundle_releases_for_item(self, item_id: UUID) -> list[BundleReleaseSummaryResponse]:
        item = await self.metadata.get_item(item_id)
        if item is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="metadata_item_not_found",
                detail="Item not found",
            )
        bundle_releases = await self.metadata.get_bundle_releases_for_item(item_id)
        return [bundle_release_summary_from_model(bundle) for bundle in bundle_releases]

    async def get_bundle_release(self, bundle_release_id: UUID) -> BundleReleaseDetailResponse:
        bundle_release = await self.metadata.get_bundle_release(bundle_release_id)
        if bundle_release is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="bundle_release_not_found",
                detail="Bundle release not found",
            )
        return bundle_release_detail_from_model(bundle_release)

    async def _enrich_item_metadata_facets(
        self,
        response: ItemResponse,
        item_id: UUID,
        series_id: UUID | None = None,
    ) -> None:
        creator_rows = (
            await self.db.execute(
                select(EntityPerson, Person)
                .join(Person, Person.id == EntityPerson.person_id)
                .where(
                    EntityPerson.entity_type == "item",
                    EntityPerson.entity_id == item_id,
                )
                .order_by(EntityPerson.role.asc(), Person.name.asc())
            )
        ).all()
        if creator_rows:
            response.creators = [
                MetadataCredit(
                    name=person.name,
                    role=link.role,
                    api_detail_url=_metadata_text(person.metadata_json, "api_detail_url"),
                    site_detail_url=_metadata_text(person.metadata_json, "site_detail_url"),
                    image_url=_metadata_text(person.metadata_json, "image_url"),
                )
                for link, person in creator_rows
            ]

        character_rows = (
            await self.db.execute(
                select(CharacterAppearance, Character)
                .join(Character, Character.id == CharacterAppearance.character_id)
                .where(CharacterAppearance.item_id == item_id)
                .order_by(CharacterAppearance.role.asc(), Character.name.asc())
            )
        ).all()
        if character_rows:
            response.characters = [
                MetadataCredit(
                    name=character.name,
                    role=appearance.role,
                    aliases=[
                        str(alias) for alias in (character.aliases or []) if str(alias).strip()
                    ],
                    description=character.description,
                    image_url=character.image_url,
                    first_appearance_item_id=character.first_appearance_item_id,
                )
                for appearance, character in character_rows
            ]

        arc_rows = (
            await self.db.execute(
                select(StoryArcItem, StoryArc)
                .join(StoryArc, StoryArc.id == StoryArcItem.story_arc_id)
                .where(StoryArcItem.item_id == item_id)
                .order_by(StoryArcItem.ordinal.asc().nullslast(), StoryArc.name.asc())
            )
        ).all()
        if arc_rows:
            response.story_arcs = [
                MetadataCredit(
                    name=arc.name,
                    description=arc.description,
                    ordinal=link.ordinal,
                    publisher=arc.publisher,
                )
                for link, arc in arc_rows
            ]
        if series_id is not None:
            response.tags = await self._entity_tags("series", series_id)

    async def _entity_tags(self, entity_type: str, entity_id: UUID) -> list[str]:
        rows = await self.db.scalars(
            select(Tag.name)
            .join(EntityTag, EntityTag.tag_id == Tag.id)
            .where(
                EntityTag.entity_type == entity_type,
                EntityTag.entity_id == entity_id,
            )
            .order_by(Tag.name.asc())
        )
        return [name for name in rows if isinstance(name, str) and name.strip()]

    async def search(
        self,
        query: str | None = None,
        kind: ItemKind | None = None,
        series: str | None = None,
        issue_number: str | None = None,
        publisher: str | None = None,
        year: int | None = None,
        barcode: str | None = None,
        limit: int = 25,
    ) -> list[SearchResult]:
        if not any(
            value is not None and str(value).strip()
            for value in (query, series, issue_number, publisher, year, barcode)
        ):
            return []

        meili_results = await self.search_client.search(
            query=query or "",
            kind=kind,
            series=series,
            issue_number=issue_number,
            publisher=publisher,
            year=year,
            barcode=barcode,
            limit=limit,
        )
        if meili_results is not None and not barcode:
            return [SearchResult(**result) for result in meili_results]

        items = await self.metadata.search_items(
            query=query,
            kind=kind,
            limit=limit,
            series=series,
            issue_number=issue_number,
            publisher=publisher,
            year=year,
            barcode=barcode,
        )
        results: list[SearchResult] = []
        for item in items:
            preferred_variant = self._preferred_variant(
                item,
                query=query,
                barcode=barcode,
            )
            cover_url, thumbnail_url = self._variant_cover(
                preferred_variant or self._primary_variant(item)
            )
            results.append(
                self._search_result(
                    item,
                    cover_url,
                    thumbnail_url,
                    preferred_variant=preferred_variant,
                )
            )
        return results

    async def lookup_barcode(self, barcode: str, kind: ItemKind | None = None) -> SearchResult:
        item = await self.metadata.find_item_by_barcode(barcode, kind)
        if item is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="barcode_not_found",
                detail="Barcode not found",
            )

        preferred_variant = self._preferred_variant(item, barcode=barcode)
        cover_url, thumbnail_url = self._variant_cover(
            preferred_variant or self._primary_variant(item)
        )
        return self._search_result(
            item,
            cover_url,
            thumbnail_url,
            preferred_variant=preferred_variant,
        )

    async def barcode_provider_search(
        self,
        barcode: str,
        kind: ItemKind | None = None,
    ) -> list[ProviderSearchResult]:
        """Search external providers for a barcode/UPC/ISBN."""
        cache_key = self._provider_search_cache_key("barcode", barcode, kind)
        cached_results = await self._cached_provider_search_results(cache_key)
        if cached_results is not None:
            return await self._with_stable_provider_image_urls(cached_results)

        if kind is not None:
            providers = self.providers.for_kind(kind)
        else:
            providers = self.providers.all()

        for provider in providers:
            if not provider.is_configured:
                continue
            if not hasattr(provider, "search_by_barcode"):
                continue
            try:
                results = await provider.search_by_barcode(barcode, kind)
            except Exception:
                logger.warning(
                    "barcode_provider_search_failed provider=%s barcode=%s",
                    provider.name,
                    barcode,
                    exc_info=True,
                )
                continue
            if results:
                results = results[:3]
                await self._store_provider_search_results(cache_key, results)
                return await self._with_stable_provider_image_urls(results)

        await self._store_provider_search_results(cache_key, [])
        return []

    async def search_provider(
        self,
        provider_name: ExternalProvider,
        query: str | None,
        kind: ItemKind | None = None,
        *,
        series: str | None = None,
        issue_number: str | None = None,
        year: int | None = None,
    ) -> list[ProviderSearchResultResponse]:
        provider = self.providers.maybe_get(provider_name)
        if provider is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_not_configured",
                detail=f"Provider '{provider_name.value}' is not configured",
            )
        if not provider.capabilities.supports_search:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_search_unsupported",
                detail=f"Provider '{provider_name.value}' does not support search",
            )
        if kind is not None and not provider.capabilities.supports_kind(kind):
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_kind_unsupported",
                detail=(f"Provider '{provider_name.value}' does not support kind '{kind.value}'"),
            )
        provider_query = self._provider_search_query(
            query,
            kind,
            series=series,
            issue_number=issue_number,
            year=year,
        )
        if not provider_query:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_query_required",
                detail="Provider search requires a query, series title, barcode, or issue context.",
            )
        cache_key = self._provider_search_cache_key(provider_name, provider_query, kind)
        results = await self._cached_provider_search_results(cache_key)
        should_refresh_cache = False
        if results is None:
            try:
                results = await self._search_provider_live(
                    provider_name,
                    provider,
                    provider_query,
                    kind,
                )
            except ApiHTTPException as exc:
                fallback_results = await self._search_provider_fallback(
                    provider_name,
                    provider_query,
                    kind,
                    exc,
                )
                if fallback_results is None:
                    raise
                results = fallback_results
            should_refresh_cache = True
        enriched_results = await self._with_provider_search_enrichment(
            provider_name,
            provider_query,
            kind,
            results,
        )
        if enriched_results is not results:
            results = enriched_results
            should_refresh_cache = True
        preview_results = await self._with_provider_search_credit_previews(
            provider_name,
            results,
        )
        if preview_results is not results:
            results = preview_results
            should_refresh_cache = True
        if should_refresh_cache:
            await self._store_provider_search_results(cache_key, results)
        results = await self._with_stable_provider_image_urls(results)
        return [ProviderSearchResultResponse(**result.__dict__) for result in results]

    async def search_default_provider(
        self,
        query: str | None,
        kind: ItemKind,
        *,
        series: str | None = None,
        issue_number: str | None = None,
        year: int | None = None,
    ) -> list[ProviderSearchResultResponse]:
        provider = self.providers.default_for_kind(kind)
        if provider is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_not_configured",
                detail=f"No metadata provider is configured for kind '{kind.value}'",
            )
        return await self.search_provider(
            ExternalProvider(provider.name),
            query,
            kind,
            series=series,
            issue_number=issue_number,
            year=year,
        )

    async def _search_provider_live(
        self,
        provider_name: ExternalProvider,
        provider: MetadataProvider,
        query: str,
        kind: ItemKind | None,
    ) -> list[ProviderSearchResult]:
        await self._raise_if_provider_on_backoff(provider_name)
        attempts = self._provider_search_attempts(provider_name)
        last_error: ApiHTTPException | None = None
        for attempt in range(attempts):
            try:
                return await provider.search(query, kind)
            except ApiHTTPException as exc:
                last_error = exc
                if self._should_backoff_provider_search(exc):
                    await self._record_provider_search_backoff(provider_name, exc)
                if attempt >= attempts - 1 or not self._should_retry_provider_search(exc):
                    raise
                await asyncio.sleep(self._provider_search_retry_delay(exc, attempt))
        raise last_error or ApiHTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="provider_search_failed",
            detail=f"Provider '{provider_name.value}' search failed",
        )

    def _provider_search_attempts(self, provider_name: ExternalProvider) -> int:
        if provider_name.value in _PROVIDER_INTERNAL_RETRY_NAMES:
            return 1
        return max(1, self.settings.provider_search_retry_attempts + 1)

    def _provider_search_cache_key(
        self,
        provider_name: ExternalProvider | str,
        query: str,
        kind: ItemKind | None,
    ) -> tuple[str, str, str]:
        normalized_query = " ".join(query.split()).casefold()
        return self._provider_search_cache_namespace(provider_name), kind.value if kind else "*", normalized_query

    def _provider_search_cache_namespace(
        self,
        provider_name: ExternalProvider | str,
    ) -> str:
        return provider_name.value if isinstance(provider_name, ExternalProvider) else str(provider_name)

    def _provider_search_query(
        self,
        query: str | None,
        kind: ItemKind | None,
        *,
        series: str | None,
        issue_number: str | None,
        year: int | None,
    ) -> str:
        base_query = self._clean_provider_query_part(query)
        if kind == ItemKind.comic:
            series_query = self._clean_provider_query_part(series)
            issue_query = self._clean_issue_number(issue_number)
            if series_query or issue_query:
                parts = [series_query or base_query]
                if issue_query:
                    parts.append(f"#{issue_query}")
                provider_query = " ".join(part for part in parts if part)
            else:
                provider_query = base_query
            if year is not None and provider_query and str(year) not in provider_query:
                provider_query = f"{provider_query} ({year})"
            return self._clean_provider_query_part(provider_query)
        if kind == ItemKind.music:
            series_query = self._clean_provider_query_part(series)
            release_query = self._clean_provider_query_part(issue_number)
            if not release_query:
                release_query = base_query
            if not series_query and year is None:
                return base_query
            parts: list[str] = []
            if series_query:
                parts.append(f'artist:"{self._escape_provider_query_phrase(series_query)}"')
            if release_query:
                parts.append(f'release:"{self._escape_provider_query_phrase(release_query)}"')
            if year is not None:
                parts.append(f'date:{year}')
            return " AND ".join(parts)
        return base_query

    def _clean_provider_query_part(self, value: str | None) -> str:
        return " ".join(str(value or "").split())

    def _escape_provider_query_phrase(self, value: str) -> str:
        return value.replace('"', r'\"')

    def _clean_issue_number(self, value: str | None) -> str:
        text = self._clean_provider_query_part(value)
        return re.sub(r"^#+\s*", "", text)

    async def _cached_provider_search_results(
        self,
        key: tuple[str, str, str],
    ) -> list[ProviderSearchResult] | None:
        return await self.provider_search_state.cached(key)

    async def _store_provider_search_results(
        self,
        key: tuple[str, str, str],
        results: list[ProviderSearchResult],
    ) -> None:
        await self.provider_search_state.store(key, results)

    async def _raise_if_provider_on_backoff(self, provider_name: ExternalProvider) -> None:
        await self.provider_search_state.raise_if_backoff(provider_name)

    async def _record_provider_search_backoff(
        self,
        provider_name: ExternalProvider,
        exc: ApiHTTPException,
    ) -> None:
        seconds = (
            self._provider_search_retry_after(exc) or self.settings.provider_search_backoff_seconds
        )
        if seconds <= 0:
            return
        provider = self.providers.maybe_get(provider_name)
        provider_label = provider.capabilities.display_name if provider else provider_name.value
        await self.provider_search_state.record_backoff(
            provider_name,
            seconds=seconds,
            provider_label=provider_label,
            reason=self._provider_search_error_reason(exc),
        )

    def _should_retry_provider_search(self, exc: ApiHTTPException) -> bool:
        return self._provider_search_status(exc) in {401, 429, 500, 502, 503, 504}

    def _should_backoff_provider_search(self, exc: ApiHTTPException) -> bool:
        return self._provider_search_status(exc) in {401, 429, 500, 502, 503, 504}

    def _provider_search_retry_delay(self, exc: ApiHTTPException, attempt: int) -> float:
        retry_after = self._provider_search_retry_after(exc)
        if retry_after is not None:
            return min(float(retry_after), 3.0)
        base = self.settings.provider_search_retry_base_delay_seconds
        return min(base * (2**attempt), 3.0)

    def _provider_search_retry_after(self, exc: ApiHTTPException) -> int | None:
        retry_after = (exc.headers or {}).get("Retry-After")
        if retry_after is None:
            return None
        try:
            value = int(float(retry_after))
        except ValueError:
            return None
        return value if value > 0 else None

    def _provider_search_status(self, exc: ApiHTTPException) -> int:
        detail = exc.detail
        if isinstance(detail, str):
            match = _UPSTREAM_HTTP_STATUS_RE.search(detail)
            if match:
                return int(match.group("status"))
        return exc.status_code

    def _provider_search_error_reason(self, exc: ApiHTTPException) -> str:
        upstream_status = self._provider_search_status(exc)
        if upstream_status != exc.status_code:
            return f"HTTP {upstream_status}"
        return f"HTTP {exc.status_code}"

    async def mirror_provider_image_url(
        self,
        source_url: str | None,
        *,
        provider_name: str | ExternalProvider,
        provider_item_id: str | None,
        cache_only: bool = False,
    ) -> str | None:
        if not self._can_mirror_provider_image(provider_name, source_url):
            return None
        provider_value = self._provider_value(provider_name)
        provider_item_id = provider_item_id or "unknown"
        cache = ImageCache(self.db)
        try:
            cached = await cache.cached_provider_cover(
                provider=provider_value,
                source_url=source_url or "",
            )
            if cached is not None:
                await self.db.commit()
                return cached.public_url

            if cache_only:
                return None

            mirrored = await ImageMirror().mirror_cover_best_effort(
                source_url,
                provider_value,
                provider_item_id,
            )
            if mirrored is None:
                return None
            await cache.record_mirrored_cover(mirrored)
            await self.db.commit()
            return mirrored.url
        except Exception:
            await self.db.rollback()
            logger.warning(
                "provider_image_mirror_failed provider=%s provider_item_id=%s source=%s",
                provider_value,
                provider_item_id,
                source_url,
                exc_info=True,
            )
            return None

    async def mirror_provider_image_bytes(
        self,
        image_bytes: bytes | None,
        *,
        source_url: str | None,
        provider_name: str | ExternalProvider,
        provider_item_id: str | None,
    ) -> str | None:
        if not image_bytes or not self._can_mirror_provider_image(provider_name, source_url):
            return None
        provider_value = self._provider_value(provider_name)
        provider_item_id = provider_item_id or "unknown"
        cache = ImageCache(self.db)
        try:
            cached = await cache.cached_provider_cover(
                provider=provider_value,
                source_url=source_url or "",
            )
            if cached is not None:
                await self.db.commit()
                return cached.public_url

            mirrored = await ImageMirror().mirror_cover_bytes_best_effort(
                image_bytes,
                source_url=source_url,
                provider=provider_value,
                provider_item_id=provider_item_id,
            )
            if mirrored is None:
                return None
            await cache.record_mirrored_cover(mirrored)
            await self.db.commit()
            return mirrored.url
        except Exception:
            await self.db.rollback()
            logger.warning(
                "provider_image_mirror_failed provider=%s provider_item_id=%s source=%s",
                provider_value,
                provider_item_id,
                source_url,
                exc_info=True,
            )
            return None

    async def _with_stable_provider_image_urls(
        self,
        results: list[ProviderSearchResult],
    ) -> list[ProviderSearchResult]:
        stable_results: list[ProviderSearchResult] = []
        for result in results:
            mirrored_url = await self.mirror_provider_image_url(
                result.image_url,
                provider_name=result.provider,
                provider_item_id=result.provider_item_id,
                cache_only=True,
            )
            stable_results.append(
                replace(result, image_url=mirrored_url) if mirrored_url else result
            )
        return stable_results

    def _can_mirror_provider_image(
        self,
        provider_name: str | ExternalProvider,
        source_url: str | None,
    ) -> bool:
        if not self.settings.mirror_provider_images:
            return False
        if not self._is_external_image_url(source_url):
            return False
        provider = self._provider_for_name(provider_name)
        if provider is None:
            return False
        if self.settings.mirror_provider_images_allow_restricted:
            return True
        return provider.capabilities.allows_image_mirroring

    def _provider_for_name(
        self,
        provider_name: str | ExternalProvider,
    ) -> MetadataProvider | None:
        try:
            provider_enum = (
                provider_name
                if isinstance(provider_name, ExternalProvider)
                else ExternalProvider(str(provider_name))
            )
        except ValueError:
            return None
        return self.providers.maybe_get(provider_enum)

    def _provider_value(self, provider_name: str | ExternalProvider) -> str:
        return (
            provider_name.value
            if isinstance(provider_name, ExternalProvider)
            else str(provider_name)
        )

    def _is_external_image_url(self, value: str | None) -> bool:
        if not value:
            return False
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    async def _search_provider_fallback(
        self,
        provider_name: ExternalProvider,
        query: str,
        kind: ItemKind | None,
        original_error: ApiHTTPException,
    ):
        if not self.settings.provider_search_comicvine_fallback_enabled:
            return None
        if provider_name != ExternalProvider.gcd:
            return None
        if not self._should_backoff_provider_search(original_error):
            return None
        fallback = self.providers.maybe_get(ExternalProvider.comicvine)
        if fallback is None or not fallback.is_configured:
            return None
        if kind is not None and not fallback.capabilities.supports_kind(kind):
            return None
        if isinstance(fallback, ComicVineProvider):
            exact_results = await self._search_gcd_comicvine_exact_fallback(
                fallback,
                query,
                kind,
                requested_provider=provider_name,
            )
            if exact_results:
                return exact_results
        try:
            results = await fallback.search(query, kind)
        except Exception:
            logger.warning(
                "provider_search_fallback_failed provider=%s fallback=%s code=%s",
                provider_name.value,
                fallback.name,
                original_error.code,
                exc_info=True,
            )
            return None
        if not results:
            return None
        results = [
            self._with_provider_fallback_notice(
                result,
                requested_provider=provider_name,
                fallback_provider=ExternalProvider.comicvine,
            )
            for result in results
        ]
        logger.info(
            "provider_search_fallback_used provider=%s fallback=%s code=%s",
            provider_name.value,
            fallback.name,
            original_error.code,
        )
        return results

    async def _with_provider_search_enrichment(
        self,
        provider_name: ExternalProvider,
        query: str,
        kind: ItemKind | None,
        results: list[ProviderSearchResult],
    ) -> list[ProviderSearchResult]:
        if not self.settings.provider_search_comicvine_fallback_enabled:
            return results
        if provider_name != ExternalProvider.gcd or not results:
            return results
        target_kind = kind or ItemKind.comic
        if target_kind not in {ItemKind.comic, ItemKind.manga}:
            return results
        if any(result.provider == ExternalProvider.comicvine.value for result in results):
            return results

        fallback = self.providers.maybe_get(ExternalProvider.comicvine)
        if (
            fallback is None
            or not fallback.is_configured
            or not fallback.capabilities.supports_kind(target_kind)
        ):
            return results

        plan = GCDProvider()._query_plan(query)
        if not plan.is_series_search:
            return results

        cache_key = self._provider_search_cache_key(
            ExternalProvider.comicvine,
            query,
            target_kind,
        )
        fallback_results = await self._cached_provider_search_results(cache_key)
        if fallback_results is None:
            try:
                fallback_results = await self._search_provider_live(
                    ExternalProvider.comicvine,
                    fallback,
                    query,
                    target_kind,
                )
            except Exception:
                logger.warning(
                    "provider_search_enrichment_failed provider=%s fallback=%s",
                    provider_name.value,
                    fallback.name,
                    exc_info=True,
                )
                return results
            await self._store_provider_search_results(cache_key, fallback_results)
        if not fallback_results:
            return results

        seen = {(result.provider, result.provider_item_id) for result in results}
        enriched = list(results)
        for result in fallback_results:
            key = (result.provider, result.provider_item_id)
            if key in seen:
                continue
            seen.add(key)
            enriched.append(result)
        return enriched

    async def _search_gcd_comicvine_exact_fallback(
        self,
        provider: ComicVineProvider,
        query: str,
        kind: ItemKind | None,
        *,
        requested_provider: ExternalProvider,
    ) -> list[ProviderSearchResult]:
        target_kind = kind or ItemKind.comic
        if target_kind not in {ItemKind.comic, ItemKind.manga}:
            return []
        plan = GCDProvider()._query_plan(query)
        if plan.is_series_search:
            return []
        for series_title, issue_number in plan.candidates[:3]:
            try:
                cover = await provider.find_issue_cover(
                    series_title=series_title,
                    issue_number=issue_number,
                )
            except Exception:
                logger.warning(
                    "provider_search_exact_cover_fallback_failed series=%s issue=%s",
                    series_title,
                    issue_number,
                    exc_info=True,
                )
                continue
            if cover is None:
                continue
            return [
                self._with_provider_fallback_notice(
                    ProviderSearchResult(
                        provider=provider.name,
                        provider_item_id=cover.provider_item_id,
                        title=f"{series_title.title()} #{issue_number}",
                        kind=target_kind,
                        image_url=cover.image_url,
                        candidate_type="issue",
                        series_title=series_title.title(),
                        issue_number=issue_number,
                        is_variant=False,
                    ),
                    requested_provider=requested_provider,
                    fallback_provider=ExternalProvider.comicvine,
                )
            ]
        return []

    async def _with_provider_search_credit_previews(
        self,
        _provider_name: ExternalProvider,
        results: list[ProviderSearchResult],
    ) -> list[ProviderSearchResult]:
        if not results:
            return results

        series_preview: dict[str, tuple[list[str], list[str]]] = {}
        for result in results:
            if result.candidate_type not in {"issue", "variant"}:
                continue
            if not result.character_preview and not result.story_arc_preview:
                continue
            series_key = self._preview_series_key(result.series_title or result.title)
            if not series_key:
                continue
            merged = self._merge_preview_lists(
                series_preview.get(series_key),
                result.character_preview,
                result.story_arc_preview,
            )
            if merged is not None:
                series_preview[series_key] = merged

        if not series_preview:
            return results

        changed = False
        final_results: list[ProviderSearchResult] = []
        for result in results:
            if (
                result.candidate_type == "series"
                and not result.character_preview
                and not result.story_arc_preview
            ):
                series_key = self._preview_series_key(result.series_title or result.title)
                series_data = series_preview.get(series_key or "")
                if series_data is not None:
                    chars, arcs = series_data
                    result = replace(
                        result,
                        character_preview=chars,
                        story_arc_preview=arcs,
                    )
                    changed = True
            final_results.append(result)

        return final_results if changed else results

    def _preview_series_key(self, value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"\s+", " ", value).strip().casefold()

    def _merge_preview_lists(
        self,
        existing: tuple[list[str], list[str]] | None,
        characters: list[str],
        arcs: list[str],
    ) -> tuple[list[str], list[str]] | None:
        if not characters and not arcs and existing is None:
            return None
        existing_characters = list(existing[0]) if existing else []
        existing_arcs = list(existing[1]) if existing else []
        merged_characters = self._merge_names(existing_characters, characters)
        merged_arcs = self._merge_names(existing_arcs, arcs)
        return merged_characters, merged_arcs

    def _merge_names(self, base: list[str], extra: list[str]) -> list[str]:
        merged = list(base)
        seen = {name.casefold() for name in merged}
        for name in extra:
            text = str(name or "").strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            merged.append(text)
            if len(merged) >= 3:
                break
        return merged[:3]

    def _with_provider_fallback_notice(
        self,
        result: ProviderSearchResult,
        *,
        requested_provider: ExternalProvider,
        fallback_provider: ExternalProvider,
    ) -> ProviderSearchResult:
        notice = (
            f"{self._provider_display_name(fallback_provider)} fallback while "
            f"{self._provider_display_name(requested_provider)} is unavailable."
        )
        summary = notice if not result.summary else f"{notice} {result.summary}"
        return replace(result, summary=summary)

    def _provider_display_name(self, provider_name: ExternalProvider) -> str:
        provider = self.providers.maybe_get(provider_name)
        return provider.capabilities.display_name if provider else provider_name.value

    async def create_proposal(self, payload: MetadataProposalCreate) -> MetadataProposalResponse:
        proposal = MetadataProposal(
            provider=payload.provider,
            provider_item_id=payload.provider_item_id,
            query=payload.query,
            title=payload.title,
            summary=payload.summary,
            image_url=payload.image_url,
            metadata_payload=payload.metadata_payload,
        )
        self.db.add(proposal)
        await self.db.commit()
        await self.db.refresh(proposal)
        return MetadataProposalResponse.model_validate(proposal)

    def _search_result(
        self,
        item,
        cover_url: str | None,
        thumbnail_url: str | None,
        *,
        preferred_variant=None,
    ) -> SearchResult:
        publisher = None
        release_date = None
        release_year = None
        barcode = None
        edition_title = None
        physical_format_id = None
        physical_format_label = None
        variant_name = getattr(preferred_variant, "name", None)
        if preferred_variant is not None:
            barcode = preferred_variant.barcode or preferred_variant.isbn or preferred_variant.sku
            preferred_format = self._physical_format(
                preferred_variant.metadata_json,
                fallback_format=preferred_variant.variant_type,
                kind=item.kind,
            )
            if preferred_format is not None:
                physical_format_id = preferred_format.id
                physical_format_label = preferred_format.label
        for edition in item.editions:
            edition_title = edition_title or edition.title
            publisher = publisher or edition.publisher
            barcode = barcode or edition.upc or edition.isbn
            physical_format = self._physical_format(
                edition.metadata_json,
                fallback_format=edition.format,
                kind=item.kind,
            )
            if physical_format is not None:
                physical_format_id = physical_format_id or physical_format.id
                physical_format_label = physical_format_label or physical_format.label
                variant_name = variant_name or physical_format.label
            if edition.release_date is not None and release_date is None:
                release_date = edition.release_date
                release_year = edition.release_date.year
            primary = next((variant for variant in edition.variants if variant.is_primary), None)
            if primary is not None and variant_name is None:
                variant_name = primary.name
                barcode = barcode or primary.barcode or primary.isbn or primary.sku
                primary_format = self._physical_format(
                    primary.metadata_json,
                    fallback_format=primary.variant_type,
                    kind=item.kind,
                )
                if primary_format is not None:
                    physical_format_id = physical_format_id or primary_format.id
                    physical_format_label = physical_format_label or primary_format.label
            if (
                publisher is not None
                and release_date is not None
                and barcode is not None
                and variant_name is not None
                and (not is_video_item_kind(item.kind) or physical_format_label is not None)
            ):
                break
        series_title = getattr(item, "series_title", None) or (
            item.series.title if hasattr(item, "series") and item.series else None
        )
        volume_name = getattr(item, "volume_name", None) or (
            item.volume.name if hasattr(item, "volume") and item.volume else None
        )
        track_count: int | None = None
        tracks: list[dict] | None = None
        catalog_number: str | None = None
        creators: list[dict] | None = None
        characters: list[str] | None = None
        story_arcs: list[str] | None = None
        platforms: list[str] | None = None
        genres: list[str] | None = None
        page_count: int | None = getattr(item, "page_count", None)
        runtime_minutes: int | None = getattr(item, "runtime_minutes", None)
        cover_price_cents: int | None = None
        item_currency: str | None = None
        country: str | None = None
        release_status: str | None = None
        language: str | None = None
        age_rating: str | None = None
        imprint_val: str | None = None
        subtitle: str | None = None
        series_group: str | None = None
        bundle_titles: list[str] | None = None
        bundle_release_ids: list[str] | None = None
        for edition in item.editions:
            md = getattr(edition, "metadata_json", None)
            if isinstance(md, dict):
                norm = md.get("normalized", md)
                if item.kind == ItemKind.music:
                    track_count = track_count or norm.get("track_count")
                    catalog_number = catalog_number or norm.get("catalog_number")
                    release_status = release_status or norm.get("release_status")
                    raw_tracks = norm.get("tracks")
                    if isinstance(raw_tracks, list) and raw_tracks and tracks is None:
                        tracks = raw_tracks
                raw_creators = norm.get("creators")
                if isinstance(raw_creators, list) and raw_creators and creators is None:
                    creators = raw_creators
                raw_characters = norm.get("characters")
                if isinstance(raw_characters, list) and raw_characters and characters is None:
                    characters = raw_characters
                raw_arcs = norm.get("story_arcs")
                if isinstance(raw_arcs, list) and raw_arcs and story_arcs is None:
                    story_arcs = raw_arcs
                raw_platforms = norm.get("platforms")
                if isinstance(raw_platforms, list) and raw_platforms and platforms is None:
                    platforms = [
                        str(value).strip()
                        for value in raw_platforms
                        if str(value).strip()
                    ]
                raw_genres = norm.get("genres")
                if isinstance(raw_genres, list) and raw_genres and genres is None:
                    genres = raw_genres
                country = country or norm.get("country")
                language = language or norm.get("language")
                age_rating = age_rating or norm.get("age_rating")
                imprint_val = imprint_val or norm.get("imprint")
                subtitle = subtitle or norm.get("subtitle")
                series_group = series_group or norm.get("series_group")
            primary = next((v for v in edition.variants if v.is_primary), None)
            if primary is not None:
                cover_price_cents = cover_price_cents or primary.cover_price_cents
                item_currency = item_currency or primary.currency
        bundle_releases = sorted(
            list(getattr(item, "primary_bundle_releases", []) or []),
            key=lambda bundle: (
                getattr(bundle, "release_date", None) is None,
                -getattr(bundle, "release_date", None).toordinal()
                if getattr(bundle, "release_date", None) is not None
                else 0,
                str(getattr(bundle, "title", "")).casefold(),
            ),
        )
        if bundle_releases:
            bundle_titles = [bundle.title for bundle in bundle_releases if getattr(bundle, "title", None)]
            bundle_release_ids = [str(bundle.id) for bundle in bundle_releases]
        return SearchResult(
            id=item.id,
            kind=item.kind,
            title=item.title,
            item_number=item.item_number,
            synopsis=item.synopsis,
            runtime_minutes=runtime_minutes,
            cover_image_url=cover_url,
            thumbnail_image_url=thumbnail_url,
            edition_title=edition_title,
            physical_format=physical_format_id,
            physical_format_label=physical_format_label,
            publisher=publisher,
            release_date=release_date,
            release_year=release_year,
            barcode=barcode,
            variant=variant_name,
            series_title=series_title,
            volume_name=volume_name,
            track_count=track_count,
            tracks=tracks,
            catalog_number=catalog_number,
            creators=creators,
            characters=characters,
            story_arcs=story_arcs,
            platforms=platforms,
            genres=genres,
            page_count=page_count,
            cover_price_cents=cover_price_cents,
            currency=item_currency,
            country=country,
            release_status=release_status,
            language=language,
            age_rating=age_rating,
            imprint=imprint_val,
            subtitle=subtitle,
            series_group=series_group,
            bundle_titles=bundle_titles,
            bundle_release_ids=bundle_release_ids,
        )

    def _preferred_variant(
        self,
        item,
        *,
        query: str | None = None,
        barcode: str | None = None,
    ):
        normalized_barcode = self._normalized_barcode(barcode)
        normalized_query = " ".join(query.split()).casefold() if query else None
        if not normalized_barcode and not normalized_query:
            return None
        for edition in item.editions:
            for variant in edition.variants:
                if normalized_barcode and normalized_barcode in {
                    self._normalized_barcode(variant.barcode),
                    self._normalized_barcode(variant.isbn),
                    self._normalized_barcode(variant.sku),
                }:
                    return variant
                if normalized_query:
                    values = [
                        variant.name,
                        variant.variant_type,
                        variant.barcode,
                        variant.isbn,
                        variant.sku,
                        variant.platform,
                    ]
                    if any(value and normalized_query in str(value).casefold() for value in values):
                        return variant
        return None

    def _primary_variant(self, item):
        for edition in item.editions:
            primary = next((variant for variant in edition.variants if variant.is_primary), None)
            if primary is not None:
                return primary
            if edition.variants:
                return edition.variants[0]
        return None

    def _variant_cover(self, variant) -> tuple[str | None, str | None]:
        if variant is None:
            return None, None
        return variant.cover_image_url, variant.thumbnail_image_url

    def _normalized_barcode(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().replace("-", "").replace(" ", "").replace(".", "")
        return normalized or None

    def _physical_format(
        self,
        metadata: dict | None,
        *,
        fallback_format: str | None,
        kind: ItemKind,
    ):
        config = None
        if isinstance(metadata, dict):
            normalized = metadata.get("normalized")
            if isinstance(normalized, dict) and normalized.get("physical_format"):
                config = physical_format_for_id(str(normalized["physical_format"]))
        if config is None and fallback_format and is_video_item_kind(kind):
            config = physical_format_for_id(fallback_format)
        return config

    async def get_series_relations(self, series_id: UUID) -> list[SeriesRelationResponse]:
        result = await self.db.execute(
            select(SeriesRelation)
            .where(SeriesRelation.source_series_id == series_id)
            .options(selectinload(SeriesRelation.target_series))
        )
        relations = result.scalars().all()
        return [
            SeriesRelationResponse(
                id=rel.id,
                relation_type=rel.relation_type,
                target_series_id=rel.target_series_id,
                target_series_title=rel.target_series.title,
                target_series_kind=rel.target_series.kind,
                ordinal=rel.ordinal,
                image_url=(rel.metadata_json or {}).get("image_url"),
                start_year=(rel.metadata_json or {}).get("start_year"),
                provider=(rel.metadata_json or {}).get("provider"),
                provider_id=(rel.metadata_json or {}).get("provider_id"),
            )
            for rel in relations
        ]

    async def get_series(self, series_id: UUID) -> SeriesResponse:
        series = await self.db.get(Series, series_id)
        if series is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="series_not_found",
                detail="Series not found",
            )
        volume_count = int(
            await self.db.scalar(
                select(func.count()).select_from(Volume).where(Volume.series_id == series_id)
            )
            or 0
        )
        item_count = int(
            await self.db.scalar(
                select(func.count())
                .select_from(Item)
                .join(Volume, Volume.id == Item.volume_id)
                .where(Volume.series_id == series_id)
            )
            or 0
        )
        tags = await self._entity_tags("series", series_id)
        return SeriesResponse(
            id=series.id,
            kind=series.kind,
            title=series.title,
            description=series.description,
            original_title=series.original_title,
            start_date=series.start_date,
            end_date=series.end_date,
            status=series.status,
            language=series.language,
            country=series.country,
            tags=tags,
            volume_count=volume_count,
            item_count=item_count,
        )

    async def get_series_items(self, series_id: UUID) -> list[SeriesItemResponse]:
        series = await self.db.get(Series, series_id)
        if series is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="series_not_found",
                detail="Series not found",
            )
        items = list(
            (
                await self.db.execute(
                    select(Item)
                    .join(Volume, Volume.id == Item.volume_id)
                    .where(Volume.series_id == series_id)
                    .options(
                        selectinload(Item.volume),
                        selectinload(Item.editions).selectinload(Edition.variants),
                    )
                    .order_by(
                        Volume.start_year.asc().nullslast(),
                        Volume.volume_number.asc().nullslast(),
                        Item.sort_key.asc().nullslast(),
                        Item.title.asc(),
                    )
                )
            ).scalars()
        )
        return [
            SeriesItemResponse(
                series_id=series_id,
                item_id=item.id,
                kind=item.kind,
                title=item.title,
                item_number=item.item_number,
                volume_name=getattr(item.volume, "name", None),
                volume_number=getattr(item.volume, "volume_number", None),
                cover_image_url=self._item_primary_cover_url(item),
            )
            for item in items
        ]

    async def get_provider_seasons(
        self, provider_name: ExternalProvider, provider_item_id: str
    ) -> list[SeasonResponse]:
        from app.providers.base import NormalizedSeason
        from app.schemas.metadata import EpisodeResponse

        provider = self.providers.maybe_get(provider_name)
        if provider is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_not_configured",
                detail=f"Provider '{provider_name.value}' is not configured",
            )
        if not hasattr(provider, "get_seasons"):
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_seasons_unsupported",
                detail=f"Provider '{provider_name.value}' does not support seasons",
            )
        seasons: list[NormalizedSeason] = await provider.get_seasons(provider_item_id)
        return [
            SeasonResponse(
                season_number=s.season_number,
                title=s.title,
                overview=s.overview,
                air_date=s.air_date,
                episode_count=s.episode_count,
                poster_url=s.poster_url,
                episodes=[
                    EpisodeResponse(
                        episode_number=ep.episode_number,
                        title=ep.title,
                        overview=ep.overview,
                        air_date=ep.air_date,
                        runtime_minutes=ep.runtime_minutes,
                        page_count=ep.page_count,
                    )
                    for ep in s.episodes
                ],
            )
            for s in seasons
        ]

    async def get_provider_volumes(
        self, provider_name: ExternalProvider, provider_item_id: str
    ) -> list[SeasonResponse]:
        from app.providers.base import NormalizedSeason
        from app.schemas.metadata import EpisodeResponse

        provider = self.providers.maybe_get(provider_name)
        if provider is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_not_configured",
                detail=f"Provider '{provider_name.value}' is not configured",
            )
        if not hasattr(provider, "get_volumes"):
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_volumes_unsupported",
                detail=f"Provider '{provider_name.value}' does not support volumes",
            )
        volumes: list[NormalizedSeason] = await provider.get_volumes(provider_item_id)
        return [
            SeasonResponse(
                season_number=v.season_number,
                title=v.title,
                overview=v.overview,
                air_date=v.air_date,
                episode_count=v.episode_count,
                poster_url=v.poster_url,
                episodes=[
                    EpisodeResponse(
                        episode_number=ep.episode_number,
                        title=ep.title,
                        overview=ep.overview,
                        air_date=ep.air_date,
                        runtime_minutes=ep.runtime_minutes,
                        page_count=ep.page_count,
                    )
                    for ep in v.episodes
                ],
            )
            for v in volumes
        ]

    async def get_item_volumes(self, item_id: UUID) -> list[SeasonResponse]:
        """Look up provider links for an item and return volumes from the first
        manga-capable provider (MangaDex, then AniList)."""
        from app.models.canonical import ExternalProviderId
        from app.providers.base import NormalizedSeason
        from app.schemas.metadata import EpisodeResponse

        _VOLUME_PROVIDERS = [ExternalProvider.mangadex, ExternalProvider.anilist]

        rows = (
            (
                await self.db.execute(
                    select(ExternalProviderId).where(
                        ExternalProviderId.entity_type == "item",
                        ExternalProviderId.entity_id == item_id,
                    )
                )
            )
            .scalars()
            .all()
        )

        provider_map = {row.provider: row.provider_item_id for row in rows}
        if ExternalProvider.mangadex not in provider_map:
            fallback_id = await self._resolve_mangadex_volume_provider_id(item_id)
            if fallback_id:
                provider_map[ExternalProvider.mangadex] = fallback_id

        for prov_enum in _VOLUME_PROVIDERS:
            pid = provider_map.get(prov_enum)
            if pid is None:
                continue
            provider = self.providers.maybe_get(prov_enum)
            if provider is None or not hasattr(provider, "get_volumes"):
                continue
            volumes: list[NormalizedSeason] = await provider.get_volumes(pid)
            return [
                SeasonResponse(
                    season_number=v.season_number,
                    title=v.title,
                    overview=v.overview,
                    air_date=v.air_date,
                    episode_count=v.episode_count,
                    poster_url=v.poster_url,
                    episodes=[
                        EpisodeResponse(
                            episode_number=ep.episode_number,
                            title=ep.title,
                            overview=ep.overview,
                            air_date=ep.air_date,
                            runtime_minutes=ep.runtime_minutes,
                            page_count=ep.page_count,
                        )
                        for ep in v.episodes
                    ],
                )
                for v in volumes
            ]

        return []

    async def get_item_seasons(self, item_id: UUID) -> list[SeasonResponse]:
        """Look up provider links for an item and return seasons from the first
        TV-capable provider (TMDB)."""
        from app.models.canonical import ExternalProviderId
        from app.providers.base import NormalizedSeason
        from app.schemas.metadata import EpisodeResponse

        _SEASON_PROVIDERS = [ExternalProvider.tmdb]

        rows = (
            (
                await self.db.execute(
                    select(ExternalProviderId).where(
                        ExternalProviderId.entity_type == "item",
                        ExternalProviderId.entity_id == item_id,
                    )
                )
            )
            .scalars()
            .all()
        )

        provider_map = {row.provider: row.provider_item_id for row in rows}

        for prov_enum in _SEASON_PROVIDERS:
            pid = provider_map.get(prov_enum)
            if pid is None:
                continue
            provider = self.providers.maybe_get(prov_enum)
            if provider is None or not hasattr(provider, "get_seasons"):
                continue
            seasons: list[NormalizedSeason] = await provider.get_seasons(pid)
            return [
                SeasonResponse(
                    season_number=s.season_number,
                    title=s.title,
                    overview=s.overview,
                    air_date=s.air_date,
                    episode_count=s.episode_count,
                    poster_url=s.poster_url,
                    episodes=[
                        EpisodeResponse(
                            episode_number=ep.episode_number,
                            title=ep.title,
                            overview=ep.overview,
                            air_date=ep.air_date,
                            runtime_minutes=ep.runtime_minutes,
                            page_count=ep.page_count,
                        )
                        for ep in s.episodes
                    ],
                )
                for s in seasons
            ]

        return []

    async def create_edition(
        self, item_id: UUID, *, title: str, **kwargs: object
    ) -> "EditionResponse":
        item = (
            await self.db.execute(select(Item).where(Item.id == item_id))
        ).scalar_one_or_none()
        if item is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="item_not_found",
                detail="Catalog item not found",
            )
        edition = Edition(item_id=item_id, title=title, **kwargs)
        self.db.add(edition)
        await self.db.flush()
        await self.db.refresh(edition, attribute_names=["variants"])
        await self.db.commit()
        return EditionResponse.model_validate(edition)

    async def search_story_arcs(
        self,
        *,
        q: str | None = None,
        limit: int = 25,
    ) -> list[StoryArcResponse]:
        count_expr = func.count(StoryArcItem.id)
        stmt = (
            select(StoryArc, count_expr.label("item_count"))
            .outerjoin(StoryArcItem, StoryArcItem.story_arc_id == StoryArc.id)
            .group_by(StoryArc.id)
            .order_by(count_expr.desc(), StoryArc.name.asc())
            .limit(limit)
        )
        if q:
            pattern = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(
                    StoryArc.name.ilike(pattern),
                    StoryArc.description.ilike(pattern),
                    StoryArc.publisher.ilike(pattern),
                )
            )
        rows = (await self.db.execute(stmt)).all()
        return [
            StoryArcResponse(
                id=arc.id,
                name=arc.name,
                description=arc.description,
                publisher=arc.publisher,
                start_date=arc.start_date,
                end_date=arc.end_date,
                item_count=int(item_count or 0),
            )
            for arc, item_count in rows
        ]

    async def search_creators(
        self,
        *,
        q: str | None = None,
        limit: int = 25,
    ) -> list[CreatorResponse]:
        count_expr = func.count(EntityPerson.id)
        stmt = (
            select(Person, count_expr.label("item_count"))
            .join(EntityPerson, EntityPerson.person_id == Person.id)
            .where(EntityPerson.entity_type == "item")
            .group_by(Person.id)
            .order_by(count_expr.desc(), Person.name.asc())
            .limit(limit)
        )
        if q:
            pattern = f"%{q.strip()}%"
            stmt = stmt.where(Person.name.ilike(pattern))
        rows = (await self.db.execute(stmt)).all()
        return [
            CreatorResponse(
                id=person.id,
                name=person.name,
                description=_metadata_text(person.metadata_json, "description"),
                image_url=_metadata_text(person.metadata_json, "image_url"),
                api_detail_url=_metadata_text(person.metadata_json, "api_detail_url"),
                site_detail_url=_metadata_text(person.metadata_json, "site_detail_url"),
                item_count=int(item_count or 0),
            )
            for person, item_count in rows
        ]

    async def get_creator_credits(
        self,
        creator_id: UUID,
    ) -> list[CreatorCreditResponse]:
        creator = await self.db.get(Person, creator_id)
        if creator is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="creator_not_found",
                detail="Creator not found",
            )
        links = list(
            (
                await self.db.execute(
                    select(EntityPerson)
                    .where(
                        EntityPerson.person_id == creator_id,
                        EntityPerson.entity_type == "item",
                    )
                    .order_by(EntityPerson.role.asc(), EntityPerson.created_at.asc())
                )
            ).scalars()
        )
        if not links:
            return []

        item_ids = [link.entity_id for link in links]
        items = {
            item.id: item
            for item in (
                await self.db.execute(
                    select(Item)
                    .where(Item.id.in_(item_ids))
                    .options(
                        selectinload(Item.volume).selectinload(Volume.series),
                        selectinload(Item.editions).selectinload(Edition.variants),
                    )
                )
            ).scalars()
        }
        results: list[CreatorCreditResponse] = []
        for link in links:
            item = items.get(link.entity_id)
            if item is None:
                continue
            results.append(
                CreatorCreditResponse(
                    creator_id=creator_id,
                    item_id=item.id,
                    role=link.role,
                    kind=item.kind,
                    title=item.title,
                    item_number=item.item_number,
                    series_title=getattr(getattr(item.volume, "series", None), "title", None),
                    volume_name=getattr(item.volume, "name", None),
                    cover_image_url=self._item_primary_cover_url(item),
                )
            )
        return results

    async def get_story_arc_items(self, story_arc_id: UUID) -> list[StoryArcItemResponse]:
        arc = await self.db.get(StoryArc, story_arc_id)
        if arc is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="story_arc_not_found",
                detail="Story arc not found",
            )
        links = list(
            (
                await self.db.execute(
                    select(StoryArcItem)
                    .where(StoryArcItem.story_arc_id == story_arc_id)
                    .options(
                        selectinload(StoryArcItem.item)
                        .selectinload(Item.volume)
                        .selectinload(Volume.series),
                        selectinload(StoryArcItem.item)
                        .selectinload(Item.editions)
                        .selectinload(Edition.variants),
                    )
                    .order_by(
                        StoryArcItem.ordinal.asc().nullslast(),
                        StoryArcItem.created_at.asc(),
                    )
                )
            ).scalars()
        )
        return [
            StoryArcItemResponse(
                story_arc_id=story_arc_id,
                item_id=link.item.id,
                ordinal=link.ordinal,
                kind=link.item.kind,
                title=link.item.title,
                item_number=link.item.item_number,
                series_title=getattr(getattr(link.item.volume, "series", None), "title", None),
                volume_name=getattr(link.item.volume, "name", None),
                cover_image_url=self._item_primary_cover_url(link.item),
            )
            for link in links
            if link.item is not None
        ]

    async def get_story_arc_facets(
        self,
        item_ids: list[UUID],
    ) -> list[StoryArcFacetResponse]:
        ordered_item_ids = list(dict.fromkeys(item_ids))
        if not ordered_item_ids:
            return []

        item_order = {item_id: index for index, item_id in enumerate(ordered_item_ids)}
        rows = (
            await self.db.execute(
                select(StoryArc, StoryArcItem.item_id)
                .join(StoryArcItem, StoryArcItem.story_arc_id == StoryArc.id)
                .where(StoryArcItem.item_id.in_(ordered_item_ids))
            )
        ).all()
        grouped: dict[UUID, dict[str, object]] = {}
        for arc, item_id in rows:
            bucket = grouped.setdefault(
                arc.id,
                {
                    "arc": arc,
                    "item_ids": set(),
                },
            )
            cast_item_ids = bucket["item_ids"]
            if isinstance(cast_item_ids, set):
                cast_item_ids.add(item_id)

        facets: list[StoryArcFacetResponse] = []
        for bucket in grouped.values():
            arc = bucket["arc"]
            if not isinstance(arc, StoryArc):
                continue
            raw_item_ids = bucket["item_ids"]
            if not isinstance(raw_item_ids, set):
                continue
            facet_item_ids = sorted(
                raw_item_ids,
                key=lambda item_id: item_order.get(item_id, len(item_order)),
            )
            facets.append(
                StoryArcFacetResponse(
                    id=arc.id,
                    name=arc.name,
                    description=arc.description,
                    publisher=arc.publisher,
                    start_date=arc.start_date,
                    end_date=arc.end_date,
                    item_count=len(facet_item_ids),
                    item_ids=facet_item_ids,
                )
            )
        facets.sort(key=lambda facet: (-facet.item_count, facet.name.casefold()))
        return facets

    async def get_creator_facets(
        self,
        item_ids: list[UUID],
    ) -> list[CreatorFacetResponse]:
        ordered_item_ids = list(dict.fromkeys(item_ids))
        if not ordered_item_ids:
            return []

        item_order = {item_id: index for index, item_id in enumerate(ordered_item_ids)}
        rows = (
            await self.db.execute(
                select(Person, EntityPerson.entity_id, EntityPerson.role)
                .join(EntityPerson, EntityPerson.person_id == Person.id)
                .where(
                    EntityPerson.entity_type == "item",
                    EntityPerson.entity_id.in_(ordered_item_ids),
                )
            )
        ).all()
        grouped: dict[UUID, dict[str, object]] = {}
        for person, item_id, role in rows:
            bucket = grouped.setdefault(
                person.id,
                {
                    "person": person,
                    "item_ids": set(),
                    "role_counts": {},
                },
            )
            cast_item_ids = bucket["item_ids"]
            if isinstance(cast_item_ids, set):
                cast_item_ids.add(item_id)
            cast_role_counts = bucket["role_counts"]
            if isinstance(cast_role_counts, dict):
                cast_role_counts[role] = int(cast_role_counts.get(role, 0)) + 1

        facets: list[CreatorFacetResponse] = []
        for bucket in grouped.values():
            person = bucket["person"]
            if not isinstance(person, Person):
                continue
            raw_item_ids = bucket["item_ids"]
            if not isinstance(raw_item_ids, set):
                continue
            facet_item_ids = sorted(
                raw_item_ids,
                key=lambda item_id: item_order.get(item_id, len(item_order)),
            )
            role_counts = bucket["role_counts"]
            facets.append(
                CreatorFacetResponse(
                    id=person.id,
                    name=person.name,
                    description=_metadata_text(person.metadata_json, "description"),
                    image_url=_metadata_text(person.metadata_json, "image_url"),
                    item_count=len(facet_item_ids),
                    item_ids=facet_item_ids,
                    role_counts=role_counts if isinstance(role_counts, dict) else {},
                )
            )
        facets.sort(key=lambda facet: (-facet.item_count, facet.name.casefold()))
        return facets

    async def search_characters(
        self,
        *,
        q: str | None = None,
        limit: int = 25,
    ) -> list[CharacterResponse]:
        count_expr = func.count(CharacterAppearance.id)
        stmt = (
            select(Character, count_expr.label("appearance_count"))
            .outerjoin(CharacterAppearance, CharacterAppearance.character_id == Character.id)
            .group_by(Character.id)
            .order_by(count_expr.desc(), Character.name.asc())
            .limit(limit)
        )
        if q:
            pattern = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(
                    Character.name.ilike(pattern),
                    Character.description.ilike(pattern),
                )
            )
        rows = (await self.db.execute(stmt)).all()
        return [
            CharacterResponse(
                id=character.id,
                name=character.name,
                aliases=[str(alias) for alias in (character.aliases or []) if str(alias).strip()],
                description=character.description,
                image_url=character.image_url,
                first_appearance_item_id=character.first_appearance_item_id,
                appearance_count=int(appearance_count or 0),
            )
            for character, appearance_count in rows
        ]

    async def get_character_appearances(
        self,
        character_id: UUID,
    ) -> list[CharacterAppearanceResponse]:
        character = await self.db.get(Character, character_id)
        if character is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="character_not_found",
                detail="Character not found",
            )
        links = list(
            (
                await self.db.execute(
                    select(CharacterAppearance)
                    .where(CharacterAppearance.character_id == character_id)
                    .options(
                        selectinload(CharacterAppearance.item)
                        .selectinload(Item.volume)
                        .selectinload(Volume.series),
                        selectinload(CharacterAppearance.item)
                        .selectinload(Item.editions)
                        .selectinload(Edition.variants),
                    )
                    .order_by(
                        CharacterAppearance.role.asc(),
                        CharacterAppearance.created_at.asc(),
                    )
                )
            ).scalars()
        )
        return [
            CharacterAppearanceResponse(
                character_id=character_id,
                item_id=link.item.id,
                role=link.role,
                kind=link.item.kind,
                title=link.item.title,
                item_number=link.item.item_number,
                series_title=getattr(getattr(link.item.volume, "series", None), "title", None),
                volume_name=getattr(link.item.volume, "name", None),
                cover_image_url=self._item_primary_cover_url(link.item),
            )
            for link in links
            if link.item is not None
        ]

    async def get_character_facets(
        self,
        item_ids: list[UUID],
    ) -> list[CharacterFacetResponse]:
        ordered_item_ids = list(dict.fromkeys(item_ids))
        if not ordered_item_ids:
            return []

        item_order = {item_id: index for index, item_id in enumerate(ordered_item_ids)}
        rows = (
            await self.db.execute(
                select(Character, CharacterAppearance.item_id, CharacterAppearance.role)
                .join(
                    CharacterAppearance,
                    CharacterAppearance.character_id == Character.id,
                )
                .where(CharacterAppearance.item_id.in_(ordered_item_ids))
            )
        ).all()
        grouped: dict[UUID, dict[str, object]] = {}
        for character, item_id, role in rows:
            bucket = grouped.setdefault(
                character.id,
                {
                    "character": character,
                    "item_ids": set(),
                    "role_counts": {},
                },
            )
            cast_item_ids = bucket["item_ids"]
            if isinstance(cast_item_ids, set):
                cast_item_ids.add(item_id)
            cast_role_counts = bucket["role_counts"]
            if isinstance(cast_role_counts, dict):
                role_key = str(role or "main")
                cast_role_counts[role_key] = int(cast_role_counts.get(role_key, 0)) + 1

        facets: list[CharacterFacetResponse] = []
        for bucket in grouped.values():
            character = bucket["character"]
            if not isinstance(character, Character):
                continue
            raw_item_ids = bucket["item_ids"]
            raw_role_counts = bucket["role_counts"]
            if not isinstance(raw_item_ids, set) or not isinstance(raw_role_counts, dict):
                continue
            facet_item_ids = sorted(
                raw_item_ids,
                key=lambda item_id: item_order.get(item_id, len(item_order)),
            )
            facets.append(
                CharacterFacetResponse(
                    id=character.id,
                    name=character.name,
                    aliases=[
                        str(alias) for alias in (character.aliases or []) if str(alias).strip()
                    ],
                    image_url=character.image_url,
                    item_count=len(facet_item_ids),
                    item_ids=facet_item_ids,
                    role_counts={str(role): int(count) for role, count in raw_role_counts.items()},
                )
            )
        facets.sort(key=lambda facet: (-facet.item_count, facet.name.casefold()))
        return facets

    async def _resolve_mangadex_volume_provider_id(self, item_id: UUID) -> str | None:
        item = await self.metadata.get_item(item_id)
        if item is None or item.kind != ItemKind.manga:
            return None
        provider = self.providers.maybe_get(ExternalProvider.mangadex)
        if provider is None or not provider.capabilities.supports_search:
            return None

        query = self._manga_volume_lookup_query(item)
        if not query:
            return None

        try:
            results = await self._search_provider_live(
                ExternalProvider.mangadex,
                provider,
                query,
                ItemKind.manga,
            )
        except ApiHTTPException:
            logger.debug(
                "mangadex_volume_lookup_failed item_id=%s query=%s",
                item_id,
                query,
                exc_info=True,
            )
            return None
        candidate = self._best_mangadex_volume_candidate(item, results)
        return candidate.provider_item_id if candidate else None

    def _manga_volume_lookup_query(self, item) -> str:
        series_title = getattr(getattr(item.volume, "series", None), "title", None)
        title = series_title or item.title
        if not title:
            return ""
        cleaned = re.sub(r"\s+#?\d+(?:[./-]\d+)?$", "", str(title)).strip()
        return cleaned or str(title).strip()

    def _best_mangadex_volume_candidate(
        self,
        item,
        results: list[ProviderSearchResult],
    ) -> ProviderSearchResult | None:
        series_title = getattr(getattr(item.volume, "series", None), "title", None)
        volume_name = getattr(item.volume, "name", None)
        targets = {
            text
            for text in (
                self._normalized_title(item.title),
                self._normalized_title(series_title),
                self._normalized_title(volume_name),
            )
            if text
        }
        best: ProviderSearchResult | None = None
        best_score = 0
        for index, result in enumerate(results[:10]):
            if result.kind != ItemKind.manga or not result.provider_item_id:
                continue
            score = self._manga_title_match_score(targets, result)
            if score <= 0:
                continue
            ranked_score = score * 100 - index
            if ranked_score > best_score:
                best_score = ranked_score
                best = result
        return best

    def _manga_title_match_score(
        self,
        targets: set[str],
        result: ProviderSearchResult,
    ) -> int:
        title = self._normalized_title(result.series_title or result.title)
        if not title:
            return 0
        if title in targets:
            return 4
        if any(
            len(target) >= 4
            and len(title) >= 4
            and (title.startswith(target) or target.startswith(title))
            for target in targets
        ):
            return 3
        if any(
            len(target) >= 6 and len(title) >= 6 and (title in target or target in title)
            for target in targets
        ):
            return 2
        return 0

    def _normalized_title(self, value: str | None) -> str:
        if not value:
            return ""
        text = re.sub(r"\s+", " ", str(value)).casefold().strip()
        text = re.sub(r"\((?:19|20)\d{2}\)", "", text)
        text = re.sub(r"[^0-9a-z\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _item_primary_cover_url(self, item: Item) -> str | None:
        for edition in item.editions or []:
            variants = list(edition.variants or [])
            primary = next((variant for variant in variants if variant.is_primary), None)
            if primary and primary.cover_image_url:
                return primary.cover_image_url
            if variants and variants[0].cover_image_url:
                return variants[0].cover_image_url
        return None
