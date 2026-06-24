import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote, urlencode, urlparse

import httpx
from fastapi import status

from app.core.config import get_settings
from app.core.errors import ApiHTTPException
from app.models.base import ItemKind
from app.providers.base import (
    NormalizedCredit,
    NormalizedItem,
    ProviderCapabilities,
    ProviderItem,
    ProviderSearchResult,
)
from app.providers.normalize import (
    canonical_credit_role,
    normalize_title,
    preview_names,
    title_aliases,
)

_ISSUE_ID_RE = re.compile(r"/issue/(\d+)/?")
_SERIES_ID_RE = re.compile(r"/series/(\d+)/?")
_SERIES_YEAR_RE = re.compile(r"\s+\((?P<year>\d{4})\s+series\)$")
_ISSUE_QUERY_RE = re.compile(
    r"^(?P<series>.+?)\s*(?:#|issue\s+|no\.?\s*)?\s*(?P<issue>\d+[A-Za-z0-9./-]*)$",
    re.IGNORECASE,
)
_YEAR_HINT_RE = re.compile(r"\b(?P<year>18\d{2}|19\d{2}|20\d{2}|21\d{2}|2200)\b")
_TRAILING_VARIANT_HINT_RE = re.compile(
    r"\s+(?:variant|variants?|cover|covers?|cover\s+[a-z]|standard|regular|main|foil|virgin|"
    r"incentive|ratio)\s*$",
    re.IGNORECASE,
)
_PRICE_RE = re.compile(r"(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<currency>[A-Z]{3})")
_EDITOR_SUFFIX_RE = re.compile(r"\s+\((?:editor|editors?)\)$", re.IGNORECASE)
_EMPTY_CREDIT_VALUES = {"", "?", "none", "[none]", "n/a"}
_ALLOWED_COVER_HOSTS = {"files1.comics.org", "www.comics.org"}

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GCDCoverFallback:
    series_title: str | None = None
    issue_number: str | None = None
    start_year: int | None = None
    variant_hint: str | None = None

    def merge(self, other: "GCDCoverFallback") -> "GCDCoverFallback":
        return GCDCoverFallback(
            series_title=self.series_title or other.series_title,
            issue_number=self.issue_number or other.issue_number,
            start_year=self.start_year or other.start_year,
            variant_hint=self.variant_hint or other.variant_hint,
        )


@dataclass(frozen=True)
class GCDCoverImage:
    content: bytes | None = None
    media_type: str | None = None
    redirect_url: str | None = None
    source_url: str | None = None

    @classmethod
    def inline(
        cls,
        content: bytes,
        media_type: str,
        *,
        source_url: str | None = None,
    ) -> "GCDCoverImage":
        return cls(content=content, media_type=media_type, source_url=source_url)

    @classmethod
    def redirect(cls, url: str) -> "GCDCoverImage":
        return cls(redirect_url=url, source_url=url)


@dataclass(frozen=True)
class GCDQueryPlan:
    candidates: list[tuple[str, str]]
    year_hint: int | None = None
    is_series_search: bool = False


