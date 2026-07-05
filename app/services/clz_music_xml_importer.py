from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MusicMedia, MusicRelease, MusicReleaseContribution, MusicTrack
from app.models.canonical_support import Person


@dataclass(frozen=True)
class ClzMusicCredit:
    name: str
    role: str
    role_id: str | None = None
    sequence: int | None = None
    image_url: str | None = None
    sort_name: str | None = None
    external_ids: dict[str, Any] | None = None


@dataclass(frozen=True)
class ClzMusicTrack:
    position: str
    title: str
    duration_ms: int | None = None
    offset_ms: int | None = None
    bitrate_kbps: int | None = None
    file_size_bytes: int | None = None
    track_hash: str | None = None
    instrument: str | None = None
    composition: str | None = None
    metadata_json: dict[str, Any] | None = None


@dataclass(frozen=True)
class ClzMusicDisc:
    media_number: int
    title: str | None = None
    media_type: str | None = None
    track_count: int | None = None
    expected_track_count: int | None = None
    owned_track_count: int | None = None
    missing_track_count: int | None = None
    missing_track_positions: list[str] | None = None
    toc: str | None = None
    cddb_id: str | None = None
    leadout_offset: int | None = None
    bp_disc_id: str | None = None
    packaging: str | None = None
    media_condition: str | None = None
    sound_type: str | None = None
    vinyl_color: str | None = None
    vinyl_weight: str | None = None
    rpm: int | None = None
    spars: str | None = None
    local_cover_image_path: str | None = None
    local_back_image_path: str | None = None
    local_thumbnail_image_path: str | None = None
    tracks: list[ClzMusicTrack] | None = None
    metadata_json: dict[str, Any] | None = None


@dataclass(frozen=True)
class ClzMusicRecord:
    title: str
    subtitle: str | None
    artist: str | None
    release_type: str | None
    release_status: str | None
    release_date: str | None
    recording_date: str | None
    publisher: str | None
    studio: str | None
    catalog_number: str | None
    upc: str | None
    barcode: str | None
    country_code: str | None
    language: str | None
    track_count: int | None
    expected_media_count: int | None
    owned_media_count: int | None
    missing_media_count: int | None
    missing_disc_numbers: list[int]
    cover_image_url: str | None
    cover_image_key: str | None
    local_cover_image_path: str | None
    local_back_image_path: str | None
    local_thumbnail_image_path: str | None
    extras: str | None
    credits: list[ClzMusicCredit]
    discs: list[ClzMusicDisc]
    metadata_json: dict[str, Any]


