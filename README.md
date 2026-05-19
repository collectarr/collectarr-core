# 🎯 Collectarr Core

> The shared metadata engine behind Collectarr — canonical catalog, provider integrations, image delivery, and admin console.

Core owns the shared catalog and provider infrastructure. Personal collection data (owned items, wishlists, grades, notes) lives in `collectarr-app` and optionally syncs through `collectarr-sync`.

## ✨ Features

- 📚 **Canonical media catalog** — series, volumes, items, editions, variants, releases, people, organizations, and tags
- 🔌 **9 metadata providers** — GCD, ComicVine, AniList, MangaDex, OpenLibrary, BGG, MusicBrainz, IGDB, TMDb
- 🔍 **Smart provider search** — title normalization, issue matching, series aliases, barcode/UPC lookup
- 🖼️ **Image pipeline** — external URLs by default, optional MinIO/S3 mirroring, WebP normalization, LRU cache with budget tracking
- 🔎 **Full-text search** — optional Meilisearch indexing for instant catalog queries
- 🛠️ **Admin Console** — provider health, ingest queues, catalog coverage, duplicate detection, user management, image cache stats, audit logs
- 📋 **Ingest job queue** — DB-backed provider ingest with automatic worker processing, retry, and status tracking
- 👤 **Role-based access** — viewer / editor / admin roles with audit trail
- 📄 **OpenAPI docs** — auto-generated schema at `/docs` with versioned export

## 🚀 Quick Start

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m app.scripts.seed_comics
```

## 🧪 Development

```powershell
python -m pip install -e .[dev]
python -m ruff check .
python -m pytest
```

Helper commands:

```powershell
.\tools\dev.ps1 start          # Start Docker stack
.\tools\dev.ps1 migrate        # Run Alembic migrations
.\tools\dev.ps1 seed           # Seed sample comics data
.\tools\dev.ps1 test           # Run test suite
.\tools\dev.ps1 check          # Lint + type check
.\tools\dev.ps1 smoke-providers # Smoke test all providers
.\tools\dev.ps1 reset-stack    # Clean reset of all containers
```

## 🌐 Local URLs

| Service | URL |
|---------|-----|
| API | http://localhost:8010 |
| API docs (Swagger) | http://localhost:8010/docs |
| Admin Console | http://localhost:8010/admin/ui |
| Meilisearch | http://localhost:7700 |
| MinIO console | http://localhost:9001 |

## 📦 Release Policy

Release publishing is manual-only. The `Release` GitHub Actions workflow uses
`workflow_dispatch`; pushing to `main` runs CI only — no auto-publish.

## 🗂️ Related Repos

| Repo | Purpose |
|------|---------|
| `collectarr/collectarr-app` | 📱 Flutter client (web, Windows, Android) |
| `collectarr/collectarr-sync` | 🔄 Optional personal sync service |

## 🗺️ Roadmap

See [docs/implementation-plan.md](docs/implementation-plan.md) for the full roadmap.