class GCDProvider:
    name = "gcd"
    capabilities = ProviderCapabilities(
        kind=ItemKind.comic,
        display_name="Grand Comics Database",
        supports_search=True,
        supports_ingest=True,
        requires_user_key=False,
        non_commercial_only=False,
        allows_redistribution=True,
        requires_attribution=True,
        license_name="CC BY-SA 4.0",
        terms_url="https://www.comics.org/",
        attribution_url="https://www.comics.org/",
        cache_policy="Cache with attribution and share-alike provenance; cover rights vary.",
    )

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def is_configured(self) -> bool:
        return True

    @property
    def status_message(self) -> str:
        return "GCD metadata is available without an API key."

    async def search(
        self,
        query: str,
        kind: ItemKind | None = None,
    ) -> list[ProviderSearchResult]:
        plan = self._query_plan(query)
        if not plan.candidates:
            return []

        normalized_results: list[ProviderSearchResult] = []
        seen: set[str] = set()
        active_year_hint = plan.year_hint
        active_series_alias: str | None = None
        series_candidate_emitted = False
        for series_name, issue_number in plan.candidates:
            series_alias_key = series_name.casefold()
            if (
                plan.is_series_search
                and active_series_alias is not None
                and series_alias_key != active_series_alias
            ):
                continue
            path = (
                f"series/name/{quote(series_name, safe='')}/issue/{quote(issue_number, safe='')}/"
            )
            payload = await self._request(path)
            results = payload.get("results") or []
            if not isinstance(results, list):
                continue

            issue_results = [result for result in results if isinstance(result, Mapping)]
            if active_year_hint is None and plan.is_series_search:
                issue_results.sort(key=lambda result: self._series_rank(result, series_name))
                active_year_hint = self._first_result_start_year(issue_results)
            if active_year_hint is not None:
                issue_results = [
                    result
                    for result in issue_results
                    if self._series_start_year(self._optional_text(result.get("series_name")) or "")
                    == active_year_hint
                ]
            issue_results.sort(
                key=lambda result: self._series_rank(
                    result,
                    series_name,
                    year_hint=active_year_hint,
                )
            )
            if issue_results and plan.is_series_search and active_series_alias is None:
                active_series_alias = series_alias_key

            if (
                plan.is_series_search
                and not series_candidate_emitted
                and issue_results
            ):
                series_result = self._series_candidate(
                    issue_results[0],
                    issue_count=payload.get("count"),
                )
                if series_result is not None:
                    normalized_results.insert(0, series_result)
                    series_candidate_emitted = True

            for result in issue_results[: self.settings.gcd_search_limit]:
                search_result = self._search_result(result)
                if not search_result.provider_item_id:
                    continue
                if search_result.provider_item_id in seen:
                    continue
                seen.add(search_result.provider_item_id)
                normalized_results.append(search_result)
                if len(normalized_results) >= self.settings.gcd_search_limit:
                    return normalized_results
            if normalized_results and not plan.is_series_search:
                return normalized_results
        return normalized_results

    async def get_item(self, provider_item_id: str) -> ProviderItem:
        issue_id = self._issue_id(provider_item_id)
        if issue_id is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="gcd_invalid_issue_id",
                detail="Invalid GCD issue id",
            )
        payload = await self._request(f"issue/{issue_id}/")
        if not isinstance(payload, Mapping):
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="gcd_invalid_item",
                detail="Invalid GCD item",
            )
        return ProviderItem(provider=self.name, provider_item_id=issue_id, raw=payload)

    async def get_cover_image(
        self,
        provider_item_id: str,
        fallback: GCDCoverFallback | None = None,
    ) -> GCDCoverImage:
        issue_id = self._issue_id(provider_item_id)
        if issue_id is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="gcd_invalid_issue_id",
                detail="Invalid GCD issue id",
            )
        fallback = fallback or GCDCoverFallback()
        last_error: ApiHTTPException | None = None
        try:
            item = await self.get_item(issue_id)
            fallback = fallback.merge(await self._cover_fallback_from_item(item.raw))
            cover_url = self._optional_text(item.raw.get("cover"))
            if cover_url is not None:
                try:
                    content, media_type = await self._download_cover_image(cover_url, issue_id)
                    return GCDCoverImage.inline(content, media_type, source_url=cover_url)
                except ApiHTTPException as exc:
                    last_error = exc
            else:
                last_error = ApiHTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="gcd_cover_not_found",
                    detail="GCD issue does not include a cover image",
                )
        except ApiHTTPException as exc:
            last_error = exc

        fallback_cover = await self._comicvine_cover_fallback(fallback)
        if fallback_cover is not None:
            return fallback_cover

        if self._requires_variant_cover_match(fallback.variant_hint):
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="provider_variant_cover_not_found",
                detail="No exact variant cover image was available",
            )

        if last_error is not None:
            raise last_error
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="provider_cover_not_found",
            detail="No provider cover image was available",
        )

    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem:
        issue_id = self._issue_id(data.get("api_url") or data.get("id"))
        series_url = self._optional_text(data.get("series"))
        series_id = self._series_id(series_url)
        raw_series_name = self._optional_text(data.get("series_name")) or "Unknown comic"
        series_title = self._series_title(raw_series_name)
        volume_start_year = self._series_start_year(raw_series_name)
        issue_number = self._optional_text(data.get("number")) or self._descriptor_number(data)
        variant_name = self._optional_text(data.get("variant_name"))
        issue_title = self._optional_text(data.get("title"))
        release_date = self._date(data.get("on_sale_date")) or self._date(data.get("key_date"))
        cover_price_cents, currency = self._price(data.get("price"))
        publisher, imprint = self._publisher_and_imprint(data)
        cover_image_url = self._normalized_cover_image_url(
            data,
            issue_id=issue_id,
            series_title=series_title,
            issue_number=issue_number,
            start_year=volume_start_year,
            variant_hint=variant_name or self._variant_name_from_descriptor(data),
        )

        return NormalizedItem(
            kind=ItemKind.comic,
            title=series_title,
            item_number=issue_number,
            synopsis=self._synopsis(data),
            series_title=series_title,
            volume_name=series_title,
            volume_start_year=volume_start_year,
            page_count=self._int_decimal(data.get("page_count")),
            edition_title=issue_title or "Standard Edition",
            edition_format="Single Issue",
            publisher=publisher,
            imprint=imprint,
            release_date=release_date,
            isbn=self._optional_text(data.get("isbn")),
            barcode=self._optional_text(data.get("barcode")),
            cover_price_cents=cover_price_cents,
            currency=currency,
            variant_name=variant_name or self._variant_name_from_descriptor(data),
            variant_type="variant" if data.get("variant_of") else None,
            cover_image_url=cover_image_url,
            creators=self._credits(data.get("story_set"), issue_editing=data.get("editing")),
            characters=self._characters(data.get("story_set")),
            story_arcs=self._story_arcs(data.get("story_set")),
            provider_ids={self.name: issue_id} if issue_id else {},
            volume_provider_ids={self.name: series_id} if series_id else {},
        )

    async def _request(self, path: str) -> dict[str, Any]:
        url = f"{self.settings.gcd_base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.gcd_timeout_seconds,
                headers={"User-Agent": self.settings.gcd_user_agent, "Accept": "application/json"},
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="gcd_http_error",
                detail=f"GCD returned HTTP {exc.response.status_code}",
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="gcd_request_failed",
                detail="GCD request failed",
            ) from exc
        if not isinstance(payload, dict):
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="gcd_invalid_response",
                detail="Invalid GCD response",
            )
        return payload

    def _search_result(self, result: Mapping[str, Any]) -> ProviderSearchResult:
        issue_id = self._issue_id(result.get("api_url"))
        series_name = self._optional_text(result.get("series_name")) or "Unknown GCD issue"
        series_title = self._series_title(series_name)
        start_year = self._series_start_year(series_name)
        descriptor = self._optional_text(result.get("descriptor"))
        title = f"{series_name} #{descriptor}" if descriptor else series_name
        issue_number = self._descriptor_number(result) or descriptor
        variant_hint = self._variant_name_from_descriptor(result)
        summary_parts = [
            self._optional_text(result.get("publication_date")),
            self._optional_text(result.get("price")),
            self._page_summary(result.get("page_count")),
            "variant" if result.get("variant_of") else None,
        ]
        character_preview = self._preview_names(self._characters(result.get("story_set")))
        story_arc_preview = self._preview_names(self._story_arcs(result.get("story_set")))
        return ProviderSearchResult(
            provider=self.name,
            provider_item_id=issue_id or "",
            title=title,
            kind=ItemKind.comic,
            summary=" · ".join(part for part in summary_parts if part),
            image_url=self._cover_proxy_url(
                issue_id,
                series_title=series_title,
                issue_number=issue_number,
                start_year=start_year,
                variant_hint=variant_hint,
            )
            or self._optional_text(result.get("cover")),
            candidate_type="variant" if result.get("variant_of") else "issue",
            series_title=series_title,
            issue_number=issue_number,
            volume_start_year=start_year,
            variant_name=variant_hint,
            is_variant=bool(result.get("variant_of")),
            character_preview=character_preview,
            story_arc_preview=story_arc_preview,
        )

    def _series_candidate(
        self,
        representative_issue: Mapping[str, Any],
        *,
        issue_count: Any = None,
    ) -> ProviderSearchResult | None:
        series_url = self._optional_text(representative_issue.get("series"))
        series_id = self._series_id(series_url)
        if not series_id:
            return None
        series_name = (
            self._optional_text(representative_issue.get("series_name")) or "Unknown series"
        )
        series_title = self._series_title(series_name)
        start_year = self._series_start_year(series_name)
        publisher = self._publisher(representative_issue)
        count = int(issue_count) if issue_count is not None and str(issue_count).isdigit() else None
        first_issue_id = self._issue_id(representative_issue.get("api_url"))
        summary_parts = [
            publisher,
            f"{start_year} series" if start_year else None,
            f"{count} issues" if count else None,
        ]
        character_preview = self._preview_names(self._characters(representative_issue.get("story_set")))
        story_arc_preview = self._preview_names(self._story_arcs(representative_issue.get("story_set")))
        return ProviderSearchResult(
            provider=self.name,
            provider_item_id=f"series-{series_id}",
            title=series_title,
            kind=ItemKind.comic,
            summary=" · ".join(part for part in summary_parts if part),
            image_url=self._cover_proxy_url(
                first_issue_id,
                series_title=series_title,
                issue_number="1",
                start_year=start_year,
            ),
            candidate_type="series",
            series_title=series_title,
            volume_start_year=start_year,
            is_variant=False,
            issue_count=count,
            publisher=publisher,
            character_preview=character_preview,
            story_arc_preview=story_arc_preview,
        )

    async def _download_cover_image(self, cover_url: str, issue_id: str) -> tuple[bytes, str]:
        parsed = urlparse(cover_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in _ALLOWED_COVER_HOSTS:
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="gcd_cover_url_untrusted",
                detail="GCD returned an unsupported cover image URL",
            )
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.gcd_timeout_seconds,
                headers={
                    "User-Agent": self.settings.gcd_user_agent,
                    "Accept": "image/*",
                    "Referer": f"https://www.comics.org/issue/{issue_id}/",
                },
                follow_redirects=True,
            ) as client:
                response = await client.get(cover_url)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.info(
                "gcd_cover_download_failed issue_id=%s status=%s",
                issue_id,
                exc.response.status_code,
            )
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="gcd_cover_download_failed",
                detail=f"GCD cover download returned HTTP {exc.response.status_code}",
            ) from exc
        except httpx.HTTPError as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="gcd_cover_download_failed",
                detail="GCD cover download failed",
            ) from exc
        media_type = response.headers.get("content-type", "image/jpeg").split(";", 1)[0]
        if not media_type.startswith("image/"):
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="gcd_cover_invalid_content_type",
                detail="GCD cover response was not an image",
            )
        return response.content, media_type

    async def _cover_fallback_from_item(self, data: Mapping[str, Any]) -> GCDCoverFallback:
        normalized = await self.normalize(data)
        return GCDCoverFallback(
            series_title=normalized.series_title or normalized.title,
            issue_number=normalized.item_number,
            start_year=normalized.volume_start_year,
            variant_hint=normalized.variant_name,
        )

    async def _comicvine_cover_fallback(
        self,
        fallback: GCDCoverFallback,
    ) -> GCDCoverImage | None:
        if not fallback.series_title or not fallback.issue_number:
            return None

        from app.providers.comicvine import ComicVineProvider

        provider = ComicVineProvider()
        if not provider.is_configured:
            return None
        try:
            cover = await provider.find_issue_cover(
                series_title=fallback.series_title,
                issue_number=fallback.issue_number,
                start_year=fallback.start_year,
                variant_hint=fallback.variant_hint,
                require_variant_match=bool(fallback.variant_hint),
            )
        except Exception:
            logger.warning(
                "comicvine_cover_fallback_lookup_failed series=%s issue=%s",
                fallback.series_title,
                fallback.issue_number,
                exc_info=True,
            )
            return None
        if cover is None:
            return None
        return GCDCoverImage.redirect(cover.image_url)

    def _requires_variant_cover_match(self, variant_hint: str | None) -> bool:
        terms = {term.casefold() for term in self._variant_terms(variant_hint)}
        return bool(
            terms
            & {
                "variant",
                "virgin",
                "foil",
                "exclusive",
                "incentive",
                "ratio",
                "printing",
                "cardstock",
                "blank",
                "nycc",
            }
        )

    def _variant_terms(self, value: Any) -> list[str]:
        normalized = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold())
        stop_words = {"a", "an", "and", "by", "cover", "edition", "of", "the"}
        return [term for term in normalized.split() if len(term) > 1 and term not in stop_words]

    def _normalized_cover_image_url(
        self,
        data: Mapping[str, Any],
        *,
        issue_id: str | None,
        series_title: str,
        issue_number: str | None,
        start_year: int | None,
        variant_hint: str | None,
    ) -> str | None:
        cover_url = self._optional_text(data.get("cover"))
        if cover_url is None and data.get("variant_of"):
            return None
        return (
            self._cover_proxy_url(
                issue_id,
                series_title=series_title,
                issue_number=issue_number,
                start_year=start_year,
                variant_hint=variant_hint,
            )
            or cover_url
        )

    def _cover_proxy_url(
        self,
        issue_id: str | None,
        *,
        series_title: str | None = None,
        issue_number: str | None = None,
        start_year: int | None = None,
        variant_hint: str | None = None,
    ) -> str | None:
        if issue_id is None:
            return None
        query = urlencode(
            {
                key: value
                for key, value in {
                    "series": series_title,
                    "issue": issue_number,
                    "year": start_year,
                    "variant": variant_hint,
                }.items()
                if value
            }
        )
        path = f"/metadata/providers/gcd/images/{quote(issue_id, safe='')}"
        return f"{path}?{query}" if query else path

    def _series_rank(
        self,
        result: Mapping[str, Any],
        query: str,
        *,
        year_hint: int | None = None,
    ) -> tuple[int, int, str]:
        series_name = self._optional_text(result.get("series_name")) or ""
        start_year = self._series_start_year(series_name)
        year_rank = 0 if year_hint is None or start_year == year_hint else 1
        series_key = self._normalized_title_key(self._series_title(series_name))
        query_key = self._normalized_title_key(query)
        if series_key == query_key:
            rank = 0
        elif series_key.removeprefix("the ") == query_key.removeprefix("the "):
            rank = 1
        elif series_key.startswith(f"{query_key} "):
            rank = 2
        elif series_key.endswith(f" {query_key}"):
            rank = 3
        else:
            rank = 4
        return year_rank, rank, series_key

    def _normalized_title_key(self, value: str) -> str:
        return normalize_title(value)

    def _parse_issue_query(self, query: str) -> tuple[str, str] | None:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            return None
        match = _ISSUE_QUERY_RE.match(normalized_query)
        if not match:
            return None
        series = match.group("series").strip()
        issue = match.group("issue").strip()
        if not series or not issue:
            return None
        if not any(char.isalpha() for char in series):
            return None
        return series, issue

    def _query_candidates(self, query: str) -> list[tuple[str, str]]:
        return self._query_plan(query).candidates

    def _query_plan(self, query: str) -> GCDQueryPlan:
        normalized_query = self._searchable_query(query)
        if not normalized_query:
            return GCDQueryPlan([])
        if not any(char.isalpha() for char in normalized_query):
            return GCDQueryPlan([])

        year_hint, normalized_query = self._extract_year_hint(normalized_query)
        if not normalized_query or not any(char.isalpha() for char in normalized_query):
            return GCDQueryPlan([])

        parsed = self._parse_issue_query(normalized_query)
        if parsed is None:
            series_name = normalized_query
            issue_numbers = [
                str(issue) for issue in range(1, self.settings.gcd_series_search_issue_span + 1)
            ]
            is_series_search = True
        else:
            series_name, issue_number = parsed
            issue_numbers = [issue_number]
            is_series_search = False

        candidates: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for issue_number in issue_numbers:
            for series_candidate in self._series_aliases(series_name):
                key = (series_candidate.casefold(), issue_number.casefold())
                if key in seen:
                    continue
                seen.add(key)
                candidates.append((series_candidate, issue_number))
        return GCDQueryPlan(
            candidates,
            year_hint=year_hint,
            is_series_search=is_series_search,
        )

    def _extract_year_hint(self, query: str) -> tuple[int | None, str]:
        matches = list(_YEAR_HINT_RE.finditer(query))
        if not matches:
            return None, query
        match = matches[-1]
        prefix = query[: match.start()]
        if re.search(r"(#|issue\s+|no\.?\s*)$", prefix, re.IGNORECASE):
            return None, query
        year = int(match.group("year"))
        without_year = f"{query[: match.start()]} {query[match.end() :]}".strip()
        return year, " ".join(without_year.split())

    def _searchable_query(self, query: str) -> str:
        normalized_query = " ".join(query.split())
        previous = None
        while previous != normalized_query:
            previous = normalized_query
            normalized_query = _TRAILING_VARIANT_HINT_RE.sub("", normalized_query).strip()
        return normalized_query

    def _series_aliases(self, series_name: str) -> list[str]:
        return title_aliases(series_name)

    def _issue_id(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if text.isdigit():
            return text
        match = _ISSUE_ID_RE.search(text)
        return match.group(1) if match else None

    def _series_id(self, value: Any) -> str | None:
        if value is None:
            return None
        match = _SERIES_ID_RE.search(str(value))
        return match.group(1) if match else None

    def _series_title(self, value: str) -> str:
        title = _SERIES_YEAR_RE.sub("", value).strip()
        return title or value

    def _series_start_year(self, value: str) -> int | None:
        match = _SERIES_YEAR_RE.search(value)
        if not match:
            return None
        try:
            return int(match.group("year"))
        except ValueError:
            return None

    def _first_result_start_year(self, results: list[Mapping[str, Any]]) -> int | None:
        for result in results:
            series_name = self._optional_text(result.get("series_name")) or ""
            start_year = self._series_start_year(series_name)
            if start_year is not None:
                return start_year
        return None

    def _descriptor_number(self, data: Mapping[str, Any]) -> str | None:
        descriptor = self._optional_text(data.get("descriptor"))
        if descriptor is None:
            return None
        return descriptor.split("[", 1)[0].split("-", 1)[0].strip() or descriptor

    def _variant_name_from_descriptor(self, data: Mapping[str, Any]) -> str | None:
        descriptor = self._optional_text(data.get("descriptor"))
        if not descriptor or "[" not in descriptor or "]" not in descriptor:
            return None
        return descriptor.split("[", 1)[1].split("]", 1)[0].strip() or None

    def _synopsis(self, data: Mapping[str, Any]) -> str | None:
        story_set = data.get("story_set")
        if isinstance(story_set, list):
            for story in story_set:
                if not isinstance(story, Mapping):
                    continue
                if story.get("type") != "comic story":
                    continue
                synopsis = self._optional_text(story.get("synopsis"))
                if synopsis:
                    return synopsis
        return self._optional_text(data.get("notes"))

    def _publisher(self, data: Mapping[str, Any]) -> str | None:
        return (
            self._optional_text(data.get("indicia_publisher"))
            or self._optional_text(data.get("publisher"))
            or self._optional_text(data.get("publisher_name"))
        )

    def _publisher_and_imprint(
        self, data: Mapping[str, Any]
    ) -> tuple[str | None, str | None]:
        """Return ``(publisher, imprint)`` from GCD issue data.

        GCD exposes ``indicia_publisher`` (often the imprint label printed
        inside the comic) and ``publisher`` / ``publisher_name`` (the parent
        company).  When they differ the indicia value is treated as an imprint.
        """
        indicia = self._optional_text(data.get("indicia_publisher"))
        parent = (
            self._optional_text(data.get("publisher"))
            or self._optional_text(data.get("publisher_name"))
        )
        publisher = indicia or parent
        imprint: str | None = None
        if indicia and parent and indicia.casefold() != parent.casefold():
            imprint = indicia
            publisher = parent
        return publisher, imprint

    def _credits(self, story_set: Any, *, issue_editing: Any = None) -> list[NormalizedCredit]:
        credits: list[NormalizedCredit] = []
        seen: set[tuple[str, str]] = set()
        canonical_editing = canonical_credit_role("editing") or "editor"
        for name in self._split_credit_names(issue_editing, role="editing"):
            seen.add((name.casefold(), canonical_editing))
            credits.append(NormalizedCredit(name=name, role=canonical_editing))
        if not isinstance(story_set, list):
            return credits
        for story in story_set:
            if not isinstance(story, Mapping):
                continue
            for field, role in (
                ("script", "script"),
                ("pencils", "pencils"),
                ("inks", "inks"),
                ("colors", "colors"),
                ("letters", "letters"),
                ("editing", "editing"),
            ):
                canonical_role = canonical_credit_role(role) or role
                for name in self._split_credit_names(story.get(field), role=role):
                    key = (name.casefold(), canonical_role)
                    if key in seen:
                        continue
                    seen.add(key)
                    credits.append(NormalizedCredit(name=name, role=canonical_role))
        return credits

    def _characters(self, story_set: Any) -> list[NormalizedCredit]:
        if not isinstance(story_set, list):
            return []
        characters: list[NormalizedCredit] = []
        seen: set[str] = set()
        for story in story_set:
            if not isinstance(story, Mapping):
                continue
            for name in self._split_credit_names(story.get("characters")):
                key = name.casefold()
                if key in seen:
                    continue
                seen.add(key)
                characters.append(NormalizedCredit(name=name))
        return characters

    def _story_arcs(self, story_set: Any) -> list[NormalizedCredit]:
        if not isinstance(story_set, list):
            return []
        arcs: list[NormalizedCredit] = []
        seen: set[str] = set()
        for story in story_set:
            if not isinstance(story, Mapping):
                continue
            if story.get("type") != "comic story":
                continue
            title = self._optional_text(story.get("title"))
            if title is None:
                continue
            key = title.casefold()
            if key in seen:
                continue
            seen.add(key)
            arcs.append(NormalizedCredit(name=title))
        return arcs

    def _preview_names(self, credits: list[NormalizedCredit]) -> list[str]:
        return preview_names(credits)

    def _split_credit_names(self, value: Any, *, role: str | None = None) -> list[str]:
        text = self._optional_text(value)
        if text is None:
            return []
        names: list[str] = []
        for part in text.split(";"):
            name = part.strip()
            if name.casefold() in _EMPTY_CREDIT_VALUES:
                continue
            if role == "editing":
                name = _EDITOR_SUFFIX_RE.sub("", name).strip()
            names.append(name)
        return names

    def _page_summary(self, value: Any) -> str | None:
        count = self._int_decimal(value)
        return f"{count} pages" if count else None

    def _int_decimal(self, value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(Decimal(str(value)))
        except (InvalidOperation, ValueError):
            return None

    def _price(self, value: Any) -> tuple[int | None, str | None]:
        text = self._optional_text(value)
        if text is None:
            return None, None
        match = _PRICE_RE.search(text.replace(",", "."))
        if not match:
            return None, None
        try:
            cents = int(Decimal(match.group("amount")) * 100)
        except InvalidOperation:
            return None, None
        return cents, match.group("currency")

    def _date(self, value: Any) -> date | None:
        text = self._optional_text(value)
        if text is None:
            return None
        parts = text[:10].split("-")
        if len(parts) != 3 or "00" in parts:
            return None
        try:
            return date.fromisoformat("-".join(parts))
        except ValueError:
            return None

    def _optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
