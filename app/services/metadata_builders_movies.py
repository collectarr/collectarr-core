from __future__ import annotations

from datetime import date

from app.models import (
        MovieRelease,
        MovieReleaseMedia,
        MovieWork,
        MovieWorkContribution,
        MovieWorkIdentifier,
)
from app.schemas import (
        MovieContributorResponse,
        MovieIdentifierResponse,
        MovieReleaseMediaResponse,
        MovieReleaseV1Response,
        MovieWorkV1Response,
)
from app.services.metadata_helpers import _metadata_links


class MovieMetadataResponseBuilders:
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
                image_url=contrib.person.image_url if contrib.person is not None else None,
                character_name=contrib.character_name,
            )

        def _movie_identifier_response(self, identifier: MovieWorkIdentifier) -> MovieIdentifierResponse:
            return MovieIdentifierResponse(
                id=identifier.id,
                identifier_type=identifier.identifier_type,
                value=identifier.value,
                is_primary=identifier.is_primary,
            )
