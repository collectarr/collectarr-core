# Collectarr Core

> The shared metadata engine behind Collectarr — canonical catalog, provider integrations, image delivery, and admin console.

Core owns the shared catalog and provider infrastructure. Personal collection data (owned items, wishlists, grades, notes) lives in `collectarr-app` and optionally syncs through `collectarr-sync`.

## Features

- **Canonical media catalog** — series, volumes, items, editions, variants, releases, people, organizations, story arcs, characters, and tags
- **10 metadata providers** — GCD, ComicVine, Hardcover, AniList, MangaDex, OpenLibrary, BGG, MusicBrainz, IGDB, TMDb
- **Smart provider search** — title normalization, issue matching, series aliases, barcode/UPC lookup
- **Story arc & character facets** — bulk facet endpoints for filtering items by arcs and characters
- **Typed metadata projection** — item, search, and admin preview responses expose normalized fields such as platforms, catalog numbers, and release status
- **Image pipeline** — external URLs by default, optional MinIO/S3 mirroring, MangaDex cover proxy, WebP normalization, LRU cache with budget tracking
- **Full-text search** — optional Meilisearch indexing for instant catalog queries
- **Admin console** — provider health, ingest queues, catalog coverage, duplicate detection, user management, image cache stats, audit logs
- **Ingest job queue** — DB-backed provider ingest with automatic worker processing, retry, and status tracking
- **Role-based access** — viewer / editor / admin roles with audit trail
- **OpenAPI docs** — auto-generated schema at `/docs` with versioned export

## Quick Start

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m app.scripts.seed_comics
```

## Development

```powershell
python -m pip install -e .[dev]
python -m ruff check .
python -m pytest
```

Helper commands:

```powershell
.\tools\dev.ps1 start          # Start Docker stack
.\tools\dev.ps1 start -WithSync # Start Core + collectarr-sync dev stack
.\tools\dev.ps1 migrate        # Run Alembic migrations
.\tools\dev.ps1 seed           # Seed sample comics data
.\tools\dev.ps1 test           # Run test suite
.\tools\dev.ps1 check          # Lint + type check
.\tools\dev.ps1 smoke-providers # Smoke test all providers
.\tools\dev.ps1 reset-stack    # Clean reset of all containers
python -m scripts.export_provider_support  # Regenerate docs/provider-support.md from the provider registry
```

## Extending Metadata For New Libraries

Core is the canonical source of cross-library metadata. When a provider exposes a
new field, wire it through the normalized metadata contract first and only then
project it into the client.

1. Normalize the field in the provider ingest pipeline.
2. Expose it through the public schemas used by the app: item responses, search results, and admin/provider previews.
3. Add it to Meilisearch documents and display attributes when it should participate in search or search previews.
4. Keep field names stable so `collectarr-app` can cache and render the same canonical shape offline.

This keeps provider growth and future library additions predictable: new kinds
can share the same catalog/search/admin contract instead of inventing parallel
app-only fields.

## Local URLs

| Service | URL |
|---------|-----|
| API | http://localhost:8010 |
| API docs (Swagger) | http://localhost:8010/docs |
| Admin Console | http://localhost:8010/admin/ui |
| Sync service | http://localhost:8020 |
| Meilisearch | http://localhost:7700 |
| MinIO console | http://localhost:9001 |

## Release Policy

Release publishing is manual-only. The `Release` GitHub Actions workflow uses
`workflow_dispatch`; pushing to `main` runs CI only — no auto-publish.

## Related Repos

| Repo | Purpose |
|------|---------|
| `collectarr-app` | Flutter client (web, Windows, Android) |
| `collectarr-sync` | Optional personal sync service |

## Provider Support

See [docs/provider-support.md](docs/provider-support.md) for the generated
support matrix derived from the provider registry.

## Roadmap

See [docs/implementation-plan.md](docs/implementation-plan.md) for the full roadmap.
