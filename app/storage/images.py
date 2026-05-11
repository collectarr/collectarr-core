import hashlib
from io import BytesIO
import mimetypes
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
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
            image_bytes, content_type = await self._download_image(source_url)
            key = self._cover_key(provider, provider_item_id, source_url, content_type)
            public_url = self.storage.put_object(key, image_bytes, content_type)
            thumbnail_key, thumbnail_url = self._mirror_thumbnail_best_effort(
                image_bytes,
                provider,
                provider_item_id,
                source_url,
            )
        except Exception:
            return None
        return MirroredImage(
            key=key,
            url=public_url,
            content_type=content_type,
            thumbnail_key=thumbnail_key,
            thumbnail_url=thumbnail_url,
        )

    async def _download_image(self, source_url: str) -> tuple[bytes, str]:
        parsed = urlparse(source_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Unsupported image URL scheme")

        async with httpx.AsyncClient(timeout=self.settings.image_download_timeout_seconds) as client:
            response = await client.get(source_url, follow_redirects=True)
            response.raise_for_status()

        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type not in _SUPPORTED_IMAGE_TYPES:
            raise ValueError("Downloaded content is not a supported image")
        if len(response.content) > self.settings.max_image_bytes:
            raise ValueError("Image exceeds configured max size")
        self._validate_image_bytes(response.content)
        return response.content, content_type

    def _cover_key(
        self, provider: str, provider_item_id: str, source_url: str, content_type: str
    ) -> str:
        extension = self._extension(source_url, content_type)
        digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:16]
        provider_segment = self._safe_segment(provider)
        item_segment = self._safe_segment(provider_item_id)
        return f"covers/{provider_segment}/{item_segment}/{digest}{extension}"

    def _mirror_thumbnail_best_effort(
        self, image_bytes: bytes, provider: str, provider_item_id: str, source_url: str
    ) -> tuple[str | None, str | None]:
        try:
            thumbnail_bytes = self._thumbnail_bytes(image_bytes)
            key = self._thumbnail_key(provider, provider_item_id, source_url)
            public_url = self.storage.put_object(key, thumbnail_bytes, "image/jpeg")
        except Exception:
            return None, None
        return key, public_url

    def _thumbnail_key(self, provider: str, provider_item_id: str, source_url: str) -> str:
        digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:16]
        provider_segment = self._safe_segment(provider)
        item_segment = self._safe_segment(provider_item_id)
        return f"thumbnails/{provider_segment}/{item_segment}/{digest}.jpg"

    def _thumbnail_bytes(self, image_bytes: bytes) -> bytes:
        with Image.open(BytesIO(image_bytes)) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail(
                (self.settings.thumbnail_max_width, self.settings.thumbnail_max_width * 2)
            )
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            output = BytesIO()
            image.save(output, format="JPEG", quality=self.settings.thumbnail_quality, optimize=True)
            return output.getvalue()

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

    def _extension(self, source_url: str, content_type: str) -> str:
        suffix = PurePosixPath(urlparse(source_url).path).suffix.lower()
        if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            return suffix
        return mimetypes.guess_extension(content_type) or ".jpg"

    def _safe_segment(self, value: str) -> str:
        cleaned = _SAFE_SEGMENT_RE.sub("-", value.strip()).strip("-._")
        return cleaned or "unknown"
