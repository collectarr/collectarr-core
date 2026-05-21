import re
from datetime import date
from typing import Any, Mapping

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


_OLID_RE = re.compile(r"^(?P<id>OL\d+[MWA])$", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(?P<year>\d{4})\b")


class OpenLibraryProvider:
    name = "openlibrary"
    capabilities = ProviderCapabilities(
        kind=ItemKind.book,
        display_name="Open Library",
        supports_search=True,
        supports_ingest=True,
        requires_user_key=False,
        non_commercial_only=False,
        allows_redistribution=True,
        requires_attribution=True,
        license_name="Open Library Data",
        terms_url="https://openlibrary.org/developers",
        attribution_url="https://openlibrary.org/",
        cache_policy=(
            "Cache bibliographic metadata with attribution. Prefer Open Library cover URLs "
            "for public covers; do not crawl the cover API."
        ),
    )

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def is_configured(self) -> bool:
        return True

    @property
    def status_message(self) -> str:
        return "Open Library metadata is available without an API key."

    async def search(
        self,
        query: str,
        kind: ItemKind | None = None,
    ) -> list[ProviderSearchResult]:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            return []

        payload = await self._request(
            "search.json",
            {
                "q": normalized_query,
                "limit": self.settings.openlibrary_search_limit,
                "fields": ",".join(
                    [
                        "key",
                        "title",
                        "author_name",
                        "first_publish_year",
                        "edition_key",
                        "isbn",
                        "publisher",
                        "cover_i",
                    ]
                ),
            },
        )
        docs = payload.get("docs") or []
        if not isinstance(docs, list):
            return []

        results: list[ProviderSearchResult] = []
        for doc in docs[: self.settings.openlibrary_search_limit]:
            if not isinstance(doc, Mapping):
                continue
            result = self._search_result(doc)
            if result.provider_item_id:
                results.append(result)
        return results

    async def search_by_barcode(
        self,
        barcode: str,
        kind: ItemKind | None = None,
    ) -> list[ProviderSearchResult]:
        normalized = barcode.strip().replace("-", "")
        if not normalized:
            return []
        return await self.search(f"isbn:{normalized}", kind)

    async def get_item(self, provider_item_id: str) -> ProviderItem:
        provider_id = self._provider_id(provider_item_id)
        if provider_id is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="openlibrary_invalid_id",
                detail="Invalid Open Library id",
            )

        if provider_id.upper().startswith("ISBN:"):
            edition = await self._request(f"isbn/{provider_id[5:]}.json")
        elif provider_id.upper().endswith("M"):
            edition = await self._request(f"books/{provider_id}.json")
        else:
            work = await self._request(f"works/{provider_id}.json")
            return ProviderItem(
                provider=self.name,
                provider_item_id=provider_id,
                raw={"work": work, "edition": None},
            )

        work = None
        work_id = self._work_id_from_edition(edition)
        if work_id is not None:
            work = await self._request(f"works/{work_id}.json")
        return ProviderItem(
            provider=self.name,
            provider_item_id=self._edition_id(edition) or provider_id,
            raw={"work": work, "edition": edition},
        )

    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem:
        edition = data.get("edition") if isinstance(data.get("edition"), Mapping) else None
        work = data.get("work") if isinstance(data.get("work"), Mapping) else None
        search_doc = data if edition is None and work is None else None

        title = (
            self._optional_text((edition or {}).get("title"))
            or self._optional_text((work or {}).get("title"))
            or self._optional_text((search_doc or {}).get("title"))
            or "Unknown book"
        )
        isbn = self._first_text(
            (edition or {}).get("isbn_13"),
            (edition or {}).get("isbn_10"),
            (search_doc or {}).get("isbn"),
        )
        work_id = self._work_id_from_edition(edition or {}) or self._work_id(work)
        edition_id = self._edition_id(edition or {}) or self._edition_key(search_doc or {})
        provider_item_id = edition_id or work_id
        publication_date = self._date(
            (edition or {}).get("publish_date") or (search_doc or {}).get("first_publish_year")
        )

        subjects = (work or {}).get("subjects")
        ol_genres = [str(s) for s in subjects if isinstance(s, str)][:20] if isinstance(subjects, list) else []

        ol_langs = (edition or {}).get("languages")
        ol_language = None
        if isinstance(ol_langs, list) and ol_langs:
            lang_key = ol_langs[0].get("key", "") if isinstance(ol_langs[0], Mapping) else str(ol_langs[0])
            ol_language = lang_key.rsplit("/", 1)[-1] if "/" in lang_key else lang_key or None

        ol_subtitle = self._optional_text((edition or {}).get("subtitle"))

        ol_series_list = (edition or {}).get("series") or (work or {}).get("series")
        ol_series_group = None
        if isinstance(ol_series_list, list) and ol_series_list:
            ol_series_group = str(ol_series_list[0]) if not isinstance(ol_series_list[0], Mapping) else ol_series_list[0].get("name")

        return NormalizedItem(
            kind=ItemKind.book,
            title=title,
            synopsis=self._description((edition or {}).get("description"))
            or self._description((work or {}).get("description")),
            series_title=None,
            volume_name=title,
            volume_start_year=publication_date.year if publication_date else None,
            page_count=self._int((edition or {}).get("number_of_pages")),
            edition_title=title,
            edition_format=self._optional_text((edition or {}).get("physical_format")) or "Book",
            publisher=self._first_text(
                (edition or {}).get("publishers"),
                (search_doc or {}).get("publisher"),
            ),
            release_date=publication_date,
            isbn=isbn,
            barcode=isbn,
            cover_image_url=self._cover_url(edition or search_doc or {}, isbn),
            creators=self._authors(search_doc or {}),
            genres=ol_genres,
            language=ol_language,
            subtitle=ol_subtitle,
            series_group=ol_series_group,
            provider_ids={self.name: provider_item_id} if provider_item_id else {},
            volume_provider_ids={self.name: work_id} if work_id else {},
        )

    async def _request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.settings.openlibrary_base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.openlibrary_timeout_seconds,
                headers={
                    "User-Agent": self.settings.openlibrary_user_agent,
                    "Accept": "application/json",
                },
                follow_redirects=True,
            ) as client:
                response = await client.get(url, params=params or {})
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="openlibrary_http_error",
                detail=f"Open Library returned HTTP {exc.response.status_code}",
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="openlibrary_request_failed",
                detail="Open Library request failed",
            ) from exc
        if not isinstance(payload, dict):
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="openlibrary_invalid_response",
                detail="Invalid Open Library response",
            )
        return payload

    def _search_result(self, doc: Mapping[str, Any]) -> ProviderSearchResult:
        title = self._optional_text(doc.get("title")) or "Unknown Open Library book"
        provider_item_id = self._edition_key(doc) or self._work_id(doc) or ""
        authors = self._text_list(doc.get("author_name"))
        publishers = self._text_list(doc.get("publisher"))
        summary_parts = [
            ", ".join(authors[:2]) if authors else None,
            self._optional_text(doc.get("first_publish_year")),
            publishers[0] if publishers else None,
        ]
        return ProviderSearchResult(
            provider=self.name,
            provider_item_id=provider_item_id,
            title=title,
            kind=ItemKind.book,
            summary=" · ".join(part for part in summary_parts if part),
            image_url=self._cover_url(doc),
        )

    def _provider_id(self, value: Any) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        text = text.removeprefix("/books/").removeprefix("/works/").removeprefix("/isbn/")
        if text.upper().startswith("ISBN:"):
            return f"ISBN:{text[5:].strip()}"
        if text.isdigit() or (len(text) == 10 and text[-1].upper() == "X"):
            return f"ISBN:{text}"
        match = _OLID_RE.fullmatch(text)
        return match.group("id") if match else None

    def _edition_key(self, data: Mapping[str, Any]) -> str | None:
        edition_keys = data.get("edition_key")
        edition_id = self._first_text(edition_keys)
        if edition_id:
            return self._provider_id(edition_id)
        return self._edition_id(data)

    def _edition_id(self, data: Mapping[str, Any]) -> str | None:
        return self._provider_id(data.get("key") or data.get("ocaid")) if data else None

    def _work_id(self, data: Mapping[str, Any] | None) -> str | None:
        if not data:
            return None
        return self._provider_id(data.get("key"))

    def _work_id_from_edition(self, data: Mapping[str, Any]) -> str | None:
        works = data.get("works")
        if not isinstance(works, list) or not works:
            return None
        first = works[0]
        if isinstance(first, Mapping):
            return self._provider_id(first.get("key"))
        return None

    def _cover_url(self, data: Mapping[str, Any], isbn: str | None = None) -> str | None:
        cover_id = self._first_text(data.get("covers"), data.get("cover_i"))
        if cover_id:
            return f"{self.settings.openlibrary_covers_url.rstrip('/')}/b/id/{cover_id}-L.jpg"
        if isbn:
            return f"{self.settings.openlibrary_covers_url.rstrip('/')}/b/isbn/{isbn}-L.jpg"
        return None

    def _authors(self, data: Mapping[str, Any]) -> list[NormalizedCredit]:
        return [NormalizedCredit(name=name, role="Author") for name in self._text_list(data.get("author_name"))]

    def _description(self, value: Any) -> str | None:
        if isinstance(value, Mapping):
            return self._optional_text(value.get("value"))
        return self._optional_text(value)

    def _date(self, value: Any) -> date | None:
        if isinstance(value, int) and 0 < value < 10000:
            return date(value, 1, 1)
        text = self._optional_text(value)
        if not text:
            return None
        match = _YEAR_RE.search(text)
        if not match:
            return None
        return date(int(match.group("year")), 1, 1)

    def _int(self, value: Any) -> int | None:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    def _first_text(self, *values: Any) -> str | None:
        for value in values:
            if isinstance(value, list):
                for item in value:
                    text = self._optional_text(item)
                    if text:
                        return text
            else:
                text = self._optional_text(value)
                if text:
                    return text
        return None

    def _text_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [text for item in value if (text := self._optional_text(item))]
        text = self._optional_text(value)
        return [text] if text else []

    def _optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
