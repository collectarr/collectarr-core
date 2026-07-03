from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.models import (
    ComicCharacterAppearance,
    ComicContribution,
    ComicIdentifier,
    ComicIssue,
    ComicStoryArcMembership,
    ComicWork,
)
from app.models.base import ItemKind
from app.schemas.metadata_shared import SearchResult


class ComicsService:
    async def _search_comic_works(
        self,
        *,
        query: str | None,
        series: str | None,
        issue_number: str | None,
        publisher: str | None,
        imprint: str | None,
        language: str | None,
        country: str | None,
        release_status: str | None,
        year: int | None,
        barcode: str | None,
        limit: int,
    ) -> list[SearchResult]:
        stmt = (
            select(ComicWork)
            .options(
                selectinload(ComicWork.issues)
                .selectinload(ComicIssue.contributions)
                .selectinload(ComicContribution.person),
                selectinload(ComicWork.issues).selectinload(ComicIssue.identifiers),
                selectinload(ComicWork.issues)
                .selectinload(ComicIssue.character_appearances)
                .selectinload(ComicCharacterAppearance.character),
                selectinload(ComicWork.issues)
                .selectinload(ComicIssue.story_arc_memberships)
                .selectinload(ComicStoryArcMembership.story_arc),
            )
            .order_by(ComicWork.sort_title.asc().nullslast(), ComicWork.title.asc())
            .limit(limit)
        )
        pattern = f"%{query.strip()}%" if query and query.strip() else None
        if pattern:
            stmt = stmt.where(
                or_(
                    ComicWork.title.ilike(pattern),
                    ComicIssue.issue_number.ilike(pattern),
                    ComicIssue.display_title.ilike(pattern),
                    ComicIssue.publisher.ilike(pattern),
                    ComicIssue.imprint.ilike(pattern),
                )
            )
        if series and series.strip():
            stmt = stmt.where(ComicWork.title.ilike(f"%{series.strip()}%"))
        if issue_number and issue_number.strip():
            stmt = stmt.where(ComicIssue.issue_number.ilike(f"%{issue_number.strip()}%"))
        if publisher and publisher.strip():
            stmt = stmt.where(ComicIssue.publisher.ilike(f"%{publisher.strip()}%"))
        if imprint and imprint.strip():
            stmt = stmt.where(ComicIssue.imprint.ilike(f"%{imprint.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(ComicIssue.language.ilike(f"%{language.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(ComicIssue.region.ilike(f"%{country.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(ComicIssue.release_status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(func.extract("year", ComicIssue.release_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode(barcode)
            stmt = stmt.where(self._normalized_barcode_expr(ComicIdentifier.value) == normalized)
        rows = list(
            (
                await self.db.execute(
                    stmt.join(ComicWork.issues, isouter=True).join(ComicIssue.identifiers, isouter=True)
                )
            )
            .scalars()
            .unique()
        )
        return [self._comic_search_result(work) for work in rows]

    def _comic_search_result(self, work: ComicWork, *, issue: ComicIssue | None = None) -> SearchResult:
        issues = sorted(
            work.issues or [],
            key=lambda row: (
                row.publication_date is None,
                row.publication_date or date.max,
                row.issue_number is None,
                row.issue_number or "",
                str(row.id),
            ),
        )
        primary = issue or (issues[0] if issues else None)
        creators: list[dict[str, object]] = []
        if primary is not None:
            for row in primary.contributions or []:
                if row.person is None:
                    continue
                creators.append({"name": row.person.name, "role": row.role})
        return SearchResult(
            id=work.id,
            kind=ItemKind.comic,
            title=work.title,
            item_number=primary.issue_number if primary is not None else None,
            synopsis=work.description,
            cover_image_url=primary.cover_image_url if primary is not None else None,
            publisher=primary.publisher if primary is not None else None,
            release_date=primary.release_date if primary is not None else None,
            release_year=primary.release_date.year if primary is not None and primary.release_date else None,
            barcode=next(
                (
                    identifier.value
                    for identifier in (primary.identifiers or [])
                    if identifier.identifier_type in {"upc", "ean", "isbn10", "isbn13", "provider_item_id"}
                ),
                None,
            )
            if primary is not None
            else None,
            variant=primary.display_title if primary is not None else None,
            series_title=work.title,
            volume_name=work.title,
            creators=creators or None,
            characters=[
                row.character.name
                for row in (primary.character_appearances or [])
                if row.character is not None and row.character.name
            ]
            if primary is not None
            else None,
            story_arcs=[
                row.story_arc.name
                for row in (primary.story_arc_memberships or [])
                if row.story_arc is not None and row.story_arc.name
            ]
            if primary is not None
            else None,
            page_count=primary.page_count if primary is not None else None,
            cover_price_cents=primary.cover_price_cents if primary is not None else None,
            currency=primary.currency if primary is not None else None,
            country=primary.region if primary is not None else None,
            release_status=primary.release_status if primary is not None else None,
            language=primary.language if primary is not None else None,
            imprint=primary.imprint if primary is not None else None,
        )

    async def _comic_work_by_barcode(self, barcode: str) -> tuple[ComicWork, ComicIssue | None] | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        row = (
            await self.db.execute(
                select(ComicWork, ComicIssue)
                .join(ComicWork.issues)
                .join(ComicIssue.identifiers)
                .where(self._normalized_barcode_expr(ComicIdentifier.value) == normalized)
                .options(
                    selectinload(ComicWork.issues)
                    .selectinload(ComicIssue.contributions)
                    .selectinload(ComicContribution.person),
                    selectinload(ComicWork.issues).selectinload(ComicIssue.identifiers),
                    selectinload(ComicWork.issues)
                    .selectinload(ComicIssue.character_appearances)
                    .selectinload(ComicCharacterAppearance.character),
                    selectinload(ComicWork.issues)
                    .selectinload(ComicIssue.story_arc_memberships)
                    .selectinload(ComicStoryArcMembership.story_arc),
                )
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        return row[0], row[1]
