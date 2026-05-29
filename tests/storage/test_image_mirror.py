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
    )

    assert key.startswith("covers/comicvine/4000-12345/")
    assert key.endswith(".webp")


def test_image_mirror_creates_bounded_webp_cover():
    mirror = ImageMirror(storage=None)
    source = BytesIO()
    Image.new("RGB", (900, 1400), color=(20, 80, 140)).save(source, format="PNG")

    cover = mirror._normalized_cover_bytes(source.getvalue())

    with Image.open(BytesIO(cover)) as image:
        assert image.format == "WEBP"
        assert max(image.size) <= mirror.settings.provider_image_max_long_edge


def test_normalized_cover_includes_phash():
    mirror = ImageMirror(storage=None)
    source = BytesIO()
    Image.new("RGB", (400, 600), color=(100, 50, 200)).save(source, format="PNG")

    cover = mirror._normalized_cover(source.getvalue())

    assert cover.phash is not None
    # phash is a 16-char hex string (64-bit hash)
    assert len(cover.phash) == 16
    int(cover.phash, 16)  # must be valid hex


def test_image_mirror_does_not_upscale_small_covers():
    mirror = ImageMirror(storage=None)
    source = BytesIO()
    Image.new("RGB", (200, 300), color=(20, 80, 140)).save(source, format="PNG")

    cover = mirror._normalized_cover_bytes(source.getvalue())

    with Image.open(BytesIO(cover)) as image:
        assert image.size == (200, 300)


@pytest.mark.asyncio
async def test_image_mirror_stores_single_normalized_webp_cover(monkeypatch):
    storage = FakeStorage()
    mirror = ImageMirror(storage=storage)
    source = BytesIO()
    Image.new("RGB", (900, 1400), color=(20, 80, 140)).save(source, format="PNG")

    async def fake_download_image(source_url: str) -> bytes:
        assert source_url == "https://example.test/cover.png"
        return source.getvalue()

    monkeypatch.setattr(mirror, "_download_image", fake_download_image)

    result = await mirror.mirror_cover_best_effort(
        "https://example.test/cover.png",
        "comicvine",
        "4000-12345",
    )

    assert result is not None
    assert result.content_type == "image/webp"
    assert result.source_url == "https://example.test/cover.png"
    assert result.provider == "comicvine"
    assert result.provider_item_id == "4000-12345"
    assert result.size_bytes > 0
    assert result.width < 900
    assert result.height == mirror.settings.provider_image_max_long_edge
    assert len(result.content_hash) == 64
    assert result.thumbnail_key is None
    assert result.thumbnail_url is None
    assert result.phash is not None
    assert len(result.phash) == 16
    assert len(storage.objects) == 1
    stored_body, stored_content_type = next(iter(storage.objects.values()))
    assert stored_content_type == "image/webp"
    with Image.open(BytesIO(stored_body)) as image:
        assert image.format == "WEBP"


def test_image_mirror_rejects_non_image_bytes():
    mirror = ImageMirror(storage=None)

    with pytest.raises(ValueError, match="valid image"):
        mirror._validate_image_bytes(b"<html>not an image</html>")


def test_image_mirror_rejects_images_over_pixel_limit(monkeypatch):
    mirror = ImageMirror(storage=None)
    monkeypatch.setattr(mirror.settings, "max_image_pixels", 100)
    source = BytesIO()
    Image.new("RGB", (20, 20), color=(20, 80, 140)).save(source, format="PNG")

    with pytest.raises(ValueError, match="pixel limit"):
        mirror._validate_image_bytes(source.getvalue())


@pytest.mark.asyncio
async def test_image_mirror_returns_none_for_missing_source_url():
    mirror = ImageMirror(storage=None)

    result = await mirror.mirror_cover_best_effort(None, "comicvine", "4000-12345")

    assert result is None
