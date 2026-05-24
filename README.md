# Collectarr Core

![Catalog items](docs/badges/catalog-total.svg)
![Comics](docs/badges/catalog-comic.svg)
![Manga](docs/badges/catalog-manga.svg)
![Anime](docs/badges/catalog-anime.svg)
![Books](docs/badges/catalog-book.svg)
![Games](docs/badges/catalog-game.svg)
![Board Games](docs/badges/catalog-boardgame.svg)
![Movies](docs/badges/catalog-movie.svg)
![TV](docs/badges/catalog-tv.svg)
![Music](docs/badges/catalog-music.svg)
![Blu-ray](docs/badges/catalog-bluray.svg)

> The shared metadata engine behind Collectarr — canonical catalog, provider integrations, image delivery, and admin console.

Core owns the shared catalog and provider infrastructure. Personal collection data (owned items, wishlists, grades, notes, personal tags) lives in `collectarr-app` and optionally syncs through `collectarr-sync`, while shared editorial tags can be attached to catalog series in Core.

## Features

- **Canonical media catalog** — series, volumes, items, editions, variants, releases, people, organizations, story arcs, characters, and shared series-level tags
- **10 metadata providers** — GCD, ComicVine, Hardcover, AniList, MangaDex, OpenLibrary, BGG, MusicBrainz, IGDB, TMDb
- **Smart provider search** — title normalization, issue matching, series aliases, barcode/UPC lookup
- **Story arc & character facets** — bulk facet endpoints for filtering items by arcs and characters
- **Typed metadata projection** — item, search, and admin preview responses expose normalized fields such as platforms, catalog numbers, and release status
- **Image pipeline** — external URLs by default, optional MinIO/S3 mirroring, MangaDex cover proxy, WebP normalization, LRU cache with budget tracking, and content-addressed origins for uploaded images
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

When normalizing provider data, preserve the provider-native raw payload exactly
as returned upstream. If a workflow also needs the canonical provider item id,
use `ProviderItem.provider_item_id` alongside the raw mapping instead of
rewriting `raw['id']`, because some providers expose numeric or kind-specific
raw identifiers that are not interchangeable with the canonical route id.

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

## Catalog Badges

The repo includes snapshot badges for total catalog items and per-kind item
counts. `.github/workflows/catalog-badges.yml` refreshes them on a daily
schedule or manual dispatch.

To switch from placeholder badges to live counts, configure:

- `COLLECTARR_BADGES_BASE_URL` — public base URL for the hosted Core server
- `COLLECTARR_BADGES_TOKEN` — bearer token for `/admin/catalog/summary`

Or, instead of a static token:

- `COLLECTARR_BADGES_EMAIL`
- `COLLECTARR_BADGES_PASSWORD`

The workflow logs in through `/auth/login` when a bearer token is not provided.

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
