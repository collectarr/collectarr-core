from __future__ import annotations

from datetime import date

from app.models import (
        MangaChapter,
        MangaCharacterAppearance,
        MangaContribution,
        MangaIdentifier,
        MangaSeriesMembership,
        MangaWork,
)
from app.schemas import (
        MangaChapterV1Response,
        MangaCharacterResponse,
        MangaContributorResponse,
        MangaIdentifierResponse,
        MangaSeriesResponse,
        MangaWorkV1Response,
)


class MangaMetadataResponseBuilders:
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
