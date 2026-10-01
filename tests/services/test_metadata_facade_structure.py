from pathlib import Path


def test_metadata_facade_is_thin_and_uses_response_builders():
    app_dir = Path(__file__).resolve().parents[2] / "app"
    facade_service = (app_dir / "services" / "facade.py").read_text(encoding="utf-8")
    response_builders = (
        app_dir / "services" / "metadata" / "metadata_response_builders.py"
    ).read_text(encoding="utf-8")

    assert not (app_dir / "services" / "movies_service.py").exists()
    assert not (app_dir / "services" / "metadata" / "metadata_builders_movies.py").exists()
    assert not (app_dir / "services" / "metadata" / "metadata_builders_comics.py").exists()
    assert not (app_dir / "services" / "tv_service.py").exists()
    assert not (app_dir / "services" / "metadata" / "metadata_builders_tv.py").exists()

    for marker in ["async def get_item(", "get_tv_release", "get_tv_series"]:
        assert marker not in facade_service
        assert marker not in response_builders
