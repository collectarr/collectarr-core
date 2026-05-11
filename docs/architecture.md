# Architecture

## Domain Boundary

Canonical metadata is shared across users. User data references canonical records but never mutates them.

Canonical hierarchy:

```text
Franchise -> Series -> Volume -> Item -> Edition -> Variant
                                      -> Release
```

User hierarchy:

```text
User -> UserCollection -> OwnedItem
                       -> WishlistItem
OwnedItem -> Notes
OwnedItem -> Tags
```

External provider IDs are stored separately and can point at any canonical entity by `(entity_type, entity_id)`.

## Backend Layers

API routers validate HTTP payloads, call services, and return DTOs.

Services own business rules, including:

- registration/login
- collection item updates
- sync conflict resolution
- metadata provider orchestration
- search indexing decisions

Repositories own database query details.

Providers adapt external APIs behind one plugin contract:

```python
class MetadataProvider(Protocol):
    async def search(self, query: str) -> list[ProviderSearchResult]: ...
    async def get_item(self, provider_item_id: str) -> ProviderItem: ...
    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem: ...
```

## Sync

The client stores local records and a pending change log. The server accepts diffs through `/sync/push`.

Initial strategy:

- UUIDs generated client-side or server-side
- `changed_at` timestamps on server changes
- last-write-wins based on `updated_at`/client change timestamps
- deletes are soft-deleted where user data needs sync visibility

Future strategy:

- per-field conflict records
- manual conflict resolution UI
- device identity and sync sessions

## Search

PostgreSQL is the source of truth. Meilisearch is a derived index.

Workers sync changed canonical records to Meilisearch and build autocomplete/fuzzy search documents. API search can fall back to PostgreSQL if Meilisearch is unavailable.

## Storage

Images are stored in MinIO/S3. The backend stores object keys/URLs only. Thumbnail generation is asynchronous.

## Scaling

The API is stateless. State lives in PostgreSQL, Redis, Meilisearch, and MinIO. API and worker containers can scale independently.

