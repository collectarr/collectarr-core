# Image Pipeline

Core stores image references and optional mirrored assets. Provider adapters and
importers choose the source image in the app; Core handles the shared storage
and delivery path.

## Delivery Modes

- `external_url`: Core stores the source URL and clients render it directly.
- `mirrored`: when `MIRROR_PROVIDER_IMAGES=true`, Core downloads the source,
  normalizes it to WebP, stores it in MinIO/S3, and records it in
  `image_cache_entries`.
- `missing`: Core stores no image URL. The client renders a deterministic
  generated cover.

User-uploaded images use the same mirroring path. Their effective source URL is
derived from the uploaded bytes, which gives object-key generation a stable
origin and prevents collisions between uploads.

Image mutation endpoints are admin-only. Viewers and editors can consume image
URLs, but only admins can add, delete, or promote canonical image assets.

## Client Fallback

Flutter accepts only valid `http` and `https` image URLs. Empty, malformed,
blocked, or failed image loads fall back to `LibraryGeneratedCover`.

## Local Check

1. Submit metadata with an image reference.
2. Confirm the URL renders in list and detail views.
3. Enable `MIRROR_PROVIDER_IMAGES=true` and submit another image.
4. Confirm the response points to the MinIO/S3 object and that the cache entry
   is visible in the admin tools.
