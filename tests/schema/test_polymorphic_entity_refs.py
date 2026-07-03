import pytest
from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.models import (
    BundleRelease,
    BundleReleaseComponent,
    ComicIssue,
    ComicWork,
    GameRelease,
    GameWork,
    MovieRelease,
    MovieWork,
    MusicMedia,
    MusicRelease,
    MusicTrack,
    TVEpisode,
    TVRelease,
    TVReleaseMedia,
)
from app.models.base import ItemKind
from app.models.entity_refs import DEFAULT_ENTITY_REF_REGISTRY


def _entity_table(entity_type: str) -> str:
    table_name = DEFAULT_ENTITY_REF_REGISTRY.table_name(entity_type)
    assert table_name is not None, f"unexpected entity_type {entity_type!r}"
    return table_name


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
        assert exists.first() is not None, f"missing {entity_type} row for {source_table}.entity_id={entity_id}"


@pytest.mark.asyncio
async def test_entity_aliases_reference_existing_entities(migrated_database):
    async with AsyncSessionLocal() as db:
        await _assert_rows_reference_existing_entities(db, source_table="entity_aliases")


@pytest.mark.asyncio
async def test_entity_links_reference_existing_entities(migrated_database):
    async with AsyncSessionLocal() as db:
        await _assert_rows_reference_existing_entities(db, source_table="entity_links")


@pytest.mark.asyncio
async def test_bundle_release_components_reference_existing_entities(migrated_database):
    async with AsyncSessionLocal() as db:
        await _assert_rows_reference_existing_entities(db, source_table="bundle_release_components")


@pytest.mark.asyncio
async def test_bundle_release_components_support_multiple_entity_types(migrated_database):
    async with AsyncSessionLocal() as db:
        movie_work = MovieWork(title="Movie Work")
        tv_release = TVRelease(title="TV Release", format="DVD")
        music_release = MusicRelease(title="Music Release")
        comic_work = ComicWork(title="Comic Work")
        game_work = GameWork(title="Game Work")
        bundle = BundleRelease(kind=ItemKind.music, title="Mixed Bundle")
        db.add_all([movie_work, tv_release, music_release, comic_work, game_work, bundle])
        await db.flush()

        movie_release = MovieRelease(work_id=movie_work.id, format="Blu-ray")
        tv_media = TVReleaseMedia(release_id=tv_release.id, media_number=1, media_type="disc")
        music_media = MusicMedia(release_id=music_release.id, media_number=1, media_type="CD")
        comic_issue = ComicIssue(work_id=comic_work.id)
        game_release = GameRelease(work_id=game_work.id)
        db.add_all([movie_release, tv_media, music_media, comic_issue, game_release])
        await db.flush()

        tv_episode = TVEpisode(
            release_id=tv_release.id,
            media_id=tv_media.id,
            series_title="TV Release",
            season_number=1,
            episode_number=1,
            title="Pilot",
        )
        music_track = MusicTrack(
            media_id=music_media.id,
            release_id=music_release.id,
            position="1",
            title="Track 1",
        )
        db.add_all([tv_episode, music_track])
        await db.flush()

        db.add_all(
            [
                BundleReleaseComponent(
                    bundle_release_id=bundle.id,
                    entity_type="movie_release",
                    entity_id=movie_release.id,
                    role="disc",
                    sequence_number=1,
                    is_primary=True,
                ),
                BundleReleaseComponent(
                    bundle_release_id=bundle.id,
                    entity_type="tv_episode",
                    entity_id=tv_episode.id,
                    role="episode",
                    sequence_number=2,
                ),
                BundleReleaseComponent(
                    bundle_release_id=bundle.id,
                    entity_type="music_track",
                    entity_id=music_track.id,
                    role="track",
                    sequence_number=3,
                ),
                BundleReleaseComponent(
                    bundle_release_id=bundle.id,
                    entity_type="comic_issue",
                    entity_id=comic_issue.id,
                    role="issue",
                    sequence_number=4,
                ),
                BundleReleaseComponent(
                    bundle_release_id=bundle.id,
                    entity_type="game_release",
                    entity_id=game_release.id,
                    role="release",
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
            "movie_release",
            "tv_episode",
            "music_track",
            "comic_issue",
            "game_release",
        ]


@pytest.mark.asyncio
async def test_entity_organizations_reference_existing_entities(migrated_database):
    async with AsyncSessionLocal() as db:
        await _assert_rows_reference_existing_entities(db, source_table="entity_organizations")


@pytest.mark.asyncio
async def test_entity_persons_reference_existing_entities(migrated_database):
    async with AsyncSessionLocal() as db:
        await _assert_rows_reference_existing_entities(db, source_table="entity_persons")


@pytest.mark.asyncio
async def test_entity_tags_reference_existing_entities(migrated_database):
    async with AsyncSessionLocal() as db:
        await _assert_rows_reference_existing_entities(db, source_table="entity_tags")
