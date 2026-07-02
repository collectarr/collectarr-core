from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models import (
    BoardGameEdition,
    BoardGameWork,
    BookEdition,
    BookWork,
    Edition,
    GameRelease,
    GameWork,
    Item,
    MusicMedia,
    MusicRelease,
    MusicTrack,
    Variant,
)
from app.models.base import ExternalProvider, ItemKind
from app.providers.base import NormalizedCredit, NormalizedItem, NormalizedTrack
from app.services.admin_domains.provider_ingest import AdminProviderIngestService


async def _noop_async(*args, **kwargs):
    return None


def _service(db):
    return AdminProviderIngestService(
        db=db,
        settings=SimpleNamespace(
            mirror_provider_images=False,
            mirror_provider_images_allow_restricted=False,
        ),
        providers=SimpleNamespace(),
        provider_preview_state=SimpleNamespace(invalidate=_noop_async),
        history_reader=lambda: iter(()),
        audit_recorder=lambda *args, **kwargs: None,
        ingest_job_audit_details=lambda job: {},
        record_ingest_history=lambda **kwargs: None,
        is_retryable_ingest_error=lambda error: False,
        error_message=lambda error: str(error),
        reindex_items=_noop_async,
        item_response_loader=lambda item: item,
        backoff_delay=lambda attempts: None,
        actor_user_id=None,
        comicvine_character_details={},
    )


async def _legacy_projection_counts(db):
    return {
        "items": await db.scalar(select(func.count()).select_from(Item)),
        "editions": await db.scalar(select(func.count()).select_from(Edition)),
        "variants": await db.scalar(select(func.count()).select_from(Variant)),
    }


@pytest.mark.asyncio
async def test_book_ingest_writes_canonical_tables_only():
    async with AsyncSessionLocal() as db:
        service = _service(db)
        await service._create_book_work_from_normalized(
            provider=SimpleNamespace(capabilities=SimpleNamespace(allows_image_mirroring=False), is_configured=True),
            provider_name=ExternalProvider.openlibrary,
            provider_item_id="book-1",
            provider_raw={"id": "book-1"},
            normalized=NormalizedItem(
                kind=ItemKind.book,
                title="The Fellowship of the Ring",
                item_number="1",
                synopsis="A hobbit begins the journey.",
                series_title="The Lord of the Rings",
                edition_title="The Fellowship of the Ring",
                edition_format="Hardcover",
                publisher="George Allen & Unwin",
                release_date=date(1954, 7, 29),
                isbn="9780261103573",
                barcode="9780261103573",
                page_count=423,
                release_status="released",
                language="en",
                creators=[NormalizedCredit(name="J.R.R. Tolkien", role="author")],
                provider_ids={"openlibrary": "book-1"},
            ),
        )

        legacy_counts = await _legacy_projection_counts(db)
        assert legacy_counts == {"items": 0, "editions": 0, "variants": 0}
        assert await db.scalar(select(func.count()).select_from(BookWork)) == 1
        assert await db.scalar(select(func.count()).select_from(BookEdition)) == 1


@pytest.mark.asyncio
async def test_game_ingest_writes_canonical_tables_only():
    async with AsyncSessionLocal() as db:
        service = _service(db)
        await service._create_game_work_from_normalized(
            provider=SimpleNamespace(capabilities=SimpleNamespace(allows_image_mirroring=False), is_configured=True),
            provider_name=ExternalProvider.igdb,
            provider_item_id="game-1",
            provider_raw={"id": "game-1"},
            normalized=NormalizedItem(
                kind=ItemKind.game,
                title="The Legend of Zelda: Breath of the Wild",
                synopsis="An open-world adventure.",
                release_date=date(2017, 3, 3),
                publisher="Nintendo",
                edition_title="Nintendo Switch Release",
                edition_format="physical",
                platforms=["Nintendo Switch"],
                genres=["adventure"],
                barcode="045496590420",
                catalog_number="HAC P AABPA",
                release_status="released",
                language="en",
                country="US",
                age_rating="E10+",
                creators=[NormalizedCredit(name="Nintendo EPD", role="developer")],
                provider_ids={"igdb": "game-1"},
            ),
        )

        legacy_counts = await _legacy_projection_counts(db)
        assert legacy_counts == {"items": 0, "editions": 0, "variants": 0}
        assert await db.scalar(select(func.count()).select_from(GameWork)) == 1
        assert await db.scalar(select(func.count()).select_from(GameRelease)) == 1


@pytest.mark.asyncio
async def test_boardgame_ingest_writes_canonical_tables_only():
    async with AsyncSessionLocal() as db:
        service = _service(db)
        await service._create_boardgame_work_from_normalized(
            provider=SimpleNamespace(capabilities=SimpleNamespace(allows_image_mirroring=False), is_configured=True),
            provider_name=ExternalProvider.bgg,
            provider_item_id="boardgame-1",
            provider_raw={"id": "boardgame-1"},
            normalized=NormalizedItem(
                kind=ItemKind.boardgame,
                title="Catan",
                synopsis="Settle the island of Catan.",
                release_date=date(1995, 1, 1),
                publisher="Kosmos",
                edition_title="First Edition",
                edition_format="box",
                barcode="4002051699955",
                catalog_number="6995",
                release_status="released",
                language="de",
                country="DE",
                age_rating="8+",
                min_players=3,
                max_players=4,
                playing_time_minutes=90,
                min_age=10,
                creators=[NormalizedCredit(name="Klaus Teuber", role="designer")],
                provider_ids={"bgg": "boardgame-1"},
            ),
        )

        legacy_counts = await _legacy_projection_counts(db)
        assert legacy_counts == {"items": 0, "editions": 0, "variants": 0}
        assert await db.scalar(select(func.count()).select_from(BoardGameWork)) == 1
        assert await db.scalar(select(func.count()).select_from(BoardGameEdition)) == 1


@pytest.mark.asyncio
async def test_music_ingest_writes_canonical_tables_only():
    async with AsyncSessionLocal() as db:
        service = _service(db)
        await service._create_music_release_from_normalized(
            provider=SimpleNamespace(capabilities=SimpleNamespace(allows_image_mirroring=False), is_configured=True),
            provider_name=ExternalProvider.musicbrainz,
            provider_item_id="music-1",
            provider_raw={"id": "music-1"},
            normalized=NormalizedItem(
                kind=ItemKind.music,
                title="Abbey Road",
                subtitle="Stereo",
                release_date=date(1969, 9, 26),
                release_status="released",
                publisher="Apple Records",
                studio="EMI",
                catalog_number="PCS 7088",
                barcode="049800048807",
                country="GB",
                language="en",
                track_count=2,
                edition_format="vinyl",
                creators=[NormalizedCredit(name="The Beatles", role="performer")],
                tracks=[
                    NormalizedTrack(position=1, title="Come Together", duration_seconds=259, disc_number=1),
                    NormalizedTrack(position=2, title="Something", duration_seconds=182, disc_number=1),
                ],
                provider_ids={"musicbrainz": "music-1"},
            ),
        )

        legacy_counts = await _legacy_projection_counts(db)
        assert legacy_counts == {"items": 0, "editions": 0, "variants": 0}
        assert await db.scalar(select(func.count()).select_from(MusicRelease)) == 1
        assert await db.scalar(select(func.count()).select_from(MusicMedia)) == 1
        assert await db.scalar(select(func.count()).select_from(MusicTrack)) == 2
