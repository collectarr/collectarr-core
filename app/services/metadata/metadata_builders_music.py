from __future__ import annotations

from app.models import (
    MusicMedium,
    MusicRelease,
    MusicReleaseContribution,
    MusicReleaseGroup,
    MusicReleaseIdentifier,
    MusicTrack,
)
from app.schemas import (
    MusicContributorResponse,
    MusicIdentifierResponse,
    MusicMediumV1Response,
    MusicReleaseGroupV1Response,
    MusicReleaseSummaryV1Response,
    MusicReleaseV1Response,
    MusicTrackV1Response,
)


class MusicMetadataResponseBuilders:
    def _music_release_group_response(
        self, group: MusicReleaseGroup
    ) -> MusicReleaseGroupV1Response:
        releases = sorted(
            group.releases or [],
            key=lambda row: (
                row.release_date is None,
                row.release_date,
                row.title.casefold(),
                str(row.id),
            ),
        )
        return MusicReleaseGroupV1Response(
            id=group.id,
            title=group.title,
            sort_title=group.sort_title,
            original_title=group.original_title,
            synopsis=group.synopsis,
            artist=group.artist,
            original_release_date=group.original_release_date,
            recording_date=group.recording_date,
            studio=group.studio,
            is_live=group.is_live,
            genres=group.genres or [],
            cover_image_url=group.cover_image_url,
            cover_image_key=group.cover_image_key,
            releases=[self._music_release_summary_response(row) for row in releases],
        )

    def _music_release_summary_response(
        self, release: MusicRelease
    ) -> MusicReleaseSummaryV1Response:
        return MusicReleaseSummaryV1Response(
            id=release.id,
            release_group_id=release.release_group_id,
            title=release.title,
            release_date=release.release_date,
            release_type=release.release_type,
            release_status=release.release_status,
            publisher=release.publisher,
            barcode=release.barcode or release.upc,
            catalog_number=release.catalog_number,
            cover_image_url=release.cover_image_url,
        )

    def _music_release_response(self, release: MusicRelease) -> MusicReleaseV1Response:
        return MusicReleaseV1Response(
            id=release.id,
            release_group_id=release.release_group_id,
            title=release.title,
            sort_title=release.sort_title,
            subtitle=release.subtitle,
            release_status=release.release_status,
            release_date=release.release_date,
            release_type=release.release_type,
            publisher=release.publisher,
            upc=release.upc,
            catalog_number=release.catalog_number,
            barcode=release.barcode,
            country_code=release.country_code,
            language=release.language,
            packaging=release.packaging,
            cover_image_url=release.cover_image_url,
            cover_image_key=release.cover_image_key,
            mediums=[
                self._music_medium_response(row)
                for row in sorted(
                    release.mediums or [], key=lambda row: (row.medium_number, str(row.id))
                )
            ],
            contributions=[
                self._music_contributor_response(row)
                for row in sorted(
                    release.contributions or [],
                    key=lambda row: (
                        row.sequence is None,
                        row.sequence or 0,
                        row.role.casefold(),
                        str(row.person_id),
                    ),
                )
            ],
            identifiers=[
                self._music_identifier_response(row)
                for row in sorted(
                    release.identifiers or [],
                    key=lambda row: (
                        row.identifier_type.casefold(),
                        (row.normalized_value or row.value or '').casefold(),
                        str(row.id),
                    ),
                )
            ],
        )

    def _music_medium_response(self, medium: MusicMedium) -> MusicMediumV1Response:
        return MusicMediumV1Response(
            id=medium.id,
            release_id=medium.release_id,
            medium_number=medium.medium_number,
            medium_type=medium.medium_type,
            title=medium.title,
            track_count=medium.track_count,
            expected_track_count=medium.expected_track_count,
            missing_track_count=medium.missing_track_count,
            missing_track_positions=medium.missing_track_positions or [],
            toc=medium.toc,
            cddb_id=medium.cddb_id,
            leadout_offset=medium.leadout_offset,
            bp_disc_id=medium.bp_disc_id,
            media_condition=medium.media_condition,
            sound_type=medium.sound_type,
            vinyl_color=medium.vinyl_color,
            vinyl_weight=medium.vinyl_weight,
            rpm=medium.rpm,
            spars=medium.spars,
            tracks=[
                self._music_track_response(row)
                for row in sorted(medium.tracks or [], key=lambda row: (row.position.casefold(), str(row.id)))
            ],
        )

    def _music_track_response(self, track: MusicTrack) -> MusicTrackV1Response:
        return MusicTrackV1Response(
            id=track.id,
            medium_id=track.medium_id,
            position=track.position,
            title=track.title,
            duration_ms=track.duration_ms,
            offset_ms=track.offset_ms,
            bitrate_kbps=track.bitrate_kbps,
            file_size_bytes=track.file_size_bytes,
            track_hash=track.track_hash,
            instrument=track.instrument,
            composition=track.composition,
        )

    def _music_contributor_response(self, contribution: MusicReleaseContribution) -> MusicContributorResponse:
        return MusicContributorResponse(
            person_id=contribution.person_id,
            name=contribution.person.name if contribution.person is not None else '',
            role=contribution.role,
            sequence=contribution.sequence,
            image_url=contribution.person.image_url if contribution.person is not None else None,
            role_id=contribution.role_id,
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
