import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass
from io import BytesIO

import imagehash
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import get_settings
from app.storage.client import ObjectStorage

_SAFE_SEGMENT_RE = re.compile(r"[^a-zA-Z0-9._-]+")
_NORMALIZED_COVER_CONTENT_TYPE = "image/webp"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MirroredImage:
    key: str
    url: str
    content_type: str
    source_url: str
    entity_type: str
    entity_id: str
    size_bytes: int
    width: int
    height: int
    content_hash: str
    phash: str | None = None
    thumbnail_key: str | None = None
    thumbnail_url: str | None = None


@dataclass(frozen=True)
class NormalizedCover:
    body: bytes
    width: int
    height: int
    phash: str | None = None

    @property
    def size_bytes(self) -> int:
        return len(self.body)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.body).hexdigest()


class ImageMirror:
    def __init__(self, storage: ObjectStorage | None = None) -> None:
        self.settings = get_settings()
        self.storage = storage or ObjectStorage()

    async def mirror_cover_bytes_best_effort(
        self,
        image_bytes: bytes | None,
        *,
        source_url: str | None,
        entity_type: str,
        entity_id: str,
        existing_content_hash: str | None = None,
    ) -> MirroredImage | None:
        if not image_bytes or not source_url:
            return None
        try:
            await asyncio.to_thread(self._validate_image_bytes, image_bytes)
            cover = await asyncio.to_thread(self._normalized_cover, image_bytes)
            # Content-hash dedup: skip upload if identical bytes already stored.
            if existing_content_hash and cover.content_hash == existing_content_hash:
                return None
            key = self._cover_key(entity_type, entity_id, source_url)
            public_url = await asyncio.to_thread(
                self.storage.put_object, key, cover.body, _NORMALIZED_COVER_CONTENT_TYPE
            )
        except Exception:
            logger.warning(
                "Failed to store uploaded catalog cover bytes %s for %s:%s",
                source_url,
                entity_type,
                entity_id,
                exc_info=True,
            )
            return None
        return MirroredImage(
            key=key,
            url=public_url,
            content_type=_NORMALIZED_COVER_CONTENT_TYPE,
            source_url=source_url,
            entity_type=entity_type,
            entity_id=entity_id,
            size_bytes=cover.size_bytes,
            width=cover.width,
            height=cover.height,
            content_hash=cover.content_hash,
            phash=cover.phash,
        )

    def _cover_key(self, entity_type: str, entity_id: str, source_url: str) -> str:
        cache_identity = "|".join(
            [
                source_url,
                _NORMALIZED_COVER_CONTENT_TYPE,
                str(self.settings.image_max_long_edge),
                str(self.settings.image_quality),
            ]
        )
        digest = hashlib.sha256(cache_identity.encode("utf-8")).hexdigest()[:16]
        type_segment = self._safe_segment(entity_type)
        item_segment = self._safe_segment(entity_id)
        return f"covers/{type_segment}/{item_segment}/{digest}.webp"

    def _normalized_cover_bytes(self, image_bytes: bytes) -> bytes:
        return self._normalized_cover(image_bytes).body

    def _normalized_cover(self, image_bytes: bytes) -> NormalizedCover:
        with Image.open(BytesIO(image_bytes)) as image:
            image = ImageOps.exif_transpose(image)
            max_edge = self.settings.image_max_long_edge
            image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
            image = self._rgb_image(image)
            width, height = image.size
            # Compute perceptual hash before WebP compression.
            phash_value: str | None = None
            try:
                phash_value = str(imagehash.phash(image))
            except Exception:
                logger.debug("phash computation failed", exc_info=True)
            output = BytesIO()
            image.save(
                output,
                format="WEBP",
                quality=self.settings.image_quality,
                method=6,
            )
            return NormalizedCover(
                body=output.getvalue(),
                width=width,
                height=height,
                phash=phash_value,
            )

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
