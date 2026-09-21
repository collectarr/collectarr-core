# Architecture

## Domain Boundary

Canonical metadata is shared across clients. Personal library data references canonical records locally but is not stored by the central metadata server.

Canonical graph:

```text
Kind-specific Work -> Release -> Medium / Track
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
- normalized metadata submission and canonical writes
- search indexing decisions

Repositories own database query details.

Provider adapters and importers live in `collectarr-app`. Core accepts the
versioned `NormalizedProviderEnvelopeV1` contract and owns validation,
provenance, canonical writes, and indexing.

## Repository Boundaries

Collectarr is split into three product repositories:

- `collectarr-core`: metadata API, canonical catalog, normalized submission
  handling, search indexing, image cache, admin identity, audit logs,
  schema bootstrap and the Core Admin Console.
- `collectarr-sync`: optional personal sync service, sync protocol, device
  pairing, conflict handling, tombstones, and sync storage.
- `collectarr-app`: Flutter client, local Drift database, local catalog
  snapshots, import/export, barcode UX, sync client, and user-facing library UI.

Core owns the operational admin frontend. The Core Admin Console should become
a Grafana-like control plane for server health, worker status, catalog coverage,
missing covers/provider IDs, audit history, admin accounts, and destructive
metadata operations. The Flutter app can show whether the connected account has
admin permissions, but the server-operator console belongs with Core.

See [repository-split.md](repository-split.md) for the current split status and
ownership map.

Movies and TV shows are canonical video works. DVD, Blu-ray, 4K UHD, VHS,
LaserDisc, and digital purchases are physical/digital formats represented by
edition and variant records under those works; normalized submissions target
the canonical movie/TV records plus exact physical release variants.
Admin corrections target exact kind-specific work or release entities and return
the normalized ID plus display label to Flutter.

Core exposes the media catalog through `GET /api/v1/metadata/media-types`. Flutter
uses that response as the runtime source for media labels, route aliases, and
physical format options, while keeping local fallback data for
offline/development sessions when Core is unavailable.

## Local Personal Data

The Flutter client stores personal collection state in Drift. Owned items, wishlist entries, purchase dates, prices, grades, condition, notes, and personal tags stay on the user's device. Shared series-level catalog tags live in Core.

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

Normalized submissions are written to PostgreSQL and indexed into Meilisearch on
a best-effort basis. Workers rebuild derived search documents periodically, and
API search can fall back to PostgreSQL if Meilisearch is unavailable or empty.
Admin metadata corrections, duplicate actions, and proposal decisions are
recorded in persistent audit logs with actor identity and typed details.

## Storage

Images are stored as references, not backend filesystem files. MinIO/S3 is used
for manual uploads, generated assets, and optional mirrored assets. Mirrored
images are normalized to WebP, indexed in `image_cache_entries`, and bounded by
a least-recently-used cache budget. Local MinIO can be configured with a public
read bucket policy through `S3_MANAGE_PUBLIC_READ_POLICY`.

## Scaling

The API is stateless. Durable state lives in PostgreSQL, Meilisearch, and MinIO.
Redis carries shared ephemeral state such as rate-limit windows. If Redis is
unavailable in local development, Core falls back to process-local state. API
and worker containers can scale independently.
