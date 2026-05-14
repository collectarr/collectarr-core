# Architecture

## Domain Boundary

Canonical metadata is shared across clients. Personal library data references canonical records locally but is not stored by the central metadata server.

Canonical hierarchy:

```text
Franchise -> Series -> Volume -> Item -> Edition -> Variant
                                      -> Release
```

Local client hierarchy:

```text
LocalDatabase -> OwnedItem
              -> WishlistItem
OwnedItem -> personal notes
OwnedItem -> condition / grading / purchase data
```

External provider IDs are stored separately and can point at any canonical entity by `(entity_type, entity_id)`.

## Backend Layers

API routers validate HTTP payloads, call services, and return DTOs.

Services own business rules, including:

- registration/login
- metadata provider orchestration
- search indexing decisions

Repositories own database query details.

Providers adapt external APIs behind one plugin contract:

```python
class MetadataProvider(Protocol):
    capabilities: ProviderCapabilities
    @property
    def is_configured(self) -> bool: ...
    @property
    def status_message(self) -> str: ...
    async def search(self, query: str) -> list[ProviderSearchResult]: ...
    async def get_item(self, provider_item_id: str) -> ProviderItem: ...
    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem: ...
```

GCD is the default legal-clean comics seed candidate because it provides CC BY-SA bibliographic issue metadata without an API key. Its provider searches issue-style queries such as `Batman #12`, normalizes issue detail into canonical metadata, and preserves source provenance.

ComicVine remains an optional personal/non-commercial enrichment provider. Its issue ingest path stores provider IDs for the item and volume, normalizes issue payloads into canonical metadata, and creates the first edition, primary cover variant, and US release record. If no `COMICVINE_API_KEY` is configured, the provider returns stub data so local development still works without secrets.

## Local Personal Data

The Flutter client stores personal collection state in Drift. Owned items, wishlist entries, purchase dates, prices, grades, condition, and notes stay on the user's device.

The central backend intentionally does not expose `/collection` or `/sync` endpoints. This keeps the shared metadata server stateless with respect to personal libraries and avoids turning public web access into a private-data hosting requirement.

Multi-device sync belongs in the separate user-hosted `collectarr-sync` service.

Initial strategy for `collectarr-sync`:

- UUIDs generated client-side
- `device_id` per installation
- `client_changed_at` timestamps on local mutations
- last-write-wins to start
- tombstones for deletes
- later manual conflict resolution UI

## Search

PostgreSQL is the source of truth. Meilisearch is a derived index.

Provider ingest indexes newly imported canonical items into Meilisearch immediately on a best-effort basis, so search becomes fresh without waiting for the periodic worker. Workers still rebuild derived search documents periodically, and API search can fall back to PostgreSQL if Meilisearch is unavailable or empty.

## Storage

Images are stored as references, not backend filesystem files. For public providers such as ComicVine, Collectarr keeps the provider cover URL by default and avoids copying that image into MinIO/S3. MinIO/S3 is reserved for manual uploads, generated assets, and providers without stable public cover URLs; provider mirroring can be enabled with `MIRROR_PROVIDER_IMAGES=true` when a fully self-contained catalog is preferred. Mirrored provider covers are normalized to one WebP asset per source image, capped by `PROVIDER_IMAGE_MAX_LONG_EDGE` without upscaling. Mirrored covers are indexed in `image_cache_entries` and bounded by a least-recently-used cache budget, defaulting to 100 GB. Local MinIO can be configured with a public read bucket policy through `S3_MANAGE_PUBLIC_READ_POLICY`.

## Scaling

The API is stateless. State lives in PostgreSQL, Redis, Meilisearch, and MinIO. API and worker containers can scale independently.
