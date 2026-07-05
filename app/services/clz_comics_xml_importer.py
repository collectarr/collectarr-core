from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Character,
    ComicCharacter,
    ComicCharacterAppearance,
    ComicContribution,
    ComicIssue,
    ComicSeries,
    ComicSeriesMembership,
    ComicWork,
)
from app.models.canonical_support import Person


@dataclass(frozen=True)
class ClzComicCreator:
    name: str
    role: str
    role_id: str | None = None
    sequence: int | None = None
    image_url: str | None = None
    sort_name: str | None = None
    external_ids: dict[str, Any] | None = None


@dataclass(frozen=True)
class ClzComicCharacter:
    name: str
    role: str = "featured"
    image_url: str | None = None
    sort_name: str | None = None
    external_ids: dict[str, Any] | None = None


@dataclass(frozen=True)
class ClzComicRecord:
    title: str
    series_title: str
    issue_number: str | None
    publisher: str | None
    format_label: str | None
    country: str | None
    language: str | None
    release_date: str | None
    summary: str | None
    value_cents: int | None
    value_currency: str | None
    grade: str | None
    grading_company: str | None
    raw_or_slabbed: str | None
    storage_box: str | None
    key_comic: bool
    key_reason: str | None
    local_image_path: str | None
    expected_issue_count: int | None
    owned_issue_count: int | None
    missing_issue_count: int | None
    missing_issue_numbers: list[int]
    creators: list[ClzComicCreator]
    characters: list[ClzComicCharacter]
    metadata_json: dict[str, Any]


