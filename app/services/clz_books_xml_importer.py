from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BookContribution, BookEdition, BookSeries, BookSeriesMembership, BookWork
from app.models.canonical_support import Person


@dataclass(frozen=True)
class ClzBookCreator:
    name: str
    role: str
    role_id: str | None = None
    sequence: int | None = None
    image_url: str | None = None
    sort_name: str | None = None
    biography: str | None = None
    external_ids: dict[str, Any] | None = None


@dataclass(frozen=True)
class ClzBookRecord:
    title: str
    series_title: str
    issue_number: str | None
    publisher: str | None
    format_label: str | None
    country: str | None
    language: str | None
    release_date: str | None
    summary: str | None
    original_language: str | None
    original_publication_date: str | None
    original_publisher: str | None
    dewey: str | None
    lccn: str | None
    loc_control_number: str | None
    page_count: int | None
    isbn: str | None
    barcode: str | None
    subtitle: str | None
    dimensions: str | None
    dust_jacket: bool | None
    printing: str | None
    first_edition: bool | None
    number_line: str | None
    creators: list[ClzBookCreator]
    metadata_json: dict[str, Any]


class ClzBooksXmlImporter:
    def parse(self, xml_text: str) -> list[ClzBookRecord]:
        root = ElementTree.fromstring(xml_text)
        records: list[ClzBookRecord] = []
        if root.tag.lower() in {"book", "bookinfo", "books"}:
            if root.tag.lower() == "books":
                records.extend(self._parse_record(node) for node in root if node.tag.lower() in {"book", "bookinfo"})
            else:
                records.append(self._parse_record(root))
            return records
        for node in root:
            if node.tag.lower() in {"book", "bookinfo"}:
                records.append(self._parse_record(node))
        if not records:
            records.append(self._parse_record(root))
        return records

    async def import_xml(self, db: AsyncSession, xml_text: str) -> int:
        records = self.parse(xml_text)
        imported = 0
        series_cache: dict[str, BookSeries] = {}
        for record in records:
            series = series_cache.get(record.series_title)
            if series is None:
                series = await self._get_or_create_series(db, record.series_title, record.metadata_json)
                series_cache[record.series_title] = series
            work = await self._get_or_create_work(db, series, record)
            edition = await self._get_or_create_edition(db, work, record)
            await self._ensure_membership(db, work, series, record)
            await self._replace_contributions(db, edition, record)
            imported += 1
        await db.commit()
        return imported

    def _parse_record(self, node: ElementTree.Element) -> ClzBookRecord:
        title = self._text(node, "Title") or self._text(node, "Series") or "Unknown book"
        series_title = self._text(node, "Series") or title
        creators = [self._parse_creator(creator) for creator in self._child_nodes(node, "Creators", "Creator", "Contributors", "Contributor", "Authors", "Author")]
        metadata_json = {
            "import_source": "clz_xml",
            "cover_icon": self._first_text(node, "CoverIcon", "CoverImage", "TemplateImage"),
        }
        return ClzBookRecord(
            title=title,
            series_title=series_title,
            issue_number=self._text(node, "Number") or self._text(node, "IssueNumber"),
            publisher=self._text(node, "Publisher"),
            format_label=self._text(node, "Format") or self._text(node, "Binding"),
            country=self._text(node, "Country"),
            language=self._text(node, "Language"),
            release_date=self._date_text(node, "ReleaseDate") or self._date_text(node, "PublicationDate"),
            summary=self._text(node, "Summary") or self._text(node, "Plot") or self._text(node, "Synopsis"),
            original_language=self._text(node, "OriginalLanguage") or self._text(node, "OriginalLang"),
            original_publication_date=self._date_text(node, "OriginalPublicationDate"),
            original_publisher=self._text(node, "OriginalPublisher"),
            dewey=self._text(node, "Dewey"),
            lccn=self._text(node, "LCCN"),
            loc_control_number=self._text(node, "LocControlNumber") or self._text(node, "LoCControlNumber"),
            page_count=self._parse_int(node, "PageCount"),
            isbn=self._text(node, "ISBN") or self._text(node, "Isbn"),
            barcode=self._text(node, "Barcode"),
            subtitle=self._text(node, "Subtitle"),
            dimensions=self._text(node, "Dimensions"),
            dust_jacket=self._bool_text(node, "DustJacket"),
            printing=self._text(node, "Printing"),
            first_edition=self._bool_text(node, "FirstEdition"),
            number_line=self._text(node, "NumberLine"),
            creators=creators,
            metadata_json=metadata_json,
        )

    async def _get_or_create_series(
        self,
        db: AsyncSession,
        title: str,
        metadata_json: dict[str, Any],
    ) -> BookSeries:
        existing = (await db.execute(select(BookSeries).where(BookSeries.title == title))).scalar_one_or_none()
        if existing is not None:
            if existing.metadata_json is None:
                existing.metadata_json = metadata_json
            return existing
        series = BookSeries(title=title, slug=self._slug(title), metadata_json=metadata_json)
        db.add(series)
        await db.flush()
        return series

    async def _get_or_create_work(
        self,
        db: AsyncSession,
        series: BookSeries,
        record: ClzBookRecord,
    ) -> BookWork:
        existing = (
            await db.execute(
                select(BookWork).where(
                    BookWork.title == series.title,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.description = existing.description or record.summary
            existing.original_language = existing.original_language or record.original_language
            existing.original_publication_date = existing.original_publication_date or self._date_value(
                record.original_publication_date
            )
            existing.original_publisher = existing.original_publisher or record.original_publisher
            existing.dewey = existing.dewey or record.dewey
            existing.lccn = existing.lccn or record.lccn
            existing.loc_control_number = existing.loc_control_number or record.loc_control_number
            return existing
        work = BookWork(
            title=series.title,
            sort_title=self._slug(series.title),
            subtitle=record.subtitle,
            description=record.summary,
            original_language=record.original_language,
            original_publication_date=self._date_value(record.original_publication_date),
            first_publication_date=self._date_value(record.release_date),
            original_publisher=record.original_publisher,
            dewey=record.dewey,
            lccn=record.lccn,
            loc_control_number=record.loc_control_number,
            metadata_json=record.metadata_json,
        )
        db.add(work)
        await db.flush()
        return work

    async def _get_or_create_edition(
        self,
        db: AsyncSession,
        work: BookWork,
        record: ClzBookRecord,
    ) -> BookEdition:
        existing = (
            await db.execute(
                select(BookEdition).where(
                    BookEdition.work_id == work.id,
                    BookEdition.display_title == record.title,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            self._apply_edition_fields(existing, record)
            return existing
        edition = BookEdition(work_id=work.id, display_title=record.title)
        self._apply_edition_fields(edition, record)
        db.add(edition)
        await db.flush()
        return edition

    async def _replace_contributions(
        self,
        db: AsyncSession,
        edition: BookEdition,
        record: ClzBookRecord,
    ) -> None:
        await db.execute(delete(BookContribution).where(BookContribution.edition_id == edition.id))
        for index, creator in enumerate(record.creators, start=1):
            person = await self._get_or_create_person(db, creator)
            db.add(
                BookContribution(
                    edition_id=edition.id,
                    person_id=person.id,
                    role=creator.role,
                    sequence=creator.sequence or index,
                    metadata_json={
                        "role_id": creator.role_id,
                        "image_url": creator.image_url,
                        "sort_name": creator.sort_name,
                        "biography": creator.biography,
                        "external_ids": creator.external_ids,
                    },
                )
            )
        await db.flush()

    async def _ensure_membership(
        self,
        db: AsyncSession,
        work: BookWork,
        series: BookSeries,
        record: ClzBookRecord,
    ) -> None:
        existing = (
            await db.execute(
                select(BookSeriesMembership).where(
                    BookSeriesMembership.work_id == work.id,
                    BookSeriesMembership.series_id == series.id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return
        sequence: float | None = None
        if record.issue_number:
            try:
                sequence = float(record.issue_number)
            except ValueError:
                sequence = None
        db.add(
            BookSeriesMembership(
                work_id=work.id,
                series_id=series.id,
                sequence=sequence,
                display_number=record.issue_number or record.title,
                metadata_json={},
            )
        )

    async def _get_or_create_person(self, db: AsyncSession, creator: ClzBookCreator) -> Person:
        existing = (await db.execute(select(Person).where(Person.name == creator.name))).scalar_one_or_none()
        if existing is not None:
            if not existing.sort_name and creator.sort_name:
                existing.sort_name = creator.sort_name
            if not existing.biography and creator.biography:
                existing.biography = creator.biography
            if not existing.image_url and creator.image_url:
                existing.image_url = creator.image_url
            if creator.external_ids:
                merged = dict(existing.external_ids or {})
                for key, value in creator.external_ids.items():
                    if value and not merged.get(key):
                        merged[key] = value
                if merged != (existing.external_ids or {}):
                    existing.external_ids = merged
            if not existing.description and creator.biography:
                existing.description = creator.biography
            return existing
        person = Person(
            name=creator.name,
            sort_name=creator.sort_name,
            biography=creator.biography,
            description=creator.biography,
            image_url=creator.image_url,
            external_ids=creator.external_ids,
        )
        db.add(person)
        await db.flush()
        return person

    def _apply_edition_fields(self, edition: BookEdition, record: ClzBookRecord) -> None:
        edition.edition_statement = record.subtitle
        edition.format = record.format_label
        edition.binding = record.format_label
        edition.publication_date = self._date_value(record.release_date)
        edition.publisher = record.publisher
        edition.imprint = record.original_publisher
        edition.language = record.language
        edition.region = record.country
        edition.page_count = record.page_count
        edition.age_rating = None
        edition.release_status = None
        edition.dimensions = record.dimensions
        edition.dust_jacket = record.dust_jacket
        edition.printing = record.printing
        edition.first_edition = record.first_edition
        edition.number_line = record.number_line
        edition.description = record.summary
        edition.metadata_json = {
            **(edition.metadata_json or {}),
            **record.metadata_json,
            "isbn": record.isbn,
            "barcode": record.barcode,
        }

    def _parse_creator(self, node: ElementTree.Element) -> ClzBookCreator:
        return ClzBookCreator(
            name=self._text(node, "Name") or self._text(node, "Creator") or "Unknown creator",
            role=self._text(node, "Role") or "Author",
            role_id=self._text(node, "RoleId") or self._text(node, "role_id"),
            sequence=self._parse_int(node, "Sequence"),
            image_url=self._text(node, "ImageUrl"),
            sort_name=self._text(node, "SortName"),
            biography=self._text(node, "Biography") or self._text(node, "Bio"),
            external_ids=self._parse_external_ids(node),
        )

    def _parse_external_ids(self, node: ElementTree.Element) -> dict[str, Any] | None:
        values: dict[str, Any] = {}
        clz_core_id = self._text(node, "CoreId") or self._text(node, "coreid")
        if clz_core_id:
            values["clz_core_id"] = clz_core_id
        imdb_name_id = self._text(node, "ImdbNameId") or self._text(node, "imdb_name_id")
        if imdb_name_id:
            values["imdb_name_id"] = imdb_name_id
        return values or None

    def _child_nodes(self, root: ElementTree.Element, *names: str) -> list[ElementTree.Element]:
        nodes: list[ElementTree.Element] = []
        wanted = {name.lower() for name in names}
        for node in list(root):
            tag = node.tag.lower()
            if tag in wanted:
                nodes.append(node)
                continue
            if tag in {"creators", "contributors", "authors"}:
                nodes.extend(child for child in list(node) if child.tag.lower() in wanted)
        return nodes

    def _text(self, node: ElementTree.Element, name: str) -> str | None:
        for child in node.iter():
            if child.tag.lower() == name.lower():
                text = (child.text or "").strip()
                if text:
                    return text
        return None

    def _first_text(self, node: ElementTree.Element, *names: str) -> str | None:
        for name in names:
            text = self._text(node, name)
            if text:
                return text
        return None

    def _parse_int(self, node: ElementTree.Element, name: str) -> int | None:
        text = self._text(node, name)
        if text is None:
            return None
        try:
            return int(text.strip())
        except ValueError:
            return None

    def _bool_text(self, node: ElementTree.Element, name: str) -> bool | None:
        text = self._text(node, name)
        if text is None:
            return None
        normalized = text.strip().lower()
        if normalized in {"1", "true", "yes", "y"}:
            return True
        if normalized in {"0", "false", "no", "n"}:
            return False
        return None

    def _date_text(self, node: ElementTree.Element, name: str) -> str | None:
        return self._text(node, name)

    def _date_value(self, value: str | None):
        from datetime import date

        if not value:
            return None
        text = value.strip()
        if len(text) == 4 and text.isdigit():
            return date(int(text), 1, 1)
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None

    def _slug(self, value: str) -> str:
        return " ".join(value.split()).strip()
