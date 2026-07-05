from __future__ import annotations

from app.models import MusicMedia, MusicRelease, MusicReleaseContribution, MusicReleaseIdentifier, MusicTrack
from app.schemas import (
    MusicContributorResponse,
    MusicIdentifierResponse,
    MusicMediaV1Response,
    MusicReleaseV1Response,
    MusicTrackV1Response,
)


class MusicMetadataResponseBuilders:
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
            for media in sorted(release.media, key=lambda row: (row.media_number, str(row.id))):
                media_list.append(self._music_media_response(media))

        return MusicReleaseV1Response(
            id=release.id,
            title=release.title,
            sort_title=release.sort_title,
            subtitle=release.subtitle,
            release_status=release.release_status,
            release_date=release.release_date,
            recording_date=release.recording_date,
            track_count=track_count,
            expected_media_count=release.expected_media_count,
            owned_media_count=release.owned_media_count,
            missing_media_count=release.missing_media_count,
            missing_disc_numbers=release.missing_disc_numbers or [],
            publisher=release.publisher,
            studio=release.studio,
            upc=release.upc,
            catalog_number=release.catalog_number,
            barcode=release.barcode,
            country_code=release.country_code,
            language=release.language,
            cover_image_url=release.cover_image_url,
            cover_image_key=release.cover_image_key,
            local_cover_image_path=release.local_cover_image_path,
            local_back_image_path=release.local_back_image_path,
            local_thumbnail_image_path=release.local_thumbnail_image_path,
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
            expected_track_count=media.expected_track_count,
            owned_track_count=media.owned_track_count,
            missing_track_count=media.missing_track_count,
            missing_track_positions=media.missing_track_positions or [],
            toc=media.toc,
            cddb_id=media.cddb_id,
            leadout_offset=media.leadout_offset,
            bp_disc_id=media.bp_disc_id,
            packaging=media.packaging,
            media_condition=media.media_condition,
            sound_type=media.sound_type,
            vinyl_color=media.vinyl_color,
            vinyl_weight=media.vinyl_weight,
            rpm=media.rpm,
            spars=media.spars,
            tracks=[self._music_track_response(track) for track in sorted(
                media.tracks or [],
                key=lambda track: (track.position.casefold(), str(track.id)),
            )],
        )

    def _music_track_response(self, track: MusicTrack) -> MusicTrackV1Response:
        return MusicTrackV1Response(
            id=track.id,
            media_id=track.media_id,
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

    def _music_contributor_response(self, contrib: MusicReleaseContribution) -> MusicContributorResponse:
        return MusicContributorResponse(
            person_id=contrib.person_id,
            name=contrib.person.name if contrib.person is not None else "",
            role=contrib.role,
            sequence=contrib.sequence,
            image_url=contrib.person.image_url if contrib.person is not None else None,
            role_id=contrib.role_id,
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
