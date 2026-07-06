from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import replace
from urllib.parse import urlparse

from app.core.errors import ApiHTTPException
from app.models.base import ExternalProvider, ItemKind
from app.providers.base import MetadataProvider, ProviderSearchResult
from app.providers.comicvine import ComicVineProvider
from app.providers.gcd import GCDProvider

logger = logging.getLogger(__name__)
_UPSTREAM_HTTP_STATUS_RE = re.compile(r"\bHTTP\s+(?P<status>\d{3})\b")


class MetadataProviderSearchSupport:
    def _provider_search_cache_key(
        self,
        provider_name: ExternalProvider | str,
        query: str,
        kind: ItemKind | None,
    ) -> tuple[str, str, str]:
        normalized_query = " ".join(query.split()).casefold()
        return self._provider_search_cache_namespace(provider_name), kind.value if kind else "*", normalized_query

    def _provider_search_cache_namespace(self, provider_name: ExternalProvider | str) -> str:
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
                parts.append(f"date:{year}")
            return " AND ".join(parts)
        return base_query

    def _clean_provider_query_part(self, value: str | None) -> str:
        return " ".join(str(value or "").split())

    def _escape_provider_query_phrase(self, value: str) -> str:
        return value.replace('"', r'\"')

    def _clean_issue_number(self, value: str | None) -> str:
        text = self._clean_provider_query_part(value)
        return re.sub(r"^#+\s*", "", text)

    async def _cached_provider_search_results(self, key: tuple[str, str, str]) -> list[ProviderSearchResult] | None:
        return await self.provider_search_state.cached(key)

    async def _store_provider_search_results(self, key: tuple[str, str, str], results: list[ProviderSearchResult]) -> None:
        await self.provider_search_state.store(key, results)

    async def _raise_if_provider_on_backoff(self, provider_name: ExternalProvider) -> None:
        await self.provider_search_state.raise_if_backoff(provider_name)

    async def _search_provider_live(
        self,
        provider_name: ExternalProvider,
        provider: MetadataProvider,
        query: str,
        kind: ItemKind | None,
    ) -> list[ProviderSearchResult]:
        await self._raise_if_provider_on_backoff(provider_name)

        attempts = max(1, self.settings.provider_search_retry_attempts + 1)
        last_error: ApiHTTPException | None = None
        for attempt in range(attempts):
            try:
                return await provider.search(query, kind)
            except ApiHTTPException as exc:
                last_error = exc
                if not self._should_retry_provider_search(exc) or attempt >= attempts - 1:
                    await self._record_provider_search_backoff(provider_name, exc)
                    raise
                await asyncio.sleep(self._provider_search_retry_delay(exc, attempt))

        if last_error is not None:
            await self._record_provider_search_backoff(provider_name, last_error)
            raise last_error
        return []

    async def _record_provider_search_backoff(self, provider_name: ExternalProvider, exc: ApiHTTPException) -> None:
        seconds = self._provider_search_retry_after(exc) or self.settings.provider_search_backoff_seconds
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

    async def _with_stable_provider_image_urls(self, results: list[ProviderSearchResult]) -> list[ProviderSearchResult]:
        stable_results: list[ProviderSearchResult] = []
        for result in results:
            mirrored_url = await self.mirror_provider_image_url(
                result.image_url,
                provider_name=result.provider,
                provider_item_id=result.provider_item_id,
                cache_only=True,
            )
            stable_results.append(replace(result, image_url=mirrored_url) if mirrored_url else result)
        return stable_results

    def _can_mirror_provider_image(self, provider_name: str | ExternalProvider, source_url: str | None) -> bool:
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

    def _provider_for_name(self, provider_name: str | ExternalProvider) -> MetadataProvider | None:
        try:
            provider_enum = provider_name if isinstance(provider_name, ExternalProvider) else ExternalProvider(str(provider_name))
        except ValueError:
            return None
        return self.providers.maybe_get(provider_enum)

    def _provider_value(self, provider_name: str | ExternalProvider) -> str:
        return provider_name.value if isinstance(provider_name, ExternalProvider) else str(provider_name)

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
        if target_kind != ItemKind.comic:
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
        if target_kind != ItemKind.comic:
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
