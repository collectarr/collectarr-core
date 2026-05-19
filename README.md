# Collectarr Core

Collectarr Core is the shared metadata and operations server for Collectarr.
It owns the canonical catalog, provider integrations, ingest jobs, search
indexing, image references/cache, admin identity, audit logs, and the Core Admin
Console.

Core stores shared metadata only. Personal collection data such as owned items,
wishlist entries, purchase prices, grades, notes, shelves, and progress belongs
in `collectarr-app` and can optionally sync through `collectarr-sync`.

## What It Does

- Serves the canonical media catalog API used by Collectarr clients.
- Models series, volumes, items, editions, variants, releases, people,
  organizations, tags, provider IDs, proposals, and audit history.
- Searches and ingests metadata from GCD, ComicVine, AniList, MangaDex,
  OpenLibrary, BGG, MusicBrainz, IGDB, and TMDb.
- Supports comics-first provider search with structured series, issue, variant,
  barcode, publisher, release date, and cover metadata.
- Surfaces real provider candidates for comic series and issues, including
  GCD/ComicVine series candidates that App can select as whole-series rows.
- Exposes manga provider support through AniList and MangaDex, including
  MangaDex volume/chapter data through the metadata volumes API.
- Provides optional Meilisearch indexing and optional MinIO/S3 cover mirroring.
- Provides the Core Admin Console for provider health, ingest queues, catalog
  coverage, search status, metadata proposals, image inspection, and audit logs.

## Development

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m app.scripts.seed_comics
```

Run checks locally:

```powershell
python -m pip install -e .[dev]
python -m ruff check .
python -m pytest
```

Helper commands:

```powershell
.\tools\dev.ps1 start
.\tools\dev.ps1 migrate
.\tools\dev.ps1 seed
.\tools\dev.ps1 test
.\tools\dev.ps1 check
.\tools\dev.ps1 smoke-providers
.\tools\dev.ps1 reset-stack
```

## Local URLs

- API: http://localhost:8010
- API docs: http://localhost:8010/docs
- Core Admin Console: http://localhost:8010/admin/ui
- Meilisearch: http://localhost:7700
- MinIO console: http://localhost:9001

## Release Policy

Release publishing is manual-only. The `Release` GitHub Actions workflow uses
`workflow_dispatch`; pushing to `main` should run CI, not publish a GitHub
Release or tag. Publish only after explicitly running the release workflow and
reviewing the generated version and notes.

## Repository Boundary

This repository contains the FastAPI metadata API, SQLAlchemy/Alembic catalog
schema, provider plugins, provider search cache/rate limit/backoff logic,
DB-backed provider ingest queue, Meilisearch integration, MinIO/S3 image cache
support, admin API, and Core Admin Console.

Related repositories:

- `collectarr/collectarr-app`: Flutter local-library client
- `collectarr/collectarr-sync`: optional personal sync service

## Current Focus

See [docs/implementation-plan.md](docs/implementation-plan.md) for the active
Core roadmap.

Near-term Core work:

- harden provider normalization and smoke fixtures across all live providers
- improve GCD + ComicVine series/issue matching, variants, barcode/UPC,
  credits, publishers, release dates, and cover fallbacks
- continue MangaDex volume/chapter support and App-facing volume contracts
- mature image delivery: external URL by default, optional MinIO/S3 mirror,
  generated fallback covers, and cache health visibility
- publish stable API/media catalog/snapshot contracts for `collectarr-app` and
  `collectarr-sync`
