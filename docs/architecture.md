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
    async def search(
        self,
        query: str,
        kind: ItemKind | None = None,
    ) -> list[ProviderSearchResult]: ...
    async def get_item(self, provider_item_id: str) -> ProviderItem: ...
    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem: ...
```

## Repository Boundaries

Collectarr should split into three product repositories once the current
pre-release monorepo is frozen for migration:

- `collectarr-core`: metadata API, canonical catalog, provider plugins,
  provider ingest worker, search indexing, image cache, admin identity, audit
  logs, migrations, and the Core Admin Console.
- `collectarr-sync`: optional personal sync service, sync protocol, device
  pairing, conflict handling, tombstones, and sync storage.
- `collectarr-app`: Flutter client, local Drift database, local catalog
  snapshots, import/export, barcode UX, sync client, and user-facing library UI.

Core owns the operational admin frontend. The Core Admin Console should become
a Grafana-like control plane for server health, worker/queue status, provider
health, catalog coverage, missing covers/provider IDs, ingest failures, audit
history, admin accounts, and destructive metadata operations. The Flutter app
can show whether the connected account has admin permissions, but the
server-operator console belongs with Core.

See [repository-split.md](repository-split.md) for the split sequence and file
ownership map.

GCD is the default legal-clean comics seed candidate because it provides CC BY-SA bibliographic issue metadata without an API key. Its provider searches issue-style queries such as `Batman #12`, falls back to issue `#1` for series-only queries such as `Absolute Batman`, normalizes issue detail into canonical metadata, and preserves source provenance.

ComicVine remains an optional personal/non-commercial enrichment provider for
comics and manga entries. Its issue ingest path stores provider IDs for the
item and volume, normalizes issue payloads into canonical metadata, and creates
the first edition, primary cover variant, associated variant covers, and US
release record. ComicVine search can also expand issue `associated_images` into
provider candidates, and GCD series searches can merge those candidates as
controlled variant-cover enrichment. Manga IDs use a `manga:` provider prefix
while existing comics IDs remain unprefixed. If no `COMICVINE_API_KEY` is
configured, the provider returns stub data so local development still works
without secrets.

OpenLibrary is the first live non-comics provider. It searches Open Library
works, prefers edition OLIDs for ingest, normalizes book metadata into the same
canonical item/edition/variant/release hierarchy, and keeps cover URLs pointed
at `covers.openlibrary.org` by default.

BoardGameGeek is the first live games-table provider. It uses XML API2 `search`
and `thing`, requires a configured application token for live calls, normalizes
board game title/year/publisher/designer/category/family data into canonical
records, and keeps BGG image URLs as references by default.

AniList is the first live manga and anime provider. It uses the public GraphQL
API for `Media(type: MANGA)` and `Media(type: ANIME)` search and detail
fetches, normalizes title/start date/format/runtime/staff/genres/cover data,
and keeps cover URLs pointed at AniList's CDN by default. Existing manga IDs
remain unprefixed; anime IDs use an `anime:` provider prefix.

MusicBrainz is the first live music provider. It searches and looks up release
MBIDs through the JSON web service, normalizes artist credits, labels, release
dates, barcodes, release-group IDs, and uses Cover Art Archive front-cover URLs
only when MusicBrainz reports front artwork.

IGDB is the first live video-game provider. It uses Twitch client credentials or
a preconfigured access token, searches the `games` endpoint, normalizes release
date/platform/publisher/developer/genre/cover metadata, and keeps IGDB image
URLs as references by default.

TMDb is the live movie, TV, and anime provider. It uses a TMDb API read access
token or API key, searches `search/movie` and `search/tv`, fetches movie/series
details with credits and external IDs appended, normalizes runtime, release
date, production company, creators, cast, genres, and poster URLs, and stores
TMDb provider IDs with `movie:`, `tv:`, or `anime:` prefixes. Anime currently
maps to TMDb's TV endpoint because TMDb models anime series as TV records.

Movies and TV shows are canonical video works. DVD, Blu-ray, 4K UHD, VHS,
LaserDisc, and digital purchases are physical/digital formats represented by
edition and variant records under those works. Legacy `bluray` routes can remain
for compatibility while new provider work targets movie/TV records plus exact
physical release variants.
Admin corrections can set the normalized physical format before a dedicated
release schema exists; Core stores that as edition/variant metadata and returns
the normalized ID plus display label to Flutter.

Core exposes the media catalog through `GET /metadata/media-types`. Flutter
uses that response as the runtime source for media labels, route aliases,
provider defaults, provider ordering, and physical format options, while keeping
local fallback data for offline/development sessions when Core is unavailable.

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
- Settings conflict actions for Keep service and Keep local retry

## Search

PostgreSQL is the source of truth. Meilisearch is a derived index.

Provider ingest indexes newly imported canonical items into Meilisearch immediately on a best-effort basis, so search becomes fresh without waiting for the periodic worker. Provider ingest jobs are DB-backed, can be run manually through admin endpoints, and are also drained by the worker with retry/backoff and stale-running job recovery. Admin queue endpoints expose status/provider/error filters plus a queue summary for due jobs, stale running jobs, and recent failures. Admin metadata corrections, duplicate actions, proposal decisions, and manual ingest queue actions are recorded in persistent audit logs with actor identity and JSON details. Workers still rebuild derived search documents periodically, and API search can fall back to PostgreSQL if Meilisearch is unavailable or empty.

## Storage

Images are stored as references, not backend filesystem files. For public providers such as ComicVine, Collectarr keeps the provider cover URL by default and avoids copying that image into MinIO/S3. MinIO/S3 is reserved for manual uploads, generated assets, and providers without stable public cover URLs; provider mirroring can be enabled with `MIRROR_PROVIDER_IMAGES=true` when a fully self-contained catalog is preferred. Ingest metadata records whether a cover is external, mirrored, or missing so admin tools can explain what the client should render. Mirroring is provider-policy aware: restricted providers remain external URLs unless `MIRROR_PROVIDER_IMAGES_ALLOW_RESTRICTED=true` is set for a deployment that accepts those provider-specific image terms. Mirrored provider covers are normalized to one WebP asset per source image, capped by `PROVIDER_IMAGE_MAX_LONG_EDGE` without upscaling. Mirrored covers are indexed in `image_cache_entries` and bounded by a least-recently-used cache budget, defaulting to 100 GB. Local MinIO can be configured with a public read bucket policy through `S3_MANAGE_PUBLIC_READ_POLICY`.

## Scaling

The API is stateless. Durable state lives in PostgreSQL, Meilisearch, and MinIO.
Redis carries shared ephemeral state: rate-limit windows, provider search
cache, and provider cooldown/backoff. If Redis is unavailable in local
development, Core falls back to process-local state; in multi-replica
deployments, configure Redis so provider protections are shared across all API
processes. API and worker containers can scale independently.
