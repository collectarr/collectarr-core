import hashlib
import logging
from io import BytesIO
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import get_settings
from app.storage.client import ObjectStorage


_SAFE_SEGMENT_RE = re.compile(r"[^a-zA-Z0-9._-]+")
_SUPPORTED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
_NORMALIZED_COVER_CONTENT_TYPE = "image/webp"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MirroredImage:
    key: str
    url: str
    content_type: str
    thumbnail_key: str | None = None
    thumbnail_url: str | None = None


class ImageMirror:
    def __init__(self, storage: ObjectStorage | None = None) -> None:
        self.settings = get_settings()
        self.storage = storage or ObjectStorage()

    async def mirror_cover_best_effort(
        self, source_url: str | None, provider: str, provider_item_id: str
    ) -> MirroredImage | None:
        if not source_url:
            return None
        try:
            image_bytes = await self._download_image(source_url)
            cover_bytes = self._normalized_cover_bytes(image_bytes)
            key = self._cover_key(provider, provider_item_id, source_url)
            public_url = self.storage.put_object(key, cover_bytes, _NORMALIZED_COVER_CONTENT_TYPE)
        except Exception:
            logger.warning(
                "Failed to mirror provider cover %s for %s:%s",
                source_url,
                provider,
                provider_item_id,
                exc_info=True,
            )
            return None
        return MirroredImage(
            key=key,
            url=public_url,
            content_type=_NORMALIZED_COVER_CONTENT_TYPE,
        )

    async def _download_image(self, source_url: str) -> bytes:
        parsed = urlparse(source_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Unsupported image URL scheme")

        async with httpx.AsyncClient(
            timeout=self.settings.image_download_timeout_seconds
        ) as client:
            async with client.stream("GET", source_url, follow_redirects=True) as response:
                response.raise_for_status()
                content_type = (
                    response.headers.get("content-type", "").split(";")[0].strip().lower()
                )
                if content_type not in _SUPPORTED_IMAGE_TYPES:
                    raise ValueError("Downloaded content is not a supported image")

                image_bytes = bytearray()
                async for chunk in response.aiter_bytes():
                    image_bytes.extend(chunk)
                    if len(image_bytes) > self.settings.max_image_bytes:
                        raise ValueError("Image exceeds configured max size")

        downloaded = bytes(image_bytes)
        self._validate_image_bytes(downloaded)
        return downloaded

    def _cover_key(self, provider: str, provider_item_id: str, source_url: str) -> str:
        cache_identity = "|".join(
            [
                source_url,
                _NORMALIZED_COVER_CONTENT_TYPE,
                str(self.settings.provider_image_max_long_edge),
                str(self.settings.provider_image_quality),
            ]
        )
        digest = hashlib.sha256(cache_identity.encode("utf-8")).hexdigest()[:16]
        provider_segment = self._safe_segment(provider)
        item_segment = self._safe_segment(provider_item_id)
        return f"covers/{provider_segment}/{item_segment}/{digest}.webp"

    def _normalized_cover_bytes(self, image_bytes: bytes) -> bytes:
        with Image.open(BytesIO(image_bytes)) as image:
            image = ImageOps.exif_transpose(image)
            max_edge = self.settings.provider_image_max_long_edge
            image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
            image = self._rgb_image(image)
            output = BytesIO()
            image.save(
                output,
                format="WEBP",
                quality=self.settings.provider_image_quality,
                method=6,
            )
            return output.getvalue()

    def _rgb_image(self, image: Image.Image) -> Image.Image:
        if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
            rgba = image.convert("RGBA")
            # Covers are normalized to a solid background so every client can render one asset.
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.getchannel("A"))
            return background
        if image.mode != "RGB":
            return image.convert("RGB")
        return image

    def _validate_image_bytes(self, image_bytes: bytes) -> None:
        if not image_bytes:
            raise ValueError("Image response is empty")
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                width, height = image.size
                if width <= 0 or height <= 0:
                    raise ValueError("Image has invalid dimensions")
                if width * height > self.settings.max_image_pixels:
                    raise ValueError("Image exceeds configured pixel limit")
                image.verify()
        except UnidentifiedImageError as exc:
            raise ValueError("Downloaded content is not a valid image") from exc

    def _safe_segment(self, value: str) -> str:
        cleaned = _SAFE_SEGMENT_RE.sub("-", value.strip()).strip("-._")
        return cleaned or "unknown"