class ClzMusicXmlImporter:
    def parse(self, xml_text: str) -> list[ClzMusicRecord]:
        root = ElementTree.fromstring(xml_text)
        if root.tag.lower() in {"music", "release", "album"}:
            return [self._parse_record(root)]
        records = [
            self._parse_record(node)
            for node in list(root)
            if node.tag.lower() in {"music", "release", "album", "disc", "cd"}
        ]
        return records or [self._parse_record(root)]

    async def import_xml(self, db: AsyncSession, xml_text: str) -> int:
        records = self.parse(xml_text)
        imported = 0
        for record in records:
            release = await self._get_or_create_release(db, record)
            await self._replace_children(db, release, record)
            imported += 1
        await db.commit()
        return imported

    def _parse_record(self, node: ElementTree.Element) -> ClzMusicRecord:
        title = self._text(node, "Title") or self._text(node, "Album") or "Unknown release"
        discs = [
            self._parse_disc(disc, index + 1)
            for index, disc in enumerate(self._child_nodes(node, "Discs", "Disc", "Media", "Medium", "CD"))
        ]
        if not discs:
            discs = [self._parse_disc(node, 1)]
        credits = [
            self._parse_credit(credit)
            for credit in self._child_nodes(node, "Credits", "Credit", "Contributors", "Contributor", "Artist")
        ]
        metadata_json = {
            "import_source": "clz_xml",
            "local_cover_image_path": self._first_text(node, "LocalCoverImagePath", "CoverImagePath"),
            "local_back_image_path": self._first_text(node, "LocalBackImagePath", "BackImagePath"),
            "local_thumbnail_image_path": self._first_text(node, "LocalThumbnailImagePath", "ThumbnailImagePath"),
        }
        return ClzMusicRecord(
            title=title,
            subtitle=self._text(node, "Subtitle"),
            artist=self._text(node, "Artist") or self._text(node, "Performer"),
            release_type=self._text(node, "ReleaseType") or self._text(node, "Format"),
            release_status=self._text(node, "ReleaseStatus"),
            release_date=self._date_text(node, "ReleaseDate"),
            recording_date=self._date_text(node, "RecordingDate"),
            publisher=self._text(node, "Label") or self._text(node, "Publisher"),
            studio=self._text(node, "Studio"),
            catalog_number=self._text(node, "CatalogNumber") or self._text(node, "CatNo"),
            upc=self._text(node, "UPC"),
            barcode=self._text(node, "Barcode"),
            country_code=self._text(node, "Country"),
            language=self._text(node, "Language"),
            track_count=self._parse_int(node, "TrackCount"),
            expected_media_count=self._parse_int(node, "DiscCount") or self._parse_int(node, "MediaCount"),
            owned_media_count=self._parse_int(node, "OwnedDiscCount"),
            missing_media_count=self._parse_int(node, "MissingDiscCount"),
            missing_disc_numbers=self._parse_int_list(node, "MissingDiscNumbers"),
            cover_image_url=self._first_text(node, "CoverImageUrl", "FrontCoverUrl"),
            cover_image_key=self._text(node, "CoverImageKey"),
            local_cover_image_path=self._first_text(node, "LocalCoverImagePath", "CoverImagePath"),
            local_back_image_path=self._first_text(node, "LocalBackImagePath", "BackImagePath"),
            local_thumbnail_image_path=self._first_text(node, "LocalThumbnailImagePath", "ThumbnailImagePath"),
            extras=self._text(node, "Notes") or self._text(node, "Extras"),
            credits=credits,
            discs=discs,
            metadata_json=metadata_json,
        )

    def _parse_disc(self, node: ElementTree.Element, media_number: int) -> ClzMusicDisc:
        tracks = [
            self._parse_track(track)
            for track in self._child_nodes(node, "Tracks", "Track")
        ]
        return ClzMusicDisc(
            media_number=self._parse_int(node, "DiscNumber") or self._parse_int(node, "MediaNumber") or media_number,
            title=self._text(node, "Title"),
            media_type=self._text(node, "MediaType") or self._text(node, "Format"),
            track_count=self._parse_int(node, "TrackCount"),
            expected_track_count=self._parse_int(node, "ExpectedTrackCount"),
            owned_track_count=self._parse_int(node, "OwnedTrackCount"),
            missing_track_count=self._parse_int(node, "MissingTrackCount"),
            missing_track_positions=self._parse_string_list(node, "MissingTrackPositions"),
            toc=self._text(node, "TOC"),
            cddb_id=self._text(node, "CDDBId"),
            leadout_offset=self._parse_int(node, "LeadoutOffset"),
            bp_disc_id=self._text(node, "BPDiscId"),
            packaging=self._text(node, "Packaging"),
            media_condition=self._text(node, "MediaCondition"),
            sound_type=self._text(node, "SoundType"),
            vinyl_color=self._text(node, "VinylColor"),
            vinyl_weight=self._text(node, "VinylWeight"),
            rpm=self._parse_int(node, "RPM"),
            spars=self._text(node, "SPARS"),
            local_cover_image_path=self._first_text(node, "LocalCoverImagePath", "CoverImagePath"),
            local_back_image_path=self._first_text(node, "LocalBackImagePath", "BackImagePath"),
            local_thumbnail_image_path=self._first_text(node, "LocalThumbnailImagePath", "ThumbnailImagePath"),
            tracks=tracks,
            metadata_json={
                "import_source": "clz_xml",
                "toc": self._text(node, "TOC"),
                "cddb_id": self._text(node, "CDDBId"),
                "leadout_offset": self._parse_int(node, "LeadoutOffset"),
                "bp_disc_id": self._text(node, "BPDiscId"),
            },
        )

    def _parse_track(self, node: ElementTree.Element) -> ClzMusicTrack:
        return ClzMusicTrack(
            position=self._text(node, "Position") or self._text(node, "TrackNumber") or "1",
            title=self._text(node, "Title") or "Untitled track",
            duration_ms=self._parse_duration_ms(node),
            offset_ms=self._parse_int(node, "OffsetMs") or self._parse_int(node, "Offset"),
            bitrate_kbps=self._parse_int(node, "BitrateKbps") or self._parse_int(node, "Bitrate"),
            file_size_bytes=self._parse_int(node, "FileSizeBytes") or self._parse_int(node, "FileSize"),
            track_hash=self._text(node, "Hash") or self._text(node, "TrackHash"),
            instrument=self._text(node, "Instrument"),
            composition=self._text(node, "Composition"),
            metadata_json={
                "file_path": self._text(node, "FilePath"),
            },
        )

    def _parse_credit(self, node: ElementTree.Element) -> ClzMusicCredit:
        return ClzMusicCredit(
            name=self._text(node, "Name") or self._text(node, "Artist") or "Unknown credit",
            role=self._text(node, "Role") or "credit",
            role_id=self._text(node, "RoleId") or self._text(node, "role_id"),
            sequence=self._parse_int(node, "Sequence"),
            image_url=self._text(node, "ImageUrl"),
            sort_name=self._text(node, "SortName"),
            external_ids=self._parse_external_ids(node),
        )

    async def _get_or_create_release(self, db: AsyncSession, record: ClzMusicRecord) -> MusicRelease:
        existing = (await db.execute(select(MusicRelease).where(MusicRelease.title == record.title))).scalar_one_or_none()
        if existing is not None:
            self._apply_release(existing, record)
            return existing
        release = MusicRelease(title=record.title)
        self._apply_release(release, record)
        db.add(release)
        await db.flush()
        return release

    async def _replace_children(self, db: AsyncSession, release: MusicRelease, record: ClzMusicRecord) -> None:
        await db.execute(delete(MusicReleaseContribution).where(MusicReleaseContribution.release_id == release.id))
        await db.execute(delete(MusicMedia).where(MusicMedia.release_id == release.id))
        for index, credit in enumerate(record.credits, start=1):
            person = await self._get_or_create_person(db, credit)
            db.add(
                MusicReleaseContribution(
                    release_id=release.id,
                    person_id=person.id,
                    role=credit.role,
                    role_id=credit.role_id,
                    sequence=credit.sequence or index,
                    metadata_json={
                        "image_url": credit.image_url,
                        "sort_name": credit.sort_name,
                        "external_ids": credit.external_ids,
                    },
                )
            )
        for disc in record.discs:
            media = MusicMedia(
                release_id=release.id,
                media_number=disc.media_number,
                media_type=disc.media_type,
                title=disc.title,
                track_count=disc.track_count,
                expected_track_count=disc.expected_track_count,
                owned_track_count=disc.owned_track_count,
                missing_track_count=disc.missing_track_count,
                missing_track_positions=disc.missing_track_positions,
                toc=disc.toc,
                cddb_id=disc.cddb_id,
                leadout_offset=disc.leadout_offset,
                bp_disc_id=disc.bp_disc_id,
                packaging=disc.packaging,
                media_condition=disc.media_condition,
                sound_type=disc.sound_type,
                vinyl_color=disc.vinyl_color,
                vinyl_weight=disc.vinyl_weight,
                rpm=disc.rpm,
                spars=disc.spars,
                metadata_json=disc.metadata_json,
            )
            db.add(media)
            await db.flush()
            for track in disc.tracks or []:
                db.add(
                    MusicTrack(
                        media_id=media.id,
                        release_id=release.id,
                        position=track.position,
                        title=track.title,
                        duration_ms=track.duration_ms,
                        offset_ms=track.offset_ms,
                        bitrate_kbps=track.bitrate_kbps,
                        file_size_bytes=track.file_size_bytes,
                        track_hash=track.track_hash,
                        instrument=track.instrument,
                        composition=track.composition,
                        metadata_json=track.metadata_json,
                    )
                )
        await db.flush()

    async def _get_or_create_person(self, db: AsyncSession, credit: ClzMusicCredit) -> Person:
        existing = (await db.execute(select(Person).where(Person.name == credit.name))).scalar_one_or_none()
        if existing is not None:
            if not existing.sort_name and credit.sort_name:
                existing.sort_name = credit.sort_name
            if not existing.external_ids and credit.external_ids:
                existing.external_ids = credit.external_ids
            if not existing.image_url and credit.image_url:
                existing.image_url = credit.image_url
            return existing
        person = Person(
            name=credit.name,
            sort_name=credit.sort_name,
            image_url=credit.image_url,
            external_ids=credit.external_ids,
        )
        db.add(person)
        await db.flush()
        return person

    def _apply_release(self, release: MusicRelease, record: ClzMusicRecord) -> None:
        release.subtitle = record.subtitle
        release.release_type = record.release_type
        release.release_status = record.release_status
        release.release_date = self._date_value(record.release_date)
        release.recording_date = self._date_value(record.recording_date)
        release.media_count = len(record.discs)
        release.expected_media_count = record.expected_media_count
        release.owned_media_count = record.owned_media_count
        release.missing_media_count = record.missing_media_count
        release.missing_disc_numbers = record.missing_disc_numbers or None
        release.track_count = record.track_count
        release.upc = record.upc
        release.cover_image_url = record.cover_image_url
        release.cover_image_key = record.cover_image_key
        release.local_cover_image_path = record.local_cover_image_path
        release.local_back_image_path = record.local_back_image_path
        release.local_thumbnail_image_path = record.local_thumbnail_image_path
        release.publisher = record.publisher
        release.studio = record.studio
        release.country_code = record.country_code
        release.language = record.language
        release.barcode = record.barcode or record.upc
        release.catalog_number = record.catalog_number
        release.extras = record.extras
        release.metadata_json = {
            **(release.metadata_json or {}),
            **record.metadata_json,
            "artist": record.artist,
        }

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
            if tag in {"credits", "contributors", "discs", "media", "tracks"}:
                nodes.extend(
                    child for child in list(node) if child.tag.lower() in wanted
                )
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

    def _parse_int_list(self, node: ElementTree.Element, name: str) -> list[int]:
        text = self._text(node, name)
        if not text:
            return []
        values: list[int] = []
        for chunk in text.replace("#", "").split(","):
            parsed = self._safe_int(chunk)
            if parsed is not None:
                values.append(parsed)
        return sorted(set(values))

    def _parse_string_list(self, node: ElementTree.Element, name: str) -> list[str]:
        text = self._text(node, name)
        if not text:
            return []
        return [chunk.strip() for chunk in text.split(",") if chunk.strip()]

    def _parse_duration_ms(self, node: ElementTree.Element) -> int | None:
        text = self._text(node, "DurationMs") or self._text(node, "Duration")
        if text is None:
            return None
        normalized = text.strip()
        if ":" in normalized:
            parts = normalized.split(":")
            if len(parts) == 2:
                minutes, seconds = parts
                return (self._safe_int(minutes) or 0) * 60_000 + (self._safe_int(seconds) or 0) * 1000
            if len(parts) == 3:
                hours, minutes, seconds = parts
                return ((self._safe_int(hours) or 0) * 3600 + (self._safe_int(minutes) or 0) * 60 + (self._safe_int(seconds) or 0)) * 1000
        parsed = self._safe_int(normalized)
        return parsed * 1000 if parsed is not None else None

    def _date_text(self, node: ElementTree.Element, name: str) -> str | None:
        text = self._text(node, name)
        return text.strip() if text else None

    def _date_value(self, text: str | None):
        from datetime import date

        if not text:
            return None
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None

    def _safe_int(self, value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value.strip())
        except ValueError:
            return None
