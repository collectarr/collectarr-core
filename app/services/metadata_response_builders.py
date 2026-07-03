from __future__ import annotations

from datetime import date

from app.models import (
    BoardGameEdition,
    BoardGameWork,
    BookContribution,
    BookEdition,
    BookIdentifier,
    BookSeriesMembership,
    BookWork,
    GameRelease,
    GameWork,
)
from app.schemas import (
    BoardGameEditionV1Response,
    BoardGameWorkV1Response,
    BookContributorResponse,
    BookEditionV1Response,
    BookIdentifierResponse,
    BookSeriesResponse,
    BookWorkV1Response,
    GameReleaseV1Response,
    GameWorkV1Response,
)
from app.services.metadata_helpers import _metadata_links, _metadata_list


class MetadataResponseBuilders:
    def _book_contributor_response(
        self,
        contribution: BookContribution,
        *,
        scope: str,
    ) -> BookContributorResponse:
        person = contribution.person
        return BookContributorResponse(
            person_id=contribution.person_id,
            name=person.name if person is not None else "",
            role=contribution.role,
            sequence=contribution.sequence,
            scope=scope,
        )

    def _book_identifier_response(self, identifier: BookIdentifier) -> BookIdentifierResponse:
        return BookIdentifierResponse(
            id=identifier.id,
            identifier_type=identifier.identifier_type,
            value=identifier.value,
            normalized_value=identifier.normalized_value,
            is_primary=identifier.is_primary,
            source_provider=identifier.source_provider,
        )

    def _book_edition_response(self, edition: BookEdition) -> BookEditionV1Response:
        return BookEditionV1Response(
            id=edition.id,
            work_id=edition.work_id,
            display_title=edition.display_title,
            edition_statement=edition.edition_statement,
            format=edition.format,
            binding=edition.binding,
            publication_date=edition.publication_date,
            publisher=edition.publisher,
            imprint=edition.imprint,
            language=edition.language,
            region=edition.region,
            page_count=edition.page_count,
            audio_length_minutes=edition.audio_length_minutes,
            age_rating=edition.age_rating,
            release_status=edition.release_status,
            cover_image_url=edition.cover_image_url,
            cover_image_key=edition.cover_image_key,
            description=edition.description,
            contributors=[
                self._book_contributor_response(row, scope="edition")
                for row in sorted(
                    edition.contributions or [],
                    key=lambda c: (
                        c.sequence is None,
                        c.sequence or 0,
                        c.role.casefold(),
                        str(c.person_id),
                    ),
                )
            ],
            identifiers=[
                self._book_identifier_response(row)
                for row in sorted(
                    edition.identifiers or [],
                    key=lambda i: (
                        i.identifier_type.casefold(),
                        (i.normalized_value or i.value or "").casefold(),
                        str(i.id),
                    ),
                )
            ],
        )

    def _book_series_response(self, membership: BookSeriesMembership) -> BookSeriesResponse:
        series = membership.series
        return BookSeriesResponse(
            id=series.id,
            title=series.title,
            slug=series.slug,
            sequence=membership.sequence,
            display_number=membership.display_number,
        )

    def _book_work_response(self, work: BookWork) -> BookWorkV1Response:
        editions = sorted(
            work.editions or [],
            key=lambda e: (
                e.publication_date is None,
                e.publication_date or date.max,
                str(e.id),
            ),
        )
        return BookWorkV1Response(
            id=work.id,
            title=work.title,
            sort_title=work.sort_title,
            subtitle=work.subtitle,
            description=work.description,
            original_language=work.original_language,
            original_publication_date=work.original_publication_date,
            first_publication_date=work.first_publication_date,
            contributors=[
                self._book_contributor_response(row, scope="work")
                for row in sorted(
                    work.contributions or [],
                    key=lambda c: (
                        c.sequence is None,
                        c.sequence or 0,
                        c.role.casefold(),
                        str(c.person_id),
                    ),
                )
            ],
            series=[
                self._book_series_response(row)
                for row in sorted(
                    work.series_memberships or [],
                    key=lambda m: (
                        m.sequence is None,
                        m.sequence or 0,
                        str(m.series_id),
                    ),
                )
            ],
            editions=[self._book_edition_response(row) for row in editions],
        )

    def _game_release_response(self, release: GameRelease) -> GameReleaseV1Response:
        return GameReleaseV1Response(
            id=release.id,
            work_id=release.work_id,
            release_title=release.release_title,
            platform=release.platform,
            release_date=release.release_date,
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
        metadata = work.metadata_json or {}
        return GameWorkV1Response(
            id=work.id,
            title=work.title,
            sort_title=work.sort_title,
            subtitle=work.subtitle,
            description=work.description,
            release_date=work.release_date,
            original_language=work.original_language,
            publisher=primary_release.publisher if primary_release is not None else None,
            age_rating=work.age_rating,
            audience_rating=work.audience_rating,
            search_aliases=_metadata_list(metadata, "search_aliases"),
            genres=_metadata_list(metadata, "genres"),
            platforms=_metadata_list(metadata, "platforms"),
            identifiers=_metadata_list(metadata, "identifiers"),
            company_roles=_metadata_list(metadata, "company_roles"),
            age_ratings=_metadata_list(metadata, "age_ratings"),
            trailer_urls=_metadata_links(metadata, "trailer_urls"),
            external_links=_metadata_links(metadata, "external_links"),
            releases=[self._game_release_response(row) for row in releases],
        )

    def _boardgame_edition_response(self, edition: BoardGameEdition) -> BoardGameEditionV1Response:
        return BoardGameEditionV1Response(
            id=edition.id,
            work_id=edition.work_id,
            edition_title=edition.edition_title,
            format=edition.format,
            release_date=edition.release_date,
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
        metadata = work.metadata_json or {}
        return BoardGameWorkV1Response(
            id=work.id,
            title=work.title,
            sort_title=work.sort_title,
            subtitle=work.subtitle,
            description=work.description,
            release_date=work.release_date,
            original_language=work.original_language,
            publisher=primary_edition.publisher if primary_edition is not None else None,
            age_rating=work.age_rating,
            audience_rating=work.audience_rating,
            search_aliases=_metadata_list(metadata, "search_aliases"),
            genres=_metadata_list(metadata, "genres"),
            platforms=_metadata_list(metadata, "platforms"),
            identifiers=_metadata_list(metadata, "identifiers"),
            contributors=_metadata_list(metadata, "contributors"),
            mechanics=_metadata_list(metadata, "mechanics"),
            categories=_metadata_list(metadata, "categories"),
            families=_metadata_list(metadata, "families"),
            expansions=_metadata_list(metadata, "expansions"),
            rankings=_metadata_list(metadata, "rankings"),
            trailer_urls=_metadata_links(metadata, "trailer_urls"),
            external_links=_metadata_links(metadata, "external_links"),
            editions=[self._boardgame_edition_response(row) for row in editions],
        )
