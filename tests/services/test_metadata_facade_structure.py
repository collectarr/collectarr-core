from pathlib import Path


def test_metadata_facade_is_thin_and_uses_response_builders():
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
