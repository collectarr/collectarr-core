from __future__ import annotations

from datetime import date

from app.models import (
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
