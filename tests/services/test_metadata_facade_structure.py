from pathlib import Path


def test_metadata_facade_is_thin_and_uses_response_builders():
    app_dir = Path(__file__).resolve().parents[2] / "app"
    facade_service = (app_dir / "services" / "facade.py").read_text(encoding="utf-8")
    response_builders = (
        app_dir / "services" / "metadata" / "metadata_response_builders.py"
    ).read_text(encoding="utf-8")

    builder_files = {
        "metadata_builders_tv.py": ["_tv_series_response", "_tv_season_response", "_tv_episode_response"],
    }
    for filename, markers in builder_files.items():
        content = (app_dir / "services" / "metadata" / filename).read_text(encoding="utf-8")
        for marker in markers:
            assert marker in content

    assert not (app_dir / "services" / "movies_service.py").exists()
    assert not (app_dir / "services" / "metadata" / "metadata_builders_movies.py").exists()
    assert not (app_dir / "services" / "metadata" / "metadata_builders_comics.py").exists()

    for marker in [marker for markers in builder_files.values() for marker in markers] + ["async def get_item("]:
        assert marker not in facade_service
        assert marker not in response_builders