class ClzComicsXmlImporter:
    def parse(self, xml_text: str) -> list[ClzComicRecord]:
        root = ElementTree.fromstring(xml_text)
        records: list[ClzComicRecord] = []
        if root.tag.lower() in {"comicinfo", "comic"}:
            records.append(self._parse_record(root))
            return records
        for node in root:
            if node.tag.lower() in {"comic", "issue", "comicinfo"}:
                records.append(self._parse_record(node))
        if not records:
            records.append(self._parse_record(root))
        return records

    async def import_xml(self, db: AsyncSession, xml_text: str) -> int:
        records = self.parse(xml_text)
        imported = 0
        series_cache: dict[str, ComicSeries] = {}
        for record in records:
            series = series_cache.get(record.series_title)
            if series is None:
                series = await self._get_or_create_series(db, record.series_title, record.metadata_json)
                series_cache[record.series_title] = series

            work = await self._get_or_create_work(db, series, record)
            issue = await self._get_or_create_issue(db, work, record)
            await self._replace_issue_relations(db, issue, record)
            self._apply_series_counts(series, record)
            imported += 1

        await db.commit()
        return imported

    def _parse_record(self, node: ElementTree.Element) -> ClzComicRecord:
        title = self._text(node, "Title") or self._text(node, "Series") or "Unknown comic"
        series_title = self._text(node, "Series") or title
        issue_number = self._text(node, "Number") or self._text(node, "IssueNumber")
        release_date = self._date_text(node)
        local_image_path = self._first_text(
            node,
            "LocalImagePath",
            "ImagePath",
            "ImageFile",
            "CoverImagePath",
            "FrontCoverPath",
            "BackCoverPath",
        )
        creators = [
            self._parse_creator(creator)
            for creator in self._child_nodes(node, "Creators", "Creator", "Contributors", "Contributor")
        ]
        characters = [
            self._parse_character(character)
            for character in self._child_nodes(node, "Characters", "Character")
        ]
        missing_numbers = self._parse_missing_issue_numbers(node)
        metadata_json = {
            "import_source": "clz_xml",
            "publisher_icon": self._first_text(node, "PublisherIcon", "PublisherImage"),
            "format_icon": self._first_text(node, "FormatIcon", "FormatImage", "TemplateImage"),
            "country_icon": self._first_text(node, "CountryIcon", "CountryImage", "CountryScaledImage"),
            "language_icon": self._first_text(node, "LanguageIcon", "LanguageImage", "LanguageScaledImage"),
            "local_image_path": local_image_path,
        }
        return ClzComicRecord(
            title=title,
            series_title=series_title,
            issue_number=issue_number,
            publisher=self._text(node, "Publisher"),
            format_label=self._text(node, "Format"),
            country=self._text(node, "Country"),
            language=self._text(node, "Language"),
            release_date=release_date,
            summary=self._text(node, "Summary") or self._text(node, "Plot"),
            value_cents=self._parse_money_cents(node),
            value_currency=self._text(node, "ValueCurrency") or self._text(node, "Currency"),
            grade=self._text(node, "Grade"),
            grading_company=self._text(node, "GradingCompany"),
            raw_or_slabbed=self._text(node, "RawOrSlabbed"),
            storage_box=self._text(node, "StorageBox"),
            key_comic=self._bool_text(node, "KeyComic"),
            key_reason=self._text(node, "KeyReason"),
            local_image_path=local_image_path,
            expected_issue_count=self._parse_int(node, "IssueCount"),
            owned_issue_count=self._parse_int(node, "OwnedIssueCount"),
            missing_issue_count=self._parse_int(node, "MissingIssueCount"),
            missing_issue_numbers=missing_numbers,
            creators=creators,
            characters=characters,
            metadata_json=metadata_json,
        )

    async def _get_or_create_series(
        self,
        db: AsyncSession,
        title: str,
        metadata_json: dict[str, Any],
    ) -> ComicSeries:
        existing = (await db.execute(select(ComicSeries).where(ComicSeries.title == title))).scalar_one_or_none()
        if existing is not None:
            if existing.metadata_json is None:
                existing.metadata_json = metadata_json
            return existing
        series = ComicSeries(title=title, slug=self._slug(title), metadata_json=metadata_json)
        db.add(series)
        await db.flush()
        return series

    async def _get_or_create_work(
        self,
        db: AsyncSession,
        series: ComicSeries,
        record: ClzComicRecord,
    ) -> ComicWork:
        existing = (
            await db.execute(
                select(ComicWork).where(
                    ComicWork.volume_id.is_(None),
                    ComicWork.title == series.title,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.description = existing.description or record.summary
            existing.expected_issue_count = record.expected_issue_count
            existing.owned_issue_count = record.owned_issue_count
            existing.missing_issue_count = record.missing_issue_count
            existing.missing_issue_numbers = record.missing_issue_numbers or None
            return existing
        work = ComicWork(
            title=series.title,
            sort_title=self._slug(series.title),
            description=record.summary,
            original_language=record.language,
            first_publication_date=None,
            expected_issue_count=record.expected_issue_count,
            owned_issue_count=record.owned_issue_count,
            missing_issue_count=record.missing_issue_count,
            missing_issue_numbers=record.missing_issue_numbers or None,
            metadata_json=record.metadata_json,
        )
        db.add(work)
        await db.flush()
        return work

    async def _get_or_create_issue(
        self,
        db: AsyncSession,
        work: ComicWork,
        record: ClzComicRecord,
    ) -> ComicIssue:
        existing = None
        if record.issue_number:
            existing = (
                await db.execute(
                    select(ComicIssue).where(
                        ComicIssue.work_id == work.id,
                        ComicIssue.issue_number == record.issue_number,
                    )
                )
            ).scalar_one_or_none()
        if existing is not None:
            self._apply_issue_fields(existing, record)
            return existing
        issue = ComicIssue(work_id=work.id, issue_number=record.issue_number)
        self._apply_issue_fields(issue, record)
        db.add(issue)
        await db.flush()
        return issue

    async def _replace_issue_relations(
        self,
        db: AsyncSession,
        issue: ComicIssue,
        record: ClzComicRecord,
    ) -> None:
        await db.execute(delete(ComicContribution).where(ComicContribution.issue_id == issue.id))
        await db.execute(delete(ComicCharacterAppearance).where(ComicCharacterAppearance.issue_id == issue.id))
        for index, creator in enumerate(record.creators, start=1):
            person = await self._get_or_create_person(db, creator)
            db.add(
                ComicContribution(
                    issue_id=issue.id,
                    person_id=person.id,
                    role=creator.role,
                    role_id=creator.role_id,
                    sequence=creator.sequence or index,
                    metadata_json={
                        "image_url": creator.image_url,
                        "sort_name": creator.sort_name,
                        "external_ids": creator.external_ids,
                    },
                )
            )
        for character_data in record.characters:
            character = await self._get_or_create_character(db, character_data)
            comic_character = await self._get_or_create_comic_character(db, character_data)
            db.add(
                ComicCharacterAppearance(
                    issue_id=issue.id,
                    character_id=character.id,
                    role=character_data.role,
                )
            )
            db.add(
                comic_character
            )
        await db.flush()

    async def _get_or_create_person(self, db: AsyncSession, creator: ClzComicCreator) -> Person:
        existing = (await db.execute(select(Person).where(Person.name == creator.name))).scalar_one_or_none()
        if existing is not None:
            if not existing.sort_name and creator.sort_name:
                existing.sort_name = creator.sort_name
            if not existing.external_ids and creator.external_ids:
                existing.external_ids = creator.external_ids
            if not existing.image_url and creator.image_url:
                existing.image_url = creator.image_url
            return existing
        person = Person(
            name=creator.name,
            sort_name=creator.sort_name,
            image_url=creator.image_url,
            external_ids=creator.external_ids,
        )
        db.add(person)
        await db.flush()
        return person

    async def _get_or_create_character(self, db: AsyncSession, character: ClzComicCharacter) -> Character:
        existing = (await db.execute(select(Character).where(Character.name == character.name))).scalar_one_or_none()
        if existing is not None:
            if not existing.canonical_name and character.sort_name:
                existing.canonical_name = character.sort_name
            if not existing.image_url and character.image_url:
                existing.image_url = character.image_url
            return existing
        row = Character(
            name=character.name,
            canonical_name=character.sort_name,
            image_url=character.image_url,
            metadata_json={"external_ids": character.external_ids} if character.external_ids else None,
        )
        db.add(row)
        await db.flush()
        return row

    async def _get_or_create_comic_character(
        self,
        db: AsyncSession,
        character: ClzComicCharacter,
    ) -> ComicCharacter:
        existing = (await db.execute(select(ComicCharacter).where(ComicCharacter.name == character.name))).scalar_one_or_none()
        if existing is not None:
            return existing
        row = ComicCharacter(
            name=character.name,
            sort_name=character.sort_name,
            image_url=character.image_url,
            external_ids=character.external_ids,
        )
        db.add(row)
        await db.flush()
        return row

    def _apply_issue_fields(self, issue: ComicIssue, record: ClzComicRecord) -> None:
        issue.display_title = record.title
        issue.publisher = record.publisher
        issue.language = record.language
        issue.region = record.country
        issue.release_status = None
        issue.cover_image_url = None
        issue.cover_image_key = None
        issue.local_image_path = record.local_image_path
        issue.value_cents = record.value_cents
        issue.value_currency = record.value_currency
        issue.grade = record.grade
        issue.grading_company = record.grading_company
        issue.raw_or_slabbed = record.raw_or_slabbed
        issue.storage_box = record.storage_box
        issue.key_comic = record.key_comic
        issue.key_reason = record.key_reason
        issue.description = record.summary
        issue.metadata_json = {
            **(issue.metadata_json or {}),
            **record.metadata_json,
            "format_label": record.format_label,
            "release_date": record.release_date,
        }

    def _apply_series_counts(self, series: ComicSeries, record: ClzComicRecord) -> None:
        if record.expected_issue_count is not None:
            series.expected_issue_count = record.expected_issue_count
        if record.owned_issue_count is not None:
            series.owned_issue_count = record.owned_issue_count
        if record.missing_issue_count is not None:
            series.missing_issue_count = record.missing_issue_count
        if record.missing_issue_numbers:
            series.missing_issue_numbers = record.missing_issue_numbers

    def _parse_creator(self, node: ElementTree.Element) -> ClzComicCreator:
        return ClzComicCreator(
            name=self._text(node, "Name") or self._text(node, "name") or self._text(node, "Creator") or "Unknown creator",
            role=self._text(node, "Role") or self._text(node, "role") or "creator",
            role_id=self._text(node, "RoleId") or self._text(node, "role_id") or self._text(node, "roleId"),
            sequence=self._parse_int(node, "Sequence"),
            image_url=self._text(node, "ImageUrl") or self._text(node, "image_url"),
            sort_name=self._text(node, "SortName") or self._text(node, "sort_name"),
            external_ids=self._parse_external_ids(node),
        )

    def _parse_character(self, node: ElementTree.Element) -> ClzComicCharacter:
        return ClzComicCharacter(
            name=self._text(node, "Name") or self._text(node, "name") or "Unknown character",
            role=self._text(node, "Role") or self._text(node, "role") or "featured",
            image_url=self._text(node, "ImageUrl") or self._text(node, "image_url"),
            sort_name=self._text(node, "SortName") or self._text(node, "sort_name"),
            external_ids=self._parse_external_ids(node),
        )

    def _parse_external_ids(self, node: ElementTree.Element) -> dict[str, Any] | None:
        values: dict[str, Any] = {}
        clz_core_id = self._text(node, "CoreId") or self._text(node, "coreid")
        imdb_name_id = self._text(node, "ImdbNameId") or self._text(node, "imdb_name_id")
        if clz_core_id:
            values["clz_core_id"] = clz_core_id
        if imdb_name_id:
            values["imdb_name_id"] = imdb_name_id
        return values or None

    def _parse_missing_issue_numbers(self, node: ElementTree.Element) -> list[int]:
        text = self._first_text(node, "MissingIssueNumbers", "MissingIssues")
        if not text:
            return []
        values: list[int] = []
        for chunk in text.replace("#", "").split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            if "-" in chunk:
                left, right = chunk.split("-", 1)
                left_num = self._int_text(left)
                right_num = self._int_text(right)
                if left_num is None or right_num is None:
                    continue
                values.extend(range(left_num, right_num + 1))
                continue
            parsed = self._int_text(chunk)
            if parsed is not None:
                values.append(parsed)
        return sorted(set(values))

    def _child_nodes(self, root: ElementTree.Element, *names: str) -> list[ElementTree.Element]:
        nodes: list[ElementTree.Element] = []
        wanted = {name.lower() for name in names}
        for node in list(root):
            tag = node.tag.lower()
            if tag in {"creators", "contributors", "characters"}:
                for child in list(node):
                    if child.tag.lower() in wanted:
                        nodes.append(child)
                continue
            if tag in wanted:
                nodes.append(node)
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
        return self._int_text(text)

    def _int_text(self, text: str | None) -> int | None:
        if text is None:
            return None
        try:
            return int(text.strip())
        except ValueError:
            return None

    def _parse_money_cents(self, node: ElementTree.Element) -> int | None:
        text = self._text(node, "Value") or self._text(node, "ValueCents")
        if text is None:
            return None
        normalized = text.strip().replace("$", "").replace(",", "")
        try:
            return int(round(float(normalized) * 100))
        except ValueError:
            return None

    def _bool_text(self, node: ElementTree.Element, name: str) -> bool:
        text = self._text(node, name)
        return text is not None and text.strip().lower() in {"1", "true", "yes", "y"}

    def _date_text(self, node: ElementTree.Element) -> str | None:
        year = self._parse_int(node, "Year")
        if year is None:
            return None
        month = self._parse_int(node, "Month") or 1
        day = self._parse_int(node, "Day") or 1
        return f"{year:04d}-{month:02d}-{day:02d}"

    def _slug(self, value: str) -> str | None:
        slug = "-".join(part for part in value.lower().split() if part)
        return slug or None
