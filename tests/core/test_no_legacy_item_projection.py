from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.base import Base


@pytest.mark.asyncio
async def test_legacy_item_projection_tables_and_fks_do_not_exist(migrated_database):
    assert "items" not in Base.metadata.tables
    assert "editions" not in Base.metadata.tables
    assert "variants" not in Base.metadata.tables

    async with AsyncSessionLocal() as db:
        tables = {
            row[0]
            for row in (
                await db.execute(
                    text(
                        """
                        select table_name
                        from information_schema.tables
                        where table_schema = 'public'
                        """
                    )
                )
            ).all()
        }

        assert "items" not in tables
        assert "editions" not in tables
        assert "variants" not in tables
        provider_ingest_columns = {
            row[0]
            for row in (
                await db.execute(
                    text(
                        """
                        select column_name
                        from information_schema.columns
                        where table_schema = 'public'
                          and table_name = 'provider_ingest_jobs'
                        """
                    )
                )
            ).all()
        }
        assert "resolved_entity_type" in provider_ingest_columns
        assert "resolved_entity_id" in provider_ingest_columns
        assert "item_id" not in provider_ingest_columns

        fk_rows = (
            await db.execute(
                text(
                    """
                    select con.conname
                    from pg_constraint con
                    join pg_class rel on rel.oid = con.conrelid
                    join pg_class frel on frel.oid = con.confrelid
                    join pg_namespace fnsp on fnsp.oid = frel.relnamespace
                    where con.contype = 'f'
                      and fnsp.nspname = 'public'
                      and frel.relname = 'items'
                    """
                )
            )
        ).all()

        assert fk_rows == []


def test_app_does_not_reference_legacy_projection_models_or_routes():
    app_dir = Path(__file__).resolve().parents[2] / "app"
    legacy_names = {"Item", "Edition", "Variant"}
    import_violations: list[str] = []
    route_violations: list[str] = []

    for path in app_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "/metadata/items" in text:
            route_violations.append(str(path))
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            module = node.module or ""
            if not module.startswith("app.models"):
                continue
            for alias in node.names:
                if alias.name in legacy_names:
                    import_violations.append(f"{path}:{alias.name}")

    assert route_violations == []
    assert import_violations == []


def test_fastapi_routes_do_not_start_with_metadata_items():
    routes = [
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
    ]
    assert all(not path.startswith("/metadata/items") for path in routes)


def test_metadata_service_is_thin_and_uses_response_builder_mixin():
    app_dir = Path(__file__).resolve().parents[2] / "app"
    facade_service = (app_dir / "services" / "facade.py").read_text(encoding="utf-8")
    response_builders = (
        app_dir / "services" / "metadata" / "metadata_response_builders.py"
    ).read_text(encoding="utf-8")

    builder_files = {
        "metadata_builders_comics.py": ["_comic_contributor_response", "_comic_issue_response", "_comic_work_response"],
        "metadata_builders_manga.py": ["_manga_series_response", "_manga_chapter_response", "_manga_work_response"],
        "metadata_builders_anime.py": ["_anime_series_response", "_anime_episode_response", "_anime_contributor_response"],
        "metadata_builders_movies.py": ["_movie_work_response", "_movie_release_response", "_movie_release_media_response"],
        "metadata_builders_music.py": ["_music_release_response", "_music_media_response", "_music_track_response"],
        "metadata_builders_tv.py": ["_tv_series_response", "_tv_season_response", "_tv_episode_response"],
    }
    for filename, markers in builder_files.items():
        content = (app_dir / "services" / "metadata" / filename).read_text(encoding="utf-8")
        for marker in markers:
            assert marker in content

    for marker in [marker for markers in builder_files.values() for marker in markers] + ["async def get_item("]:
        assert marker not in facade_service
        assert marker not in response_builders

    metadata_routes = app_dir / "api" / "routes" / "metadata"
    for path in metadata_routes.rglob("*.py"):
        assert "/metadata/items" not in path.read_text(encoding="utf-8")
