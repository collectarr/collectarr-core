from __future__ import annotations

from collections import defaultdict
from datetime import date
from uuid import NAMESPACE_URL, uuid5

from app.models import (
    AnimeCharacterAppearance,
    AnimeContribution,
    AnimeEpisode,
    AnimeIdentifier,
    AnimeSeries,
    BoardGameEdition,
    BoardGameWork,
    BookContribution,
    BookEdition,
    BookIdentifier,
    BookSeriesMembership,
    BookWork,
    ComicContribution,
    ComicIdentifier,
    ComicIssue,
    ComicWork,
    GameRelease,
    GameWork,
    MangaChapter,
    MangaCharacterAppearance,
    MangaContribution,
    MangaIdentifier,
    MangaSeriesMembership,
    MangaWork,
    MovieRelease,
    MovieReleaseMedia,
    MovieWork,
    MovieWorkContribution,
    MovieWorkIdentifier,
    MusicMedia,
    MusicRelease,
    MusicReleaseContribution,
    MusicReleaseIdentifier,
    MusicTrack,
    TVEpisode,
    TVRelease,
    TVReleaseContribution,
    TVReleaseIdentifier,
    TVReleaseMedia,
)
from app.schemas import (
    AnimeCharacterResponse,
    AnimeContributorResponse,
    AnimeEpisodeV1Response,
    AnimeIdentifierResponse,
    AnimeSeriesV1Response,
    BoardGameEditionV1Response,
    BoardGameWorkV1Response,
    BookContributorResponse,
    BookEditionV1Response,
    BookIdentifierResponse,
    BookSeriesResponse,
    BookWorkV1Response,
    ComicCharacterResponse,
    ComicContributorResponse,
    ComicIdentifierResponse,
    ComicIssueV1Response,
    ComicStoryArcResponse,
    ComicWorkV1Response,
    GameReleaseV1Response,
    GameWorkV1Response,
    MangaChapterV1Response,
    MangaCharacterResponse,
    MangaContributorResponse,
    MangaIdentifierResponse,
    MangaSeriesResponse,
    MangaWorkV1Response,
    MovieContributorResponse,
    MovieIdentifierResponse,
    MovieReleaseMediaResponse,
    MovieReleaseV1Response,
    MovieWorkV1Response,
    MusicContributorResponse,
    MusicIdentifierResponse,
    MusicMediaV1Response,
    MusicReleaseV1Response,
    MusicTrackV1Response,
    TVContributorResponse,
    TVEpisodeV1Response,
    TVIdentifierResponse,
    TVReleaseMediaResponse,
    TVSeasonV1Response,
    TVSeriesV1Response,
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

    def _comic_contributor_response(
        self,
        contribution: ComicContribution,
        *,
        scope: str,
    ) -> ComicContributorResponse:
        person = contribution.person
        return ComicContributorResponse(
            person_id=contribution.person_id,
            name=person.name if person is not None else "",
            role=contribution.role,
            sequence=contribution.sequence,
            scope=scope,
        )

    def _comic_identifier_response(self, identifier: ComicIdentifier) -> ComicIdentifierResponse:
        return ComicIdentifierResponse(
            id=identifier.id,
            identifier_type=identifier.identifier_type,
            value=identifier.value,
            normalized_value=identifier.normalized_value,
            is_primary=identifier.is_primary,
            source_provider=identifier.source_provider,
        )

    def _comic_issue_response(self, issue: ComicIssue) -> ComicIssueV1Response:
        return ComicIssueV1Response(
            id=issue.id,
            work_id=issue.work_id,
            issue_number=issue.issue_number,
            display_title=issue.display_title,
            publication_date=issue.publication_date,
            release_date=issue.release_date,
            publisher=issue.publisher,
            imprint=issue.imprint,
            language=issue.language,
            region=issue.region,
            page_count=issue.page_count,
            cover_price_cents=issue.cover_price_cents,
            currency=issue.currency,
            release_status=issue.release_status,
            cover_image_url=issue.cover_image_url,
            cover_image_key=issue.cover_image_key,
            description=issue.description,
            contributors=[
                self._comic_contributor_response(row, scope="issue")
                for row in sorted(
                    issue.contributions or [],
                    key=lambda c: (
                        c.sequence is None,
                        c.sequence or 0,
                        c.role.casefold(),
                        str(c.person_id),
                    ),
                )
            ],
            identifiers=[
                self._comic_identifier_response(row)
                for row in sorted(
                    issue.identifiers or [],
                    key=lambda i: (
                        i.identifier_type.casefold(),
                        (i.normalized_value or i.value or "").casefold(),
                        str(i.id),
                    ),
                )
            ],
            characters=[
                ComicCharacterResponse(
                    character_id=row.character_id,
                    name=row.character.name if row.character is not None else "",
                    role=row.role,
                )
                for row in sorted(
                    issue.character_appearances or [],
                    key=lambda c: (
                        c.role.casefold(),
                        str(c.character_id),
                    ),
                )
            ],
            story_arcs=[
                ComicStoryArcResponse(
                    story_arc_id=row.story_arc_id,
                    name=row.story_arc.name if row.story_arc is not None else "",
                    ordinal=row.ordinal,
                )
                for row in sorted(
                    issue.story_arc_memberships or [],
                    key=lambda a: (
                        a.ordinal is None,
                        a.ordinal or 0,
                        str(a.story_arc_id),
                    ),
                )
            ],
        )

    def _comic_work_response(self, work: ComicWork) -> ComicWorkV1Response:
        issues = sorted(
            work.issues or [],
            key=lambda i: (
                i.publication_date is None,
                i.publication_date or date.max,
                i.issue_number is None,
                i.issue_number or "",
                str(i.id),
            ),
        )
        return ComicWorkV1Response(
            id=work.id,
            title=work.title,
            sort_title=work.sort_title,
            subtitle=work.subtitle,
            description=work.description,
            original_language=work.original_language,
            first_publication_date=work.first_publication_date,
            contributors=[
                self._comic_contributor_response(row, scope="work")
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
            issues=[self._comic_issue_response(row) for row in issues],
        )

    def _manga_series_response(self, membership: MangaSeriesMembership) -> MangaSeriesResponse:
        series = membership.series
        return MangaSeriesResponse(
            id=series.id,
            title=series.title,
            slug=series.slug,
            sequence=membership.sequence,
            display_number=membership.display_number,
        )

    def _manga_chapter_response(self, chapter: MangaChapter) -> MangaChapterV1Response:
        return MangaChapterV1Response(
            id=chapter.id,
            work_id=chapter.work_id,
            chapter_number=chapter.chapter_number,
            chapter_title=chapter.chapter_title,
            publication_date=chapter.publication_date,
            page_count=chapter.page_count,
            description=chapter.description,
            cover_image_url=chapter.cover_image_url,
            cover_image_key=chapter.cover_image_key,
        )

    def _manga_contributor_response(self, contrib: MangaContribution) -> MangaContributorResponse:
        return MangaContributorResponse(
            id=contrib.id,
            person_id=contrib.person_id,
            name=contrib.person.name if contrib.person is not None else "",
            role=contrib.role,
            sequence=contrib.sequence,
        )

    def _manga_identifier_response(self, identifier: MangaIdentifier) -> MangaIdentifierResponse:
        return MangaIdentifierResponse(
            id=identifier.id,
            identifier_type=identifier.identifier_type,
            value=identifier.value,
            is_primary=identifier.is_primary,
        )

    def _manga_character_response(self, char: MangaCharacterAppearance) -> MangaCharacterResponse:
        return MangaCharacterResponse(
            id=char.id,
            character_id=char.character_id,
            character_name=char.character.name if char.character is not None else "",
            role=char.role,
        )

    def _manga_work_response(self, work: MangaWork) -> MangaWorkV1Response:
        chapters = sorted(
            work.chapters or [],
            key=lambda c: (
                c.chapter_number is None,
                c.chapter_number or 0,
                c.publication_date is None,
                c.publication_date or date.max,
                str(c.id),
            ),
        )
        return MangaWorkV1Response(
            id=work.id,
            title=work.title,
            sort_title=work.sort_title,
            subtitle=work.subtitle,
            description=work.description,
            original_language=work.original_language,
            original_publication_date=work.original_publication_date,
            first_publication_date=work.first_publication_date,
            status=work.status,
            series=[
                self._manga_series_response(row)
                for row in sorted(
                    work.series_memberships or [],
                    key=lambda m: (
                        m.sequence is None,
                        m.sequence or 0,
                        str(m.series_id),
                    ),
                )
            ],
            chapters=[self._manga_chapter_response(row) for row in chapters],
            contributions=[
                self._manga_contributor_response(row)
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
            identifiers=[
                self._manga_identifier_response(row)
                for row in sorted(
                    work.identifiers or [],
                    key=lambda i: (
                        i.identifier_type.casefold(),
                        (i.normalized_value or i.value or "").casefold(),
                        str(i.id),
                    ),
                )
            ],
            character_appearances=[
                self._manga_character_response(row)
                for row in sorted(
                    work.character_appearances or [],
                    key=lambda c: (
                        c.role.casefold(),
                        str(c.character_id),
                    ),
                )
            ],
        )

    def _anime_series_response(self, series: AnimeSeries) -> AnimeSeriesV1Response:
        episodes = sorted(
            series.episodes or [],
            key=lambda e: (
                e.episode_number is None,
                e.episode_number or 0,
                e.air_date is None,
                e.air_date or date.max,
                str(e.id),
            ),
        )
        return AnimeSeriesV1Response(
            id=series.id,
            title=series.title,
            sort_title=series.sort_title,
            description=series.description,
            original_language=series.original_language,
            original_air_date=series.original_air_date,
            end_date=series.end_date,
            status=series.status,
            anime_type=series.anime_type,
            episode_count=series.episode_count,
            episodes=[self._anime_episode_response(row) for row in episodes],
            contributions=[
                self._anime_contributor_response(row)
                for row in sorted(
                    series.contributions or [],
                    key=lambda c: (
                        c.sequence is None,
                        c.sequence or 0,
                        c.role.casefold(),
                        str(c.person_id),
                    ),
                )
            ],
            identifiers=[
                self._anime_identifier_response(row)
                for row in sorted(
                    series.identifiers or [],
                    key=lambda i: (
                        i.identifier_type.casefold(),
                        (i.normalized_value or i.value or "").casefold(),
                        str(i.id),
                    ),
                )
            ],
            character_appearances=[
                self._anime_character_response(row)
                for row in sorted(
                    series.character_appearances or [],
                    key=lambda c: (
                        c.role.casefold(),
                        str(c.character_id),
                    ),
                )
            ],
        )

    def _anime_episode_response(self, episode: AnimeEpisode) -> AnimeEpisodeV1Response:
        return AnimeEpisodeV1Response(
            id=episode.id,
            series_id=episode.series_id,
            episode_number=episode.episode_number,
            episode_title=episode.episode_title,
            air_date=episode.air_date,
            description=episode.description,
            cover_image_url=episode.cover_image_url,
            cover_image_key=episode.cover_image_key,
            runtime_minutes=episode.runtime_minutes,
        )

    def _anime_contributor_response(self, contrib: AnimeContribution) -> AnimeContributorResponse:
        return AnimeContributorResponse(
            id=contrib.id,
            person_id=contrib.person_id,
            name=contrib.person.name if contrib.person is not None else "",
            role=contrib.role,
            sequence=contrib.sequence,
        )

    def _anime_identifier_response(self, identifier: AnimeIdentifier) -> AnimeIdentifierResponse:
        return AnimeIdentifierResponse(
            id=identifier.id,
            identifier_type=identifier.identifier_type,
            value=identifier.value,
            is_primary=identifier.is_primary,
        )

    def _anime_character_response(self, char: AnimeCharacterAppearance) -> AnimeCharacterResponse:
        return AnimeCharacterResponse(
            id=char.id,
            character_id=char.character_id,
            character_name=char.character.name if char.character is not None else "",
            role=char.role,
        )

    def _movie_work_response(self, work: MovieWork) -> MovieWorkV1Response:
        releases = sorted(
            work.releases or [],
            key=lambda r: (
                r.release_date is None,
                r.release_date or date.max,
                str(r.id),
            ),
        )
        return MovieWorkV1Response(
            id=work.id,
            title=work.title,
            sort_title=work.sort_title,
            subtitle=work.subtitle,
            description=work.description,
            original_language=work.original_language,
            release_date=work.original_release_date,
            runtime_minutes=work.runtime_minutes,
            age_rating=work.age_rating,
            audience_rating=work.audience_rating,
            releases=[self._movie_release_response(row) for row in releases],
            contributions=[
                self._movie_contributor_response(row)
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
            trailer_urls=_metadata_links(work.metadata_json, "trailer_urls"),
            external_links=_metadata_links(work.metadata_json, "external_links"),
            identifiers=[
                self._movie_identifier_response(row)
                for row in sorted(
                    work.identifiers or [],
                    key=lambda i: (
                        i.identifier_type.casefold(),
                        (i.normalized_value or i.value or "").casefold(),
                        str(i.id),
                    ),
                )
            ],
            character_appearances=[],
        )

    def _movie_release_media_response(self, media: MovieReleaseMedia) -> MovieReleaseMediaResponse:
        return MovieReleaseMediaResponse(
            id=media.id,
            release_id=media.release_id,
            media_number=media.media_number,
            media_type=media.media_type,
            title=media.title,
            aspect_ratio=media.aspect_ratio,
            screen_ratio=media.screen_ratio,
            color=media.color,
            num_discs=media.num_discs,
            nr_layers=media.nr_layers,
            layers=media.layers,
            audio_tracks=media.audio_tracks,
            subtitles=media.subtitles,
        )

    def _movie_release_response(self, release: MovieRelease) -> MovieReleaseV1Response:
        media = sorted(
            release.media or [],
            key=lambda row: (
                row.media_number is None,
                row.media_number or 0,
                str(row.id),
            ),
        )
        return MovieReleaseV1Response(
            id=release.id,
            work_id=release.work_id,
            release_date=release.release_date,
            region=release.region_code,
            format=release.format,
            distributor=release.distributor,
            cover_image_url=release.cover_image_url,
            cover_image_key=release.cover_image_key,
            trailer_urls=_metadata_links(release.metadata_json, "trailer_urls"),
            external_links=_metadata_links(release.metadata_json, "external_links"),
            media=[self._movie_release_media_response(row) for row in media],
        )

    def _movie_contributor_response(self, contrib: MovieWorkContribution) -> MovieContributorResponse:
        return MovieContributorResponse(
            id=contrib.id,
            person_id=contrib.person_id,
            name=contrib.person.name if contrib.person is not None else "",
            role=contrib.role,
            sequence=contrib.sequence,
            character_name=contrib.character_name,
        )

    def _movie_identifier_response(self, identifier: MovieWorkIdentifier) -> MovieIdentifierResponse:
        return MovieIdentifierResponse(
            id=identifier.id,
            identifier_type=identifier.identifier_type,
            value=identifier.value,
            is_primary=identifier.is_primary,
        )

    def _music_release_response(self, release: MusicRelease) -> MusicReleaseV1Response:
        track_count = release.track_count
        if track_count is None:
            media_track_counts = [
                media.track_count
                for media in (release.media or [])
                if media.track_count is not None
            ]
            if media_track_counts:
                track_count = sum(media_track_counts)
            else:
                track_count = sum(len(media.tracks or []) for media in (release.media or [])) or None
        media_list = []
        if release.media:
            for m in sorted(
                release.media,
                key=lambda media: (media.media_number, str(media.id)),
            ):
                tracks = [
                    MusicTrackV1Response(
                        id=t.id,
                        media_id=t.media_id,
                        position=t.position,
                        title=t.title,
                        duration_ms=t.duration_ms,
                        instrument=t.instrument,
                        composition=t.composition,
                    )
                    for t in sorted(
                        m.tracks or [],
                        key=lambda track: (track.position.casefold(), str(track.id)),
                    )
                ]
                media_list.append(
                    MusicMediaV1Response(
                        id=m.id,
                        release_id=m.release_id,
                        media_number=m.media_number,
                        media_type=m.media_type,
                        title=m.title,
                        track_count=m.track_count,
                        packaging=m.packaging,
                        media_condition=m.media_condition,
                        sound_type=m.sound_type,
                        vinyl_color=m.vinyl_color,
                        vinyl_weight=m.vinyl_weight,
                        rpm=m.rpm,
                        spars=m.spars,
                        tracks=tracks,
                    )
                )
        return MusicReleaseV1Response(
            id=release.id,
            title=release.title,
            sort_title=release.sort_title,
            subtitle=release.subtitle,
            release_status=release.release_status,
            release_date=release.release_date,
            recording_date=release.recording_date,
            track_count=track_count,
            publisher=release.publisher,
            studio=release.studio,
            catalog_number=release.catalog_number,
            barcode=release.barcode,
            country_code=release.country_code,
            language=release.language,
            cover_image_url=release.cover_image_url,
            cover_image_key=release.cover_image_key,
            extras=release.extras,
            media=media_list,
            contributions=[
                self._music_contributor_response(row)
                for row in sorted(
                    release.contributions or [],
                    key=lambda c: (
                        c.sequence is None,
                        c.sequence or 0,
                        c.role.casefold(),
                        str(c.person_id),
                    ),
                )
            ],
            identifiers=[
                self._music_identifier_response(row)
                for row in sorted(
                    release.identifiers or [],
                    key=lambda i: (
                        i.identifier_type.casefold(),
                        (i.normalized_value or i.value or "").casefold(),
                        str(i.id),
                    ),
                )
            ],
        )

    def _music_media_response(self, media: MusicMedia) -> MusicMediaV1Response:
        return MusicMediaV1Response(
            id=media.id,
            release_id=media.release_id,
            media_number=media.media_number,
            media_type=media.media_type,
            title=media.title,
            track_count=media.track_count,
            packaging=media.packaging,
            media_condition=media.media_condition,
            sound_type=media.sound_type,
            vinyl_color=media.vinyl_color,
            vinyl_weight=media.vinyl_weight,
            rpm=media.rpm,
            spars=media.spars,
            tracks=[
                self._music_track_response(track)
                for track in sorted(
                    media.tracks or [],
                    key=lambda track: (track.position.casefold(), str(track.id)),
                )
            ],
        )

    def _music_track_response(self, track: MusicTrack) -> MusicTrackV1Response:
        return MusicTrackV1Response(
            id=track.id,
            media_id=track.media_id,
            position=track.position,
            title=track.title,
            duration_ms=track.duration_ms,
            instrument=track.instrument,
            composition=track.composition,
        )

    def _music_contributor_response(self, contrib: MusicReleaseContribution) -> MusicContributorResponse:
        return MusicContributorResponse(
            person_id=contrib.person_id,
            name=contrib.person.name if contrib.person is not None else "",
            role=contrib.role,
            sequence=contrib.sequence,
        )

    def _music_identifier_response(self, identifier: MusicReleaseIdentifier) -> MusicIdentifierResponse:
        return MusicIdentifierResponse(
            id=identifier.id,
            identifier_type=identifier.identifier_type,
            value=identifier.value,
            normalized_value=identifier.normalized_value or identifier.value,
            is_primary=identifier.is_primary,
            source_provider=identifier.source_provider,
        )

    def _tv_episode_response(self, episode: TVEpisode) -> TVEpisodeV1Response:
        return TVEpisodeV1Response(
            id=episode.id,
            series_id=episode.release_id,
            episode_number=float(episode.episode_number),
            episode_title=episode.title,
            air_date=episode.original_air_date,
            description=episode.overview,
            cover_image_url=episode.still_url,
            cover_image_key=episode.still_key,
            runtime_minutes=episode.duration_seconds // 60 if episode.duration_seconds is not None else None,
        )

    def _tv_release_media_response(self, media: TVReleaseMedia) -> TVReleaseMediaResponse:
        return TVReleaseMediaResponse(
            id=media.id,
            release_id=media.release_id,
            media_number=media.media_number,
            media_type=media.media_type,
            title=media.title,
            episode_count=media.episode_count,
            runtime_minutes=media.runtime_minutes,
            region_code=media.region_code,
            encoding=media.encoding,
            aspect_ratio=media.aspect_ratio,
            color=media.color,
            audio_tracks=media.audio_tracks,
            subtitles=media.subtitles,
            layers=media.layers,
            frame_rate=media.frame_rate,
            bit_depth=media.bit_depth,
            resolution=media.resolution,
            hdr_format=media.hdr_format,
        )

    def _tv_season_response(self, release: TVRelease, season_number: int, episodes: list[TVEpisode]) -> TVSeasonV1Response:
        ordered_episodes = sorted(
            episodes,
            key=lambda episode: (episode.episode_number, episode.original_air_date or date.max, str(episode.id)),
        )
        season_air_date = next((episode.original_air_date for episode in ordered_episodes if episode.original_air_date), None)
        return TVSeasonV1Response(
            id=uuid5(NAMESPACE_URL, f"tv-season:{release.id}:{season_number}"),
            series_id=release.id,
            season_number=season_number,
            air_date=season_air_date,
            episode_count=len(ordered_episodes),
            description=release.description,
            cover_image_url=release.cover_image_url,
            cover_image_key=release.cover_image_key,
            episodes=[self._tv_episode_response(episode) for episode in ordered_episodes],
        )

    def _tv_series_response(self, release: TVRelease) -> TVSeriesV1Response:
        media = sorted(
            release.media or [],
            key=lambda row: (
                row.media_number is None,
                row.media_number or 0,
                str(row.id),
            ),
        )
        episodes_by_season: dict[int, list[TVEpisode]] = defaultdict(list)
        for episode in release.episodes or []:
            episodes_by_season[episode.season_number].append(episode)
        seasons = [
            self._tv_season_response(release, season_number, episodes)
            for season_number, episodes in sorted(episodes_by_season.items(), key=lambda item: item[0])
        ]
        return TVSeriesV1Response(
            id=release.id,
            title=release.title,
            sort_title=release.sort_title,
            description=release.description,
            original_language=None,
            original_air_date=release.release_date,
            end_date=None,
            status=None,
            season_count=release.season_count or len(seasons),
            episode_count=release.episode_count or sum(len(season.episodes) for season in seasons),
            network=release.publisher,
            seasons=seasons,
            media=[self._tv_release_media_response(row) for row in media],
            contributions=[
                self._tv_contributor_response(row)
                for row in sorted(
                    release.contributions or [],
                    key=lambda c: (
                        c.sequence is None,
                        c.sequence or 0,
                        c.role.casefold(),
                        str(c.person_id),
                    ),
                )
            ],
            identifiers=[
                self._tv_identifier_response(row)
                for row in sorted(
                    release.identifiers or [],
                    key=lambda i: (
                        i.identifier_type.casefold(),
                        (i.normalized_value or i.value or "").casefold(),
                        str(i.id),
                    ),
                )
            ],
            character_appearances=[],
        )

    def _tv_contributor_response(self, contrib: TVReleaseContribution) -> TVContributorResponse:
        return TVContributorResponse(
            id=contrib.id,
            person_id=contrib.person_id,
            name=contrib.person.name if contrib.person is not None else "",
            role=contrib.role,
            sequence=contrib.sequence,
        )

    def _tv_identifier_response(self, identifier: TVReleaseIdentifier) -> TVIdentifierResponse:
        return TVIdentifierResponse(
            id=identifier.id,
            identifier_type=identifier.identifier_type,
            value=identifier.value,
            is_primary=identifier.is_primary,
        )
