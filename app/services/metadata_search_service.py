from __future__ import annotations

from uuid import UUID

from fastapi import status

from app.core.errors import ApiHTTPException
from app.models import (
    AnimeSeries,
    BoardGameWork,
    BookWork,
    ComicWork,
    GameWork,
    MangaWork,
    MovieWork,
    MusicRelease,
    TVRelease,
)
from app.models.base import ItemKind
from app.schemas.metadata_shared import SearchResult, public_item_kind


class MetadataSearchService:
    def __init__(self, service) -> None:
        self.service = service

    async def search(
        self,
        query: str | None = None,
        kind: ItemKind | None = None,
        series: str | None = None,
        issue_number: str | None = None,
        publisher: str | None = None,
        imprint: str | None = None,
        subtitle: str | None = None,
        series_group: str | None = None,
        language: str | None = None,
        country: str | None = None,
        age_rating: str | None = None,
        catalog_number: str | None = None,
        release_status: str | None = None,
        year: int | None = None,
        barcode: str | None = None,
        limit: int = 25,
    ) -> list[SearchResult]:
        if not any(
            value is not None and str(value).strip()
            for value in (
                query,
                series,
                issue_number,
                publisher,
                imprint,
                subtitle,
                series_group,
                language,
                country,
                age_rating,
                catalog_number,
                release_status,
                year,
                barcode,
            )
        ):
            return []

        meili_results = await self.service.search_client.search(
            query=query or "",
            kind=kind,
            series=series,
            issue_number=issue_number,
            publisher=publisher,
            imprint=imprint,
            subtitle=subtitle,
            series_group=series_group,
            language=language,
            country=country,
            age_rating=age_rating,
            catalog_number=catalog_number,
            release_status=release_status,
            year=year,
            barcode=barcode,
            limit=limit,
        )
        if meili_results is not None and not barcode:
            return [
                SearchResult(**{**result, "kind": public_item_kind(result.get("kind"))})
                for result in meili_results
            ]
        if kind == ItemKind.comic:
            comic_results = await self.service._search_comic_works(
                query=query,
                series=series,
                issue_number=issue_number,
                publisher=publisher,
                imprint=imprint,
                language=language,
                country=country,
                release_status=release_status,
                year=year,
                barcode=barcode,
                limit=limit,
            )
            if comic_results:
                return comic_results
        if kind == ItemKind.book:
            book_results = await self.service._search_book_works(
                query=query,
                series=series,
                publisher=publisher,
                imprint=imprint,
                subtitle=subtitle,
                language=language,
                country=country,
                age_rating=age_rating,
                catalog_number=catalog_number,
                release_status=release_status,
                year=year,
                barcode=barcode,
                limit=limit,
            )
            if book_results:
                return book_results
        if kind == ItemKind.movie:
            movie_results = await self.service._search_movie_works(
                query=query,
                publisher=publisher,
                subtitle=subtitle,
                language=language,
                country=country,
                age_rating=age_rating,
                catalog_number=catalog_number,
                release_status=release_status,
                year=year,
                barcode=barcode,
                limit=limit,
            )
            if movie_results:
                return movie_results
        if kind == ItemKind.tv:
            tv_results = await self.service._search_tv_releases(
                query=query,
                publisher=publisher,
                subtitle=subtitle,
                language=language,
                country=country,
                age_rating=age_rating,
                catalog_number=catalog_number,
                release_status=release_status,
                year=year,
                barcode=barcode,
                limit=limit,
            )
            if tv_results:
                return tv_results
        if kind == ItemKind.anime:
            anime_results = await self.service._search_anime_series(
                query=query,
                language=language,
                country=country,
                release_status=release_status,
                year=year,
                barcode=barcode,
                limit=limit,
            )
            if anime_results:
                return anime_results
        if kind == ItemKind.music:
            music_results = await self.service._search_music_releases(
                query=query,
                publisher=publisher,
                subtitle=subtitle,
                language=language,
                country=country,
                release_status=release_status,
                year=year,
                barcode=barcode,
                catalog_number=catalog_number,
                limit=limit,
            )
            if music_results:
                return music_results
        if kind == ItemKind.boardgame:
            boardgame_results = await self.service._search_boardgame_works(
                query=query,
                publisher=publisher,
                subtitle=subtitle,
                language=language,
                country=country,
                age_rating=age_rating,
                catalog_number=catalog_number,
                release_status=release_status,
                year=year,
                barcode=barcode,
                limit=limit,
            )
            if boardgame_results:
                return boardgame_results
        if kind == ItemKind.game:
            game_results = await self.service._search_game_works(
                query=query,
                publisher=publisher,
                subtitle=subtitle,
                language=language,
                country=country,
                age_rating=age_rating,
                catalog_number=catalog_number,
                release_status=release_status,
                year=year,
                barcode=barcode,
                limit=limit,
            )
            if game_results:
                return game_results
        if kind == ItemKind.manga:
            manga_results = await self.service._search_manga_works(
                query=query,
                language=language,
                country=country,
                release_status=release_status,
                year=year,
                barcode=barcode,
                limit=limit,
            )
            if manga_results:
                return manga_results
        if kind is None:
            results: list[SearchResult] = []
            for batch in (
                await self.service._search_comic_works(
                    query=query,
                    series=series,
                    issue_number=issue_number,
                    publisher=publisher,
                    imprint=imprint,
                    language=language,
                    country=country,
                    release_status=release_status,
                    year=year,
                    barcode=barcode,
                    limit=limit,
                ),
                await self.service._search_book_works(
                    query=query,
                    series=series,
                    publisher=publisher,
                    imprint=imprint,
                    subtitle=subtitle,
                    language=language,
                    country=country,
                    age_rating=age_rating,
                    catalog_number=catalog_number,
                    release_status=release_status,
                    year=year,
                    barcode=barcode,
                    limit=limit,
                ),
                await self.service._search_movie_works(
                    query=query,
                    publisher=publisher,
                    subtitle=subtitle,
                    language=language,
                    country=country,
                    age_rating=age_rating,
                    catalog_number=catalog_number,
                    release_status=release_status,
                    year=year,
                    barcode=barcode,
                    limit=limit,
                ),
                await self.service._search_tv_releases(
                    query=query,
                    publisher=publisher,
                    subtitle=subtitle,
                    language=language,
                    country=country,
                    age_rating=age_rating,
                    catalog_number=catalog_number,
                    release_status=release_status,
                    year=year,
                    barcode=barcode,
                    limit=limit,
                ),
                await self.service._search_anime_series(
                    query=query,
                    language=language,
                    country=country,
                    release_status=release_status,
                    year=year,
                    barcode=barcode,
                    limit=limit,
                ),
                await self.service._search_music_releases(
                    query=query,
                    publisher=publisher,
                    subtitle=subtitle,
                    language=language,
                    country=country,
                    release_status=release_status,
                    year=year,
                    barcode=barcode,
                    catalog_number=catalog_number,
                    limit=limit,
                ),
                await self.service._search_boardgame_works(
                    query=query,
                    publisher=publisher,
                    subtitle=subtitle,
                    language=language,
                    country=country,
                    age_rating=age_rating,
                    catalog_number=catalog_number,
                    release_status=release_status,
                    year=year,
                    barcode=barcode,
                    limit=limit,
                ),
                await self.service._search_game_works(
                    query=query,
                    publisher=publisher,
                    subtitle=subtitle,
                    language=language,
                    country=country,
                    age_rating=age_rating,
                    catalog_number=catalog_number,
                    release_status=release_status,
                    year=year,
                    barcode=barcode,
                    limit=limit,
                ),
                await self.service._search_manga_works(
                    query=query,
                    language=language,
                    country=country,
                    release_status=release_status,
                    year=year,
                    barcode=barcode,
                    limit=limit,
                ),
            ):
                results.extend(batch)
            deduped: list[SearchResult] = []
            seen: set[tuple[ItemKind, UUID]] = set()
            for result in results:
                key = (result.kind, result.id)
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(result)
            return deduped[:limit]
        return []

    async def lookup_barcode(self, barcode: str, kind: ItemKind | None = None) -> SearchResult:
        if kind == ItemKind.comic:
            match = await self.service._comic_work_by_barcode(barcode)
            if match is not None:
                return self.service._comic_search_result(match[0], issue=match[1])
        if kind == ItemKind.book:
            match = await self.service._book_work_by_barcode(barcode)
            if match is not None:
                return self.service._book_search_result(match[0], edition=match[1])
        if kind == ItemKind.movie:
            match = await self.service._movie_work_by_barcode(barcode)
            if match is not None:
                return self.service._movie_search_result(match[0], release=match[1])
        if kind == ItemKind.tv:
            release = await self.service._tv_release_by_barcode(barcode)
            if release is not None:
                return self.service._tv_search_result(release)
        if kind == ItemKind.anime:
            series = await self.service._anime_series_by_barcode(barcode)
            if series is not None:
                return self.service._anime_search_result(series)
        if kind == ItemKind.music:
            release = await self.service._music_release_by_barcode(barcode)
            if release is not None:
                return self.service._music_search_result(release)
        if kind == ItemKind.boardgame:
            work = await self.service._boardgame_work_by_barcode(barcode)
            if work is not None:
                return self.service._boardgame_search_result(work)
        if kind == ItemKind.game:
            work = await self.service._game_work_by_barcode(barcode)
            if work is not None:
                return self.service._game_search_result(work)
        if kind == ItemKind.manga:
            work = await self.service._manga_work_by_barcode(barcode)
            if work is not None:
                return self.service._manga_search_result(work)
        if kind is None:
            for lookup in (
                self.service._comic_work_by_barcode,
                self.service._book_work_by_barcode,
                self.service._movie_work_by_barcode,
                self.service._tv_release_by_barcode,
                self.service._anime_series_by_barcode,
                self.service._music_release_by_barcode,
                self.service._boardgame_work_by_barcode,
                self.service._game_work_by_barcode,
                self.service._manga_work_by_barcode,
            ):
                match = await lookup(barcode)
                if match is None:
                    continue
                if isinstance(match, tuple):
                    if isinstance(match[0], ComicWork):
                        return self.service._comic_search_result(match[0], issue=match[1])
                    if isinstance(match[0], BookWork):
                        return self.service._book_search_result(match[0], edition=match[1])
                    if isinstance(match[0], MovieWork):
                        return self.service._movie_search_result(match[0], release=match[1])
                if isinstance(match, TVRelease):
                    return self.service._tv_search_result(match)
                if isinstance(match, AnimeSeries):
                    return self.service._anime_search_result(match)
                if isinstance(match, MusicRelease):
                    return self.service._music_search_result(match)
                if isinstance(match, BoardGameWork):
                    return self.service._boardgame_search_result(match)
                if isinstance(match, GameWork):
                    return self.service._game_search_result(match)
                if isinstance(match, MangaWork):
                    return self.service._manga_search_result(match)
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="barcode_not_found",
            detail="Barcode not found",
        )
