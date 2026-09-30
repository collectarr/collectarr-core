from __future__ import annotations

from datetime import date

from app.models import (
        ComicContribution,
        ComicIdentifier,
        ComicIssue,
        ComicVariant,
        ComicWork,
)
from app.models.partial_date import partial_date_from_storage
from app.schemas import (
        ComicCharacterResponse,
        ComicContributorResponse,
        ComicIdentifierResponse,
        ComicIssueV1Response,
        ComicStoryArcResponse,
        ComicVariantV1Response,
        ComicWorkV1Response,
)


class ComicMetadataResponseBuilders:
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
                image_url=person.image_url if person is not None else None,
                scope=scope,
                role_id=contribution.role_id,
            )

        def _comic_identifier_response(self, identifier: ComicIdentifier) -> ComicIdentifierResponse:
            return ComicIdentifierResponse(
                id=identifier.id,
                identifier_type=identifier.identifier_type,
                value=identifier.value,
                normalized_value=identifier.normalized_value,
                is_primary=identifier.is_primary,
            )

        def _comic_variant_response(self, variant: ComicVariant) -> ComicVariantV1Response:
            return ComicVariantV1Response(
                id=variant.id,
                issue_id=variant.issue_id,
                variant_name=variant.variant_name,
                variant_type=variant.variant_type,
                cover_label=variant.cover_label,
                printing_number=variant.printing_number,
                publisher=variant.publisher,
                imprint=variant.imprint,
                publication_date=variant.publication_date,
                publication_date_parts=partial_date_from_storage(variant.publication_date_parts),
                release_date=variant.release_date,
                release_date_parts=partial_date_from_storage(variant.release_date_parts),
                language=variant.language,
                region=variant.region,
                physical_format=variant.physical_format,
                catalog_number=variant.catalog_number,
                barcode=variant.barcode,
                cover_image_url=variant.cover_image_url,
                cover_image_key=variant.cover_image_key,
                description=variant.description,
            )

        def _comic_issue_response(self, issue: ComicIssue) -> ComicIssueV1Response:
            return ComicIssueV1Response(
                id=issue.id,
                work_id=issue.work_id,
                issue_number=issue.issue_number,
                display_title=issue.display_title,
                publication_date=issue.publication_date,
                publication_date_parts=partial_date_from_storage(issue.publication_date_parts),
                release_date=issue.release_date,
                release_date_parts=partial_date_from_storage(issue.release_date_parts),
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
                key_comic=issue.key_comic,
                key_reason=issue.key_reason,
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
                        image_url=row.character.image_url if row.character is not None else None,
                        sort_name=row.character.canonical_name if row.character is not None else None,
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
                variants=[
                    self._comic_variant_response(row)
                    for row in sorted(
                        issue.variants or [],
                        key=lambda row: (
                            row.release_date is None,
                            row.release_date or date.max,
                            row.variant_name or "",
                            str(row.id),
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
                first_publication_date_parts=partial_date_from_storage(work.first_publication_date_parts),
                expected_issue_count=work.expected_issue_count,
                missing_issue_count=work.missing_issue_count,
                missing_issue_numbers=[
                    entry.issue_number
                    for entry in sorted(
                        work.missing_issue_entries,
                        key=lambda row: row.position,
                    )
                ],
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
