from __future__ import annotations

from datetime import date

from app.models import (
        AnimeRelease,
        AnimeReleaseEpisodeMap,
        AnimeReleaseMedia,
        AnimeCharacterAppearance,
        AnimeContribution,
        AnimeEpisode,
        AnimeIdentifier,
        AnimeSeries,
)
from app.schemas import (
        AnimeCharacterResponse,
        AnimeContributorResponse,
        AnimeEpisodeV1Response,
        AnimeIdentifierResponse,
        AnimeReleaseEpisodeMapV1Response,
        AnimeReleaseMediaResponse,
        AnimeReleaseV1Response,
        AnimeSeriesV1Response,
)


class AnimeMetadataResponseBuilders:
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
                releases=[
                    self._anime_release_response(row)
                    for row in sorted(
                        series.releases or [],
                        key=lambda row: (
                            row.release_date is None,
                            row.release_date or date.max,
                            row.title.casefold(),
                            str(row.id),
                        ),
                    )
                ],
            )

        def _anime_release_media_response(self, media: AnimeReleaseMedia) -> AnimeReleaseMediaResponse:
            return AnimeReleaseMediaResponse(
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
                audio_tracks=media.audio_tracks,
                subtitles=media.subtitles,
                resolution=media.resolution,
                hdr_format=media.hdr_format,
            )

        def _anime_release_episode_map_response(
            self,
            mapping: AnimeReleaseEpisodeMap,
        ) -> AnimeReleaseEpisodeMapV1Response:
            return AnimeReleaseEpisodeMapV1Response(
                id=mapping.id,
                release_id=mapping.release_id,
                media_id=mapping.media_id,
                episode_id=mapping.episode_id,
                disc_number=mapping.disc_number,
                sequence_number=mapping.sequence_number,
            )

        def _anime_release_response(self, release: AnimeRelease) -> AnimeReleaseV1Response:
            media = sorted(
                release.media or [],
                key=lambda row: (row.media_number, str(row.id)),
            )
            mappings = sorted(
                release.episode_mappings or [],
                key=lambda row: (
                    row.disc_number is None,
                    row.disc_number or 0,
                    row.sequence_number is None,
                    row.sequence_number or 0,
                    str(row.id),
                ),
            )
            return AnimeReleaseV1Response(
                id=release.id,
                work_id=release.work_id,
                title=release.title,
                sort_title=release.sort_title,
                description=release.description,
                media_count=release.media_count,
                format=release.format,
                region_code=release.region_code,
                release_date=release.release_date,
                publisher=release.publisher,
                distributor=release.distributor,
                barcode=release.barcode,
                catalog_number=release.catalog_number,
                packaging=release.packaging,
                release_status=release.release_status,
                language_audio=release.language_audio,
                language_subtitles=release.language_subtitles,
                cover_image_url=release.cover_image_url,
                cover_image_key=release.cover_image_key,
                media=[self._anime_release_media_response(row) for row in media],
                episode_mappings=[
                    self._anime_release_episode_map_response(row) for row in mappings
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
                    image_url=contrib.person.image_url if contrib.person is not None else None,
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
