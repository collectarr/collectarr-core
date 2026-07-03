from __future__ import annotations

from collections import defaultdict
from datetime import date
from uuid import NAMESPACE_URL, uuid5

from app.models import (
        TVEpisode,
        TVRelease,
        TVReleaseContribution,
        TVReleaseIdentifier,
        TVReleaseMedia,
)
from app.schemas import (
        TVContributorResponse,
        TVEpisodeV1Response,
        TVIdentifierResponse,
        TVReleaseMediaResponse,
        TVSeasonV1Response,
        TVSeriesV1Response,
)


class TVMetadataResponseBuilders:
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
