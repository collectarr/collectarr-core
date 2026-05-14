# Image Pipeline

Collectarr keeps provider cover URLs as external references by default. This is
the safest MVP behavior for licensing, storage, and browser compatibility.

## Delivery Modes

- `external_url`: Core stores the provider URL and clients render it directly.
- `mirrored`: when `MIRROR_PROVIDER_IMAGES=true` and provider policy allows it,
  Core downloads one source image, normalizes it to WebP, stores it in
  MinIO/S3, and records the object in `image_cache_entries`.
- `missing`: Core stores no cover URL. Flutter renders a deterministic generated
  cover from the title and issue number.

Restricted providers stay external unless
`MIRROR_PROVIDER_IMAGES_ALLOW_RESTRICTED=true` is explicitly enabled for a
deployment that accepts the provider terms.

## Client Fallback

Flutter accepts only `http` and `https` cover URLs. Empty, malformed, blocked,
or failed image loads fall back to `LibraryGeneratedCover`, so web and desktop
do not show blank cover slots when a provider URL is unavailable.

## Smoke Checklist

Use this with Core + Flutter running:

1. Ingest a GCD comic that has a cover URL.
2. Open Flutter web and desktop and confirm the cover renders in shelf, table,
   and detail views.
3. Ingest or edit an item with no cover URL and confirm the generated cover
   appears.
4. If GCD images are blocked, run ComicVine cover enrichment with
   `COMICVINE_API_KEY` and confirm the cover URL changes.
5. If testing MinIO mirroring, enable `MIRROR_PROVIDER_IMAGES=true`, ingest a
   provider whose terms permit mirroring, and confirm the rendered URL points at
   object storage.

