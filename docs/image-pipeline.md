# Image Pipeline

Core stores canonical image references and uploaded image assets. App clients
choose canonical image sources and upload images through the shared Core image
API. Core validates, normalizes, and stores uploaded bytes in object storage.

## Delivery Modes

- `external_url`: Core stores a canonical source URL and clients render it
  directly.
- `uploaded`: Core normalizes uploaded bytes to WebP and stores the asset in
  MinIO/S3. The image record points to the stored object.
- `missing`: Core stores no image URL. The client renders a deterministic
  generated cover.

Uploaded assets are normalized to a bounded image size and deduplicated by
content hash. Image records retain the entity and image type so clients can
retrieve the right cover or auxiliary image.

Image mutation endpoints are admin-only. Viewers and editors can consume image
URLs, but only admins can add, delete, or promote canonical image assets.

## Client Fallback

Flutter accepts only valid `http` and `https` image URLs. Empty, malformed,
blocked, or failed image loads fall back to `LibraryGeneratedCover`.

## Local Check

1. Upload an image through the Core image API.
2. Confirm Core returns an object URL and the image renders in list and detail
   views.
3. Confirm the corresponding image asset is visible in the admin tools.
