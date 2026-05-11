import pytest

from app.storage.images import ImageMirror


def test_image_mirror_builds_stable_cover_key():
    mirror = ImageMirror(storage=None)

    key = mirror._cover_key(
        provider="comicvine",
        provider_item_id="4000-12345",
        source_url="https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg",
        content_type="image/jpeg",
    )

    assert key.startswith("covers/comicvine/4000-12345/")
    assert key.endswith(".jpg")


@pytest.mark.asyncio
async def test_image_mirror_returns_none_for_missing_source_url():
    mirror = ImageMirror(storage=None)

    result = await mirror.mirror_cover_best_effort(None, "comicvine", "4000-12345")

    assert result is None
