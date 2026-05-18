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

Provider search participates in the same policy. If mirroring is enabled and the
provider image is an external `http` or `https` URL, Core returns the cached
MinIO/S3 URL in the search response after the image has been normalized. GCD
search results still use the Core cover proxy URL, and that proxy can lazily
mirror the fetched cover before redirecting the client to object storage.

Provider searches are explicit user actions from Flutter. Core rate-limits those
requests, caches provider search responses by provider/kind/query for a few
hours, and places providers on a short cooldown when upstream returns
401/429/5xx. Redis stores those guardrails when `REDIS_URL` is configured, with
in-memory fallback for local development. GCD can use ComicVine only when the
fallback setting is enabled: exact issue queries use ComicVine when GCD is
unavailable, while series-style GCD searches can merge ComicVine associated
cover candidates so variant covers appear without exposing provider routing to
the client.

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
5. If testing MinIO mirroring, enable `MIRROR_PROVIDER_IMAGES=true`, ingest or
   search a provider whose terms permit mirroring, and confirm the rendered URL
   points at object storage.
