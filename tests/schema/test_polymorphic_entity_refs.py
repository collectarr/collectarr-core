import pytest
from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.models import (
    BundleRelease,
    BundleReleaseComponent,
    ComicItem,
    MovieItem,
    MusicItem,
)
from app.models.base import ItemKind
from app.models.catalog_game_item import GameItem
from app.models.catalog_tv_item import TvItem
from app.models.entity_refs import DEFAULT_ENTITY_REF_REGISTRY


def _entity_table(entity_type: str) -> str:
    table_name = DEFAULT_ENTITY_REF_REGISTRY.table_name(entity_type)
    assert table_name is not None, f"unexpected entity_type {entity_type!r}"
    return table_name


def test_music_entity_refs_target_the_flat_catalog():
    assert _entity_table("catalog_music_item") == "music_items"
    assert not DEFAULT_ENTITY_REF_REGISTRY.is_known("music_item_disc")
    assert not DEFAULT_ENTITY_REF_REGISTRY.is_known("music_item_track")
    assert not DEFAULT_ENTITY_REF_REGISTRY.is_known("music_release_group")
    assert not DEFAULT_ENTITY_REF_REGISTRY.is_known("music_release")
    assert not DEFAULT_ENTITY_REF_REGISTRY.is_known("music_medium")
    assert not DEFAULT_ENTITY_REF_REGISTRY.is_known("music_track")


def test_movie_entity_refs_target_the_flat_catalog():
    assert _entity_table("catalog_movie_item") == "movie_items"
    assert not DEFAULT_ENTITY_REF_REGISTRY.is_known("movie_work")
    assert not DEFAULT_ENTITY_REF_REGISTRY.is_known("movie_release")


def test_comic_entity_refs_target_the_flat_catalog():
    assert _entity_table("catalog_comic_item") == "comic_items"
    assert not DEFAULT_ENTITY_REF_REGISTRY.is_known("comic_work")
    assert not DEFAULT_ENTITY_REF_REGISTRY.is_known("comic_issue")
    assert not DEFAULT_ENTITY_REF_REGISTRY.is_known("comic_variant")


def test_game_and_board_game_entity_refs_target_flat_catalog_items():
    assert _entity_table("catalog_game_item") == "game_items"
    assert _entity_table("catalog_boardgame_item") == "boardgame_items"
    assert not DEFAULT_ENTITY_REF_REGISTRY.is_known("game_work")
    assert not DEFAULT_ENTITY_REF_REGISTRY.is_known("game_release")
    assert not DEFAULT_ENTITY_REF_REGISTRY.is_known("boardgame_work")
    assert not DEFAULT_ENTITY_REF_REGISTRY.is_known("boardgame_edition")


async def _assert_rows_reference_existing_entities(
    db,
    *,
    source_table: str,
    where_clause: str = "",
) -> None:
    stmt = f"select entity_type, entity_id from {source_table} {where_clause}"
    rows = (await db.execute(text(stmt))).all()
    for entity_type, entity_id in rows:
        table_name = _entity_table(entity_type)
        exists = await db.execute(
            text(f"select 1 from {table_name} where id = :entity_id limit 1"),
            {"entity_id": entity_id},
        )
        assert exists.first() is not None, (
            f"missing {entity_type} row for {source_table}.entity_id={entity_id}"
        )


@pytest.mark.asyncio
async def test_entity_aliases_reference_existing_entities(schema_database):
    async with AsyncSessionLocal() as db:
        await _assert_rows_reference_existing_entities(db, source_table="entity_aliases")


@pytest.mark.asyncio
async def test_entity_links_reference_existing_entities(schema_database):
    async with AsyncSessionLocal() as db:
        await _assert_rows_reference_existing_entities(db, source_table="entity_links")


@pytest.mark.asyncio
async def test_bundle_release_components_reference_existing_entities(schema_database):
    async with AsyncSessionLocal() as db:
        await _assert_rows_reference_existing_entities(db, source_table="bundle_release_components")


@pytest.mark.asyncio
async def test_bundle_release_components_support_multiple_entity_types(schema_database):
    async with AsyncSessionLocal() as db:
        movie_item = MovieItem(title="Movie Item", details={})
        tv_item = TvItem(title="TV Item", details={})
        music_item = MusicItem(title="Music Item")
        comic_item = ComicItem(title="Comic Item", details={})
        game_item = GameItem(title="Game Item", details={})
        bundle = BundleRelease(kind=ItemKind.music, title="Mixed Bundle")
        db.add_all([movie_item, tv_item, music_item, comic_item, game_item, bundle])
        await db.flush()

        movie_media = MovieItemMedia(movie_item_id=movie_item.id, media_number=1)
        tv_media = TvItemMedia(
            item=tv_item,
            position=0,
            media_number=1,
            details={"media_type": "disc"},
        )
        db.add_all([movie_media, tv_media])
        await db.flush()

        tv_episode = TvItemEpisode(
            item=tv_item,
            position=0,
            season_number=1,
            episode_number=1,
            title="Pilot",
            details={},
        )
        db.add(tv_episode)
        await db.flush()

        db.add_all(
            [
                BundleReleaseComponent(
                    bundle_release_id=bundle.id,
                    entity_type="catalog_movie_item",
                    entity_id=movie_item.id,
                    role="edition",
                    sequence_number=1,
                    is_primary=True,
                ),
                BundleReleaseComponent(
                    bundle_release_id=bundle.id,
                    entity_type="catalog_tv_item",
                    entity_id=tv_item.id,
                    role="edition",
                    sequence_number=2,
                ),
                BundleReleaseComponent(
                    bundle_release_id=bundle.id,
                    entity_type="catalog_music_item",
                    entity_id=music_item.id,
                    role="item",
                    sequence_number=3,
                ),
                BundleReleaseComponent(
                    bundle_release_id=bundle.id,
                    entity_type="catalog_comic_item",
                    entity_id=comic_item.id,
                    role="issue",
                    sequence_number=4,
                ),
                BundleReleaseComponent(
                    bundle_release_id=bundle.id,
                    entity_type="catalog_game_item",
                    entity_id=game_item.id,
                    role="edition",
                    sequence_number=5,
                ),
            ]
        )
        await db.commit()

        rows = (
            await db.execute(
                text(
                    """
                    select entity_type, role, sequence_number
                    from bundle_release_components
                    where bundle_release_id = :bundle_id
                    order by sequence_number
                    """
                ),
                {"bundle_id": bundle.id},
            )
        ).all()

        assert [row[0] for row in rows] == [
            "catalog_movie_item",
            "catalog_tv_item",
            "music_item_track",
            "catalog_comic_item",
            "catalog_game_item",
        ]


@pytest.mark.asyncio
async def test_entity_organizations_reference_existing_entities(schema_database):
    async with AsyncSessionLocal() as db:
        await _assert_rows_reference_existing_entities(db, source_table="entity_organizations")


@pytest.mark.asyncio
async def test_entity_persons_reference_existing_entities(schema_database):
    async with AsyncSessionLocal() as db:
        await _assert_rows_reference_existing_entities(db, source_table="entity_persons")


@pytest.mark.asyncio
async def test_entity_tags_reference_existing_entities(schema_database):
    async with AsyncSessionLocal() as db:
        await _assert_rows_reference_existing_entities(db, source_table="entity_tags")
