import hashlib
import mimetypes
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.storage.client import ObjectStorage


_SAFE_SEGMENT_RE = re.compile(r"[^a-zA-Z0-9._-]+")


@dataclass(frozen=True)
class MirroredImage:
    key: str
    url: str
    content_type: str


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
        except Exception:
            return None
        return MirroredImage(key=key, url=public_url, content_type=content_type)

    async def _download_image(self, source_url: str) -> tuple[bytes, str]:
        parsed = urlparse(source_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Unsupported image URL scheme")

        async with httpx.AsyncClient(timeout=self.settings.image_download_timeout_seconds) as client:
            response = await client.get(source_url, follow_redirects=True)
            response.raise_for_status()

        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        if not content_type.startswith("image/"):
            raise ValueError("Downloaded content is not an image")
        if len(response.content) > self.settings.max_image_bytes:
            raise ValueError("Image exceeds configured max size")
        return response.content, content_type

    def _cover_key(
        self, provider: str, provider_item_id: str, source_url: str, content_type: str
    ) -> str:
        extension = self._extension(source_url, content_type)
        digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:16]
        provider_segment = self._safe_segment(provider)
        item_segment = self._safe_segment(provider_item_id)
        return f"covers/{provider_segment}/{item_segment}/{digest}{extension}"

    def _extension(self, source_url: str, content_type: str) -> str:
        suffix = PurePosixPath(urlparse(source_url).path).suffix.lower()
        if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            return suffix
        return mimetypes.guess_extension(content_type) or ".jpg"

    def _safe_segment(self, value: str) -> str:
        cleaned = _SAFE_SEGMENT_RE.sub("-", value.strip()).strip("-._")
        return cleaned or "unknown"
