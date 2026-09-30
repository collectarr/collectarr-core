from __future__ import annotations

from app.models import (
    BoardGameEdition,
    BoardGameWork,
    GameRelease,
    GameWork,
)
from app.models.partial_date import partial_date_from_storage
from app.schemas import (
    BoardGameEditionV1Response,
    BoardGameWorkV1Response,
    GameReleaseV1Response,
    GameWorkV1Response,
)
from app.services.metadata.metadata_builders_anime import AnimeMetadataResponseBuilders
from app.services.metadata.metadata_builders_comics import ComicMetadataResponseBuilders
from app.services.metadata.metadata_builders_manga import MangaMetadataResponseBuilders
from app.services.metadata.metadata_builders_movies import MovieMetadataResponseBuilders
from app.services.metadata.metadata_builders_tv import TVMetadataResponseBuilders
from app.services.metadata.metadata_helpers import entity_link_values


class MetadataResponseBuilders(ComicMetadataResponseBuilders, MangaMetadataResponseBuilders, AnimeMetadataResponseBuilders, MovieMetadataResponseBuilders, TVMetadataResponseBuilders):
    def _game_release_response(self, release: GameRelease) -> GameReleaseV1Response:
        return GameReleaseV1Response(
            id=release.id,
            work_id=release.work_id,
            release_title=release.release_title,
            platform=release.platform,
            release_date=release.release_date,
            release_date_parts=partial_date_from_storage(release.release_date_parts),
            region_code=release.region_code,
            format=release.format,
            publisher=release.publisher,
            catalog_number=release.catalog_number,
            barcode=release.barcode,
            release_status=release.release_status,
            language=release.language,
            cover_image_url=release.cover_image_url,
            cover_image_key=release.cover_image_key,
        )

    def _game_work_response(self, work: GameWork) -> GameWorkV1Response:
        releases = sorted(
            work.releases or [],
            key=lambda row: (
                getattr(row, "release_date", None) is None,
                getattr(row, "release_date", None) or date.max,
                str(getattr(row, "id", "")),
            ),
        )
        primary_release = releases[0] if releases else None
        return GameWorkV1Response(
            id=work.id,
            title=work.title,
            sort_title=work.sort_title,
            subtitle=work.subtitle,
            description=work.description,
            release_date=work.release_date,
            release_date_parts=partial_date_from_storage(work.release_date_parts),
            original_language=work.original_language,
            publisher=primary_release.publisher if primary_release is not None else None,
            age_rating=work.age_rating,
            audience_rating=work.audience_rating,
            search_aliases=[row.alias for row in work.alias_entries],
            genres=work.genres,
            platforms=work.platforms,
            identifiers=work.identifiers,
            company_roles=work.company_roles,
            age_ratings=work.age_ratings,
            trailer_urls=entity_link_values(work.entity_links, "trailer"),
            external_links=entity_link_values(work.entity_links, "external"),
            releases=[self._game_release_response(row) for row in releases],
        )

    def _boardgame_edition_response(self, edition: BoardGameEdition) -> BoardGameEditionV1Response:
        return BoardGameEditionV1Response(
            id=edition.id,
            work_id=edition.work_id,
            edition_title=edition.edition_title,
            format=edition.format,
            release_date=edition.release_date,
            release_date_parts=partial_date_from_storage(edition.release_date_parts),
            publisher=edition.publisher,
            catalog_number=edition.catalog_number,
            barcode=edition.barcode,
            release_status=edition.release_status,
            language=edition.language,
            country=edition.country,
            age_rating=edition.age_rating,
            audience_rating=edition.audience_rating,
            min_players=edition.min_players,
            max_players=edition.max_players,
            playing_time_minutes=edition.playing_time_minutes,
            min_age=edition.min_age,
            cover_image_url=edition.cover_image_url,
            cover_image_key=edition.cover_image_key,
            description=edition.description,
        )

    def _boardgame_work_response(self, work: BoardGameWork) -> BoardGameWorkV1Response:
        editions = sorted(
            work.editions or [],
            key=lambda row: (
                getattr(row, "release_date", None) is None,
                getattr(row, "release_date", None) or date.max,
                str(getattr(row, "id", "")),
            ),
        )
        primary_edition = editions[0] if editions else None
        return BoardGameWorkV1Response(
            id=work.id,
            title=work.title,
            sort_title=work.sort_title,
            subtitle=work.subtitle,
            description=work.description,
            release_date=work.release_date,
            release_date_parts=partial_date_from_storage(work.release_date_parts),
            original_language=work.original_language,
            publisher=primary_edition.publisher if primary_edition is not None else None,
            age_rating=work.age_rating,
            audience_rating=work.audience_rating,
            search_aliases=[row.alias for row in work.alias_entries],
            genres=work.genres,
            platforms=work.platforms,
            identifiers=work.identifiers,
            contributors=work.contributors,
            mechanics=work.mechanics,
            categories=work.categories,
            families=work.families,
            expansions=work.expansions,
            rankings=work.rankings,
            trailer_urls=entity_link_values(work.entity_links, "trailer"),
            external_links=entity_link_values(work.entity_links, "external"),
            editions=[self._boardgame_edition_response(row) for row in editions],
        )
