from io import BytesIO

import pytest
from PIL import Image

from app.storage.images import ImageMirror


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put_object(self, key: str, body: bytes, content_type: str) -> str:
        self.objects[key] = (body, content_type)
        return f"http://storage.test/{key}"


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


def test_image_mirror_builds_stable_thumbnail_key():
    mirror = ImageMirror(storage=None)

    key = mirror._thumbnail_key(
        provider="comicvine",
        provider_item_id="4000-12345",
        source_url="https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg",
    )

    assert key.startswith("thumbnails/comicvine/4000-12345/")
    assert key.endswith(".jpg")


def test_image_mirror_creates_bounded_jpeg_thumbnail():
    storage = FakeStorage()
    mirror = ImageMirror(storage=storage)
    source = BytesIO()
    Image.new("RGB", (900, 1400), color=(20, 80, 140)).save(source, format="PNG")

    thumbnail = mirror._thumbnail_bytes(source.getvalue())

    with Image.open(BytesIO(thumbnail)) as image:
        assert image.format == "JPEG"
        assert image.width <= mirror.settings.thumbnail_max_width
        assert image.height <= mirror.settings.thumbnail_max_width * 2


@pytest.mark.asyncio
async def test_image_mirror_returns_none_for_missing_source_url():
    mirror = ImageMirror(storage=None)

    result = await mirror.mirror_cover_best_effort(None, "comicvine", "4000-12345")

    assert result is None
