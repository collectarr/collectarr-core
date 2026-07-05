from __future__ import annotations

from datetime import date

from app.models import TVEpisode, TVReleaseContribution, TVReleaseIdentifier, TVReleaseMedia, TVSeason, TVSeries
from app.schemas import (
    TVContributorResponse,
    TVEpisodeV1Response,
    TVIdentifierResponse,
    TVReleaseEpisodeMapV1Response,
    TVReleaseMediaResponse,
    TVReleaseV1Response,
    TVSeasonV1Response,
    TVSeriesV1Response,
)


class TVMetadataResponseBuilders:
    def _tv_episode_response(self, episode: TVEpisode) -> TVEpisodeV1Response:
        return TVEpisodeV1Response(
            id=episode.id,
            season_id=episode.season_id,
            episode_number=float(episode.episode_number),
            episode_title=episode.title,
            air_date=episode.original_air_date,
            description=episode.overview,
            cover_image_url=episode.still_url,
            cover_image_key=episode.still_key,
            image_url=episode.image_url,
            large_image_url=episode.large_image_url,
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

    def _tv_release_episode_map_response(
        self,
        mapping,
    ) -> TVReleaseEpisodeMapV1Response:
        return TVReleaseEpisodeMapV1Response(
            id=mapping.id,
            release_id=mapping.release_id,
            media_id=mapping.media_id,
            episode_id=mapping.episode_id,
            disc_number=mapping.disc_number,
            sequence_number=mapping.sequence_number,
        )

    def _tv_season_response(self, season: TVSeason) -> TVSeasonV1Response:
        ordered_episodes = sorted(
            season.episodes or [],
            key=lambda episode: (episode.episode_number, episode.original_air_date or date.max, str(episode.id)),
        )
        return TVSeasonV1Response(
            id=season.id,
            series_id=season.series_id,
            season_number=season.season_number,
            air_date=season.air_date,
            episode_count=len(ordered_episodes),
            description=season.overview,
            cover_image_url=season.poster_url,
            cover_image_key=None,
            episodes=[self._tv_episode_response(episode) for episode in ordered_episodes],
        )

    def _tv_release_response(self, release) -> TVReleaseV1Response:
        media = sorted(
            release.media or [],
            key=lambda row: (
                row.media_number is None,
                row.media_number or 0,
                str(row.id),
            ),
        )
        episode_mappings = sorted(
            release.episode_mappings or [],
            key=lambda row: (
                row.disc_number is None,
                row.disc_number or 0,
                row.sequence_number is None,
                row.sequence_number or 0,
                str(row.id),
            ),
        )
        return TVReleaseV1Response(
            id=release.id,
            series_id=release.series_id,
            title=release.title,
            sort_title=release.sort_title,
            description=release.description,
            media_count=release.media_count,
            format=release.format,
            region_code=release.region_code,
            release_date=release.release_date,
            publisher=release.publisher,
            sku=release.sku,
            case_type=release.case_type,
            episode_count=release.episode_count,
            season_count=release.season_count,
            runtime_minutes=release.runtime_minutes,
            language_audio=release.language_audio,
            language_subtitles=release.language_subtitles,
            content_rating=release.content_rating,
            cover_image_url=release.cover_image_url,
            cover_image_key=release.cover_image_key,
            media=[self._tv_release_media_response(row) for row in media],
            episode_mappings=[
                self._tv_release_episode_map_response(row) for row in episode_mappings
            ],
        )

    def _tv_series_response(self, series: TVSeries) -> TVSeriesV1Response:
        media = sorted(
            [media for release in series.releases or [] for media in (release.media or [])],
            key=lambda row: (
                row.media_number is None,
                row.media_number or 0,
                str(row.id),
            ),
        )
        seasons = [
            self._tv_season_response(season)
            for season in sorted(series.seasons or [], key=lambda row: (row.season_number, str(row.id)))
        ]
        contributions = sorted(
            [contrib for release in series.releases or [] for contrib in (release.contributions or [])],
            key=lambda c: (
                c.sequence is None,
                c.sequence or 0,
                c.role.casefold(),
                str(c.person_id),
            ),
        )
        identifiers = sorted(
            [identifier for release in series.releases or [] for identifier in (release.identifiers or [])],
            key=lambda i: (
                i.identifier_type.casefold(),
                (i.normalized_value or i.value or "").casefold(),
                str(i.id),
            ),
        )
        return TVSeriesV1Response(
            id=series.id,
            title=series.title,
            sort_title=series.sort_title,
            description=series.overview,
            original_language=series.original_language,
            original_air_date=series.first_air_date,
            end_date=series.last_air_date,
            status=series.status,
            season_count=series.season_count or len(seasons),
            episode_count=series.episode_count or sum(len(season.episodes) for season in seasons),
            network=series.network,
            seasons=seasons,
            media=[self._tv_release_media_response(row) for row in media],
            contributions=[self._tv_contributor_response(row) for row in contributions],
            identifiers=[self._tv_identifier_response(row) for row in identifiers],
            character_appearances=[],
        )

    def _tv_contributor_response(self, contrib: TVReleaseContribution) -> TVContributorResponse:
        return TVContributorResponse(
            id=contrib.id,
            person_id=contrib.person_id,
            name=contrib.person.name if contrib.person is not None else "",
            role=contrib.role,
            sequence=contrib.sequence,
            image_url=contrib.person.image_url if contrib.person is not None else None,
        )

    def _tv_identifier_response(self, identifier: TVReleaseIdentifier) -> TVIdentifierResponse:
        return TVIdentifierResponse(
            id=identifier.id,
            identifier_type=identifier.identifier_type,
            value=identifier.value,
            is_primary=identifier.is_primary,
        )
