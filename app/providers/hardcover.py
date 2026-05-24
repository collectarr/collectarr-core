import json
from datetime import date
from typing import Any, ClassVar, Mapping

import httpx
from fastapi import status

from app.core.config import get_settings
from app.core.errors import ApiHTTPException
from app.models.base import ItemKind
from app.providers.base import (
    NormalizedCredit,
    NormalizedEpisode,
    NormalizedItem,
    NormalizedSeason,
    ProviderCapabilities,
    ProviderItem,
    ProviderSearchResult,
)

_SEARCH_QUERY = """
query SearchManga($query: String!, $perPage: Int!, $page: Int!) {
  search(
    query: $query,
    query_type: "Book",
    per_page: $perPage,
    page: $page,
    fields: "title,isbns,series_names,author_names,alternative_titles",
    sort: "_text_match:desc,users_count:desc"
  ) {
    results
  }
}
"""

_BOOK_DETAIL_QUERY = """
query GetBook($id: Int!) {
  books(where: {id: {_eq: $id}}) {
    id
    title
    subtitle
    slug
    description
    pages
    release_date
    contributions {
      author {
        name
                image {
                    url
                }
      }
      contribution_type
    }
    book_series {
      series {
        id
        name
        slug
      }
      position
    }
    editions(
      where: {is_default: {_eq: true}}
      limit: 1
    ) {
      isbn_10
      isbn_13
      pages
      release_date
      edition_format
      image {
        url
      }
      publisher {
        name
      }
    }
    image {
      url
    }
    taggings {
      tag {
        tag
      }
    }
  }
}
"""

_SERIES_VOLUMES_QUERY = """
query GetSeriesVolumes($seriesId: Int!) {
  series(where: {id: {_eq: $seriesId}}) {
    id
    name
    book_series(
      distinct_on: position
      order_by: [{position: asc}, {book: {users_count: desc}}]
      where: {
        book: {canonical_id: {_is_null: true}, is_partial_book: {_eq: false}},
        compilation: {_eq: false}
      }
    ) {
      position
      book {
        id
        title
        slug
        pages
        release_date
        description
        image {
          url
        }
        editions(where: {is_default: {_eq: true}}, limit: 1) {
          isbn_13
          pages
          release_date
          edition_format
          publisher {
            name
          }
        }
      }
    }
  }
}
"""


