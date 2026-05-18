# Collectarr Core

Collectarr Core is the shared metadata and operations server for Collectarr.

It owns the canonical catalog, provider integrations, provider ingest jobs,
search indexing, image references/cache, admin identity, audit logs, and the
Core Admin Console.

Core stores shared metadata only. Personal collection data such as owned items,
wishlist entries, purchase prices, grades, notes, shelves, and progress belongs
in `collectarr-app` and can optionally sync through `collectarr-sync`.

## Development

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m app.scripts.seed_comics
```

Run tests locally:

```powershell
python -m pip install -e .[dev]
python -m ruff check .
python -m pytest
```

## Local URLs

- API: http://localhost:8010
- API docs: http://localhost:8010/docs
- Core Admin Console: http://localhost:8010/admin/ui
- Meilisearch: http://localhost:7700
- MinIO console: http://localhost:9001

## Repository Boundary

This repository contains:

- FastAPI metadata API
- SQLAlchemy/Alembic catalog schema
- provider plugins for GCD, ComicVine, AniList, OpenLibrary, BGG, MusicBrainz,
  IGDB, and TMDb
- provider search cache/rate limit/backoff logic
- DB-backed provider ingest queue and worker
- Meilisearch indexing
- MinIO/S3 image cache support
- admin API and Core Admin Console

Related repositories:

- `collectarr/collectarr-app`: Flutter local-library client
- `collectarr/collectarr-sync`: optional personal sync service
