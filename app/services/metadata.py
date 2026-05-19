import logging
import re
import asyncio
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
    Item,
    MetadataProposal,
    SeriesRelation,
    StoryArc,
    StoryArcItem,
    Volume,
)
from app.providers.base import MetadataProvider, ProviderSearchResult
from app.providers.comicvine import ComicVineProvider
from app.providers.gcd import GCDProvider
from app.providers.registry import ProviderRegistry
from app.repositories.metadata import MetadataRepository
from app.schemas.metadata import (
    CharacterAppearanceResponse,
    CharacterResponse,
    ItemResponse,
    MetadataProposalCreate,
    MetadataProposalResponse,
    ProviderSearchResultResponse,
    SeasonResponse,
    SearchResult,
    StoryArcItemResponse,
    StoryArcResponse,
    SeriesRelationResponse,
    item_response_from_model,
)
from app.search.client import SearchClient
from app.services.provider_search_state import ProviderSearchState
from app.storage.image_cache import ImageCache
from app.storage.images import ImageMirror

logger = logging.getLogger(__name__)

_UPSTREAM_HTTP_STATUS_RE = re.compile(r"\bHTTP\s+(?P<status>\d{3})\b")
_PROVIDER_INTERNAL_RETRY_NAMES = {ExternalProvider.bgg.value, ExternalProvider.comicvine.value}


class MetadataService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()
        self.metadata = MetadataRepository(db)
        self.search_client = SearchClient()
        self.providers = ProviderRegistry()
        self.provider_search_state = ProviderSearchState(self.settings)

    async def get_item(self, item_id: UUID, kind: ItemKind) -> ItemResponse:
        item = await self.metadata.get_item(item_id, kind)
        if item is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="metadata_item_not_found",
                detail="Item not found",
            )
        return item_response_from_model(item)

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
        provider_name: ExternalProvider,
        query: str,
        kind: ItemKind | None,
    ) -> tuple[str, str, str]:
        normalized_query = " ".join(query.split()).casefold()
        return provider_name.value, kind.value if kind else "*", normalized_query

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
        return base_query

    def _clean_provider_query_part(self, value: str | None) -> str:
        return " ".join(str(value or "").split())

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
        return SearchResult(
            id=item.id,
            kind=item.kind,
            title=item.title,
            item_number=item.item_number,
            synopsis=item.synopsis,
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
                        still_url=ep.still_url,
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
                        still_url=ep.still_url,
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
            await self.db.execute(
                select(ExternalProviderId).where(
                    ExternalProviderId.entity_type == "item",
                    ExternalProviderId.entity_id == item_id,
                )
            )
        ).scalars().all()

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
                            still_url=ep.still_url,
                        )
                        for ep in v.episodes
                    ],
                )
                for v in volumes
            ]

        return []

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
                aliases=[str(alias) for alias in (character.aliases or []) if alias],
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
            len(target) >= 6
            and len(title) >= 6
            and (title in target or target in title)
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