class HardcoverProvider:
    _shared_client: ClassVar[httpx.AsyncClient | None] = None

    name = "hardcover"
    capabilities = ProviderCapabilities(
        kind=ItemKind.manga,
        kinds=(ItemKind.manga, ItemKind.book),
        display_name="Hardcover",
        supports_search=True,
        supports_ingest=True,
        requires_user_key=True,
        non_commercial_only=False,
        allows_redistribution=False,
        requires_attribution=True,
        license_name="Hardcover API Terms",
        terms_url="https://docs.hardcover.app/api/getting-started/",
        attribution_url="https://hardcover.app/",
        rate_limit="60 req/min",
        cache_policy="Cache book/series details; search results are ephemeral.",
    )

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.hardcover_api_key)

    @property
    def status_message(self) -> str:
        if self.is_configured:
            return "Hardcover API key is configured."
        return "Hardcover requires an API key. Get one at https://hardcover.app/account/api"

    def _get_client(self) -> httpx.AsyncClient:
        if HardcoverProvider._shared_client is None:
            HardcoverProvider._shared_client = httpx.AsyncClient(
                timeout=self.settings.hardcover_timeout_seconds,
                follow_redirects=True,
            )
        return HardcoverProvider._shared_client

    async def aclose(self) -> None:
        if HardcoverProvider._shared_client is not None:
            await HardcoverProvider._shared_client.aclose()
            HardcoverProvider._shared_client = None

    async def search(
        self,
        query: str,
        kind: ItemKind | None = None,
    ) -> list[ProviderSearchResult]:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            return []
        data = await self._graphql(
            _SEARCH_QUERY,
            {
                "query": normalized_query,
                "perPage": self.settings.hardcover_search_limit,
                "page": 1,
            },
        )
        search_data = data.get("data") or {}
        search_result = search_data.get("search") or {}
        raw_results = search_result.get("results")
        if not raw_results:
            return []
        if isinstance(raw_results, str):
            try:
                results_list = json.loads(raw_results)
            except (json.JSONDecodeError, TypeError):
                return []
        elif isinstance(raw_results, list):
            results_list = raw_results
        else:
            return []

        hits: list[ProviderSearchResult] = []
        for hit in results_list:
            if not isinstance(hit, Mapping):
                continue
            doc = hit.get("document") or hit
            book_id = doc.get("id")
            title = doc.get("title") or "Unknown"
            if book_id is None:
                continue
            author_names = doc.get("author_names") or []
            series = doc.get("featured_series") or {}
            series_name = series.get("name") if isinstance(series, Mapping) else None
            summary_parts = [
                ", ".join(author_names[:2]) if author_names else None,
                series_name,
                str(doc["release_year"]) if doc.get("release_year") else None,
            ]
            image = doc.get("image") or {}
            image_url = image.get("url") if isinstance(image, Mapping) else None
            result_kind = kind or ItemKind.manga
            hits.append(
                ProviderSearchResult(
                    provider=self.name,
                    provider_item_id=self._provider_item_id(book_id, result_kind),
                    title=title,
                    kind=result_kind,
                    summary=" · ".join(p for p in summary_parts if p),
                    image_url=image_url,
                    series_title=series_name,
                )
            )
        return hits

    async def get_item(self, provider_item_id: str) -> ProviderItem:
        normalized_kind, book_id = self._parse_provider_item_id(provider_item_id)
        if not book_id:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="hardcover_invalid_id",
                detail="Invalid Hardcover book id",
            )
        try:
            int_id = int(book_id)
        except ValueError:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="hardcover_invalid_id",
                detail="Hardcover book id must be an integer",
            )
        data = await self._graphql(_BOOK_DETAIL_QUERY, {"id": int_id})
        books = (data.get("data") or {}).get("books") or []
        if not books:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="hardcover_not_found",
                detail="Hardcover book not found",
            )
        return ProviderItem(
            provider=self.name,
            provider_item_id=provider_item_id.strip(),
            raw={**dict(books[0]), "_collectarr_kind": normalized_kind.value},
        )

    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem:
        title = data.get("title") or "Unknown"
        book_id = data.get("id")
        description = data.get("description")

        contributions = data.get("contributions") or []
        creators = self._creators(contributions)
        genres = self._tags(data.get("taggings"))

        release_date = self._parse_date(data.get("release_date"))

        image = data.get("image") or {}
        cover_url = image.get("url") if isinstance(image, Mapping) else None

        editions = data.get("editions") or []
        default_edition = editions[0] if editions else {}

        isbn = None
        publisher = None
        page_count = data.get("pages")
        edition_format = None
        if isinstance(default_edition, Mapping):
            isbn = default_edition.get("isbn_13") or default_edition.get("isbn_10")
            pub = default_edition.get("publisher") or {}
            publisher = pub.get("name") if isinstance(pub, Mapping) else None
            page_count = page_count or default_edition.get("pages")
            edition_format = default_edition.get("edition_format")
            ed_image = default_edition.get("image") or {}
            if not cover_url and isinstance(ed_image, Mapping):
                cover_url = ed_image.get("url")

        series_title = None
        volume_number = None
        book_series = data.get("book_series") or []
        if book_series and isinstance(book_series[0], Mapping):
            bs = book_series[0]
            series = bs.get("series") or {}
            if isinstance(series, Mapping):
                series_title = series.get("name")
            pos = bs.get("position")
            if pos is not None:
                try:
                    volume_number = int(float(pos))
                except (ValueError, TypeError):
                    pass

        normalized_kind = self._normalized_kind(data.get("_collectarr_kind"))
        provider_id = self._provider_item_id(book_id, normalized_kind) if book_id else None
        provider_ids = {self.name: provider_id} if provider_id else {}

        return NormalizedItem(
            kind=normalized_kind,
            title=title,
            synopsis=description,
            series_title=series_title,
            volume_name=title,
            volume_number=volume_number,
            volume_start_year=release_date.year if release_date else None,
            edition_title=title,
            edition_format=edition_format or self._default_format(normalized_kind),
            page_count=page_count,
            publisher=publisher,
            release_date=release_date,
            isbn=isbn,
            cover_image_url=cover_url,
            creators=creators,
            genres=genres,
            subtitle=data.get("subtitle") or None,
            provider_ids=provider_ids,
            volume_provider_ids=provider_ids,
        )

    async def get_volumes(self, provider_item_id: str) -> list[NormalizedSeason]:
        """Fetch all books in a series from Hardcover.

        provider_item_id can be:
        - "series:<id>"  → fetch books for that series directly
        - "<book_id>"    → look up the book's series, then fetch all books in it
        """
        series_id: int | None = None

        if provider_item_id.startswith("series:"):
            try:
                series_id = int(provider_item_id.split(":", 1)[1])
            except ValueError:
                return []
        else:
            try:
                normalized_kind, raw_book_id = self._parse_provider_item_id(
                    provider_item_id
                )
                book_id = int(raw_book_id)
            except ValueError:
                return []
            item = await self.get_item(
                self._provider_item_id(book_id, normalized_kind)
            )
            book_series = item.raw.get("book_series") or []
            if not book_series:
                return []
            first_bs = book_series[0] if isinstance(book_series[0], Mapping) else {}
            series = first_bs.get("series") or {}
            if isinstance(series, Mapping):
                series_id = series.get("id")
            if series_id is None:
                return []

        data = await self._graphql(_SERIES_VOLUMES_QUERY, {"seriesId": series_id})
        series_list = (data.get("data") or {}).get("series") or []
        if not series_list:
            return []

        book_entries = series_list[0].get("book_series") or []

        episodes: list[NormalizedEpisode] = []
        for entry in book_entries:
            if not isinstance(entry, Mapping):
                continue
            book = entry.get("book") or {}
            if not isinstance(book, Mapping):
                continue
            position = entry.get("position")
            if position is None:
                continue
            try:
                vol_num = int(float(position))
            except (ValueError, TypeError):
                continue

            book_title = book.get("title") or f"Volume {vol_num}"
            release = self._parse_date(book.get("release_date"))
            pages = book.get("pages")
            editions = book.get("editions") or []
            if not pages and editions:
                ed = editions[0]
                if isinstance(ed, Mapping):
                    pages = ed.get("pages")

            episodes.append(
                NormalizedEpisode(
                    episode_number=vol_num,
                    title=book_title,
                    overview=book.get("description"),
                    air_date=release,
                    page_count=pages,
                    still_url=self._book_image(book),
                )
            )

        if not episodes:
            return []

        series_name = series_list[0].get("name") or "Volumes"
        return [
            NormalizedSeason(
                season_number=1,
                title=series_name,
                overview=None,
                air_date=episodes[0].air_date if episodes else None,
                episode_count=len(episodes),
                poster_url=None,
                episodes=episodes,
            )
        ]

    def _parse_provider_item_id(self, provider_item_id: str) -> tuple[ItemKind, str]:
        raw = provider_item_id.strip()
        if not raw:
            return ItemKind.manga, ""
        prefix, separator, suffix = raw.partition(":")
        if separator and prefix in {ItemKind.book.value, ItemKind.manga.value}:
            return self._normalized_kind(prefix), suffix.strip()
        return ItemKind.manga, raw

    def _normalized_kind(self, value: Any) -> ItemKind:
        normalized = str(value or "").strip().lower()
        if normalized == ItemKind.book.value:
            return ItemKind.book
        return ItemKind.manga

    def _provider_item_id(self, book_id: Any, kind: ItemKind) -> str:
        return f"{kind.value}:{book_id}"

    def _default_format(self, kind: ItemKind) -> str:
        return "Book" if kind == ItemKind.book else "Manga"

    async def _graphql(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = self.settings.hardcover_graphql_url
        headers = {
            "authorization": self.settings.hardcover_api_key or "",
            "Content-Type": "application/json",
            "User-Agent": self.settings.hardcover_user_agent,
        }
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        try:
            response = await self._get_client().post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            if "errors" in result:
                errors = result["errors"]
                msg = errors[0].get("message", "Unknown") if errors else "Unknown"
                raise ApiHTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    code="hardcover_graphql_error",
                    detail=f"Hardcover GraphQL error: {msg}",
                )
            return result
        except httpx.HTTPStatusError as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="hardcover_http_error",
                detail=f"Hardcover returned HTTP {exc.response.status_code}",
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="hardcover_request_failed",
                detail="Hardcover request failed",
            ) from exc

    def _creators(self, contributions: Any) -> list[NormalizedCredit]:
        if not isinstance(contributions, list):
            return []
        credits: list[NormalizedCredit] = []
        for c in contributions:
            if not isinstance(c, Mapping):
                continue
            author = c.get("author") or {}
            name = author.get("name") if isinstance(author, Mapping) else None
            if name:
                role = c.get("contribution_type") or "Author"
                image_url = None
                if isinstance(author, Mapping):
                    image = author.get("image") or {}
                    if isinstance(image, Mapping) and image.get("url"):
                        image_url = str(image.get("url"))
                credits.append(
                    NormalizedCredit(
                        name=name,
                        role=role,
                        image_url=image_url,
                    )
                )
        return credits

    def _tags(self, taggings: Any) -> list[str]:
        if not isinstance(taggings, list):
            return []
        tags: list[str] = []
        for t in taggings:
            if not isinstance(t, Mapping):
                continue
            tag = t.get("tag") or {}
            name = tag.get("tag") if isinstance(tag, Mapping) else None
            if name:
                tags.append(name)
        return tags

    def _book_image(self, book: Mapping[str, Any]) -> str | None:
        image = book.get("image") or {}
        if isinstance(image, Mapping):
            return image.get("url")
        return None

    def _parse_date(self, value: Any) -> date | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None
