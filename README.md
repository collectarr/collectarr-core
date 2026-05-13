# Collectarr

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![GitHub Release](https://img.shields.io/github/v/release/saitatter/collectarr)
[![Issues](https://img.shields.io/github/issues/saitatter/collectarr)](https://github.com/saitatter/collectarr/issues)
![Made with Python](https://img.shields.io/badge/Made%20with-Python-3776AB?logo=python&logoColor=white)
![Flutter](https://img.shields.io/badge/Flutter-02569B?logo=flutter&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Web%20%7C%20Mobile%20%7C%20Desktop-lightgrey)

> Self-hosted metadata hub for comics, manga, anime, movies, TV, games, books, music, board games, and other collectibles.

Collectarr is a centralized collector metadata hub with variant-aware catalog records, offline-first local libraries, and plugin-based metadata providers. The central server stores shared metadata only. Personal collection data stays on the user's device, with an optional `collectarr-sync` service for people who want to sync their own devices.

For quick handoff context in new chats, see [docs/context.md](docs/context.md).

---

## ✨ Features

### 📚 Metadata Catalog

- Canonical metadata kept separate from personal library data
- Generalized work, series, release, edition, and variant hierarchy
- External provider IDs for ComicVine, IGDB, TMDb, AniList, BGG, OpenLibrary, MusicBrainz, and future providers
- Public provider cover URLs kept as references by default, with MinIO/S3 reserved for manual or non-public assets
- Meilisearch-backed fuzzy search with PostgreSQL fallback when the search index is unavailable
- See [docs/schema.md](docs/schema.md) for the database boundary and catalog schema

### 🧾 Personal Libraries

- Owned items, wishlist, purchase dates, prices, condition, grading, and notes are stored in the Flutter app's local Drift database
- Edition-aware and variant-aware local ownership records
- The central metadata server does not store personal collection or wishlist records

### 🔄 Offline-First Sync

- Flutter clients work offline against a local database first
- The central server is metadata-only and does not expose personal `/collection` or `/sync` APIs
- Multi-device personal sync is reserved for a separate self-hosted `collectarr-sync` service
- The sync service is opt-in, user-owned infrastructure

### 🧩 Provider Plugins

- Provider abstraction for search, item fetch, and normalization
- ComicVine provider supports live issue search/fetch when `COMICVINE_API_KEY` is set
- Admin ingest upserts ComicVine issues into canonical series, volume, item, edition, variant, and release records
- IGDB and TMDb providers are scaffolded for future game and Blu-ray metadata
- Provider image URLs are preferred by default; set `MIRROR_PROVIDER_IMAGES=true` only when you want to copy public provider covers into MinIO/S3

---

## 🏗 Architecture

The backend is a FastAPI modular monolith:

- `api`: routers and HTTP schemas
- `services`: business logic and metadata ingest rules
- `repositories`: SQLAlchemy database access
- `providers`: external metadata adapters
- `worker`: background indexing and image jobs
- `search`: Meilisearch integration
- `storage`: MinIO/S3 object storage

The Flutter app keeps client models separate from backend database models:

- `core/api`: REST client
- `core/db`: Drift local database
- `features/comics`: first MVP feature
- `features/collection`: local-only ownership and wishlist state
- `features/games` and `features/bluray`: expansion placeholders
- `state`: Riverpod providers
- `ui`: shared UI components

---

## 🎯 Supported Collectible Types

| Type | MVP Status | Provider |
|------|------------|----------|
| Comics | Active MVP | ComicVine |
| Games | Scaffolded | IGDB |
| Blu-rays | Scaffolded | TMDb |
| Manga | Schema-ready | Future provider |
| Anime | Schema-ready | AniList |
| Movies / TV | Schema-ready | TMDb |
| Board games | Schema-ready | BGG |
| Books | Schema-ready | OpenLibrary |
| Music | Schema-ready | MusicBrainz |

---

## 🚀 Quick Start

```powershell
Copy-Item .env.example .env
docker compose --profile sync up --build -d
```

Apply migrations and seed development comics data:

```powershell
docker compose exec api alembic upgrade head
docker compose exec api python -m app.scripts.seed_comics
```

To bootstrap an admin account, set `BOOTSTRAP_ADMIN_EMAILS=["you@example.com"]` before registering that email.

Optional ComicVine live metadata:

```powershell
$env:COMICVINE_API_KEY="your-key"
# or set COMICVINE_API_KEY in .env before starting Docker
```

Open:

- API: http://localhost:8010
- Docs: http://localhost:8010/docs
- Admin UI: http://localhost:8010/admin/ui
- Sync service: http://localhost:8020
- Meilisearch: http://localhost:7700
- MinIO Console: http://localhost:9001

If PowerShell cannot find `docker`, Docker Desktop is installed at:

```powershell
& "C:\Program Files\Docker\Docker\resources\bin\docker.exe" compose --profile sync up --build -d
```

---

## 🐳 Docker

The local stack includes:

- FastAPI backend
- background worker
- PostgreSQL
- Redis
- Meilisearch
- MinIO
- optional `collectarr-sync` personal sync service

Common commands:

```powershell
.\tools\dev.ps1 start
.\tools\dev.ps1 migrate
.\tools\dev.ps1 seed
.\tools\dev.ps1 test-backend
```

Optional personal sync service:

```powershell
docker compose --profile sync up --build sync
```

The sync service is separate from the central metadata backend and uses `SYNC_API_KEY` plus its own SQLite database volume.

Reset the local pre-release development stack when schemas drift:

```powershell
.\scripts\dev-reset-stack.ps1 -WithSync
```

Low-write development settings for SSDs:

```env
MIRROR_PROVIDER_IMAGES=false
WORKER_INDEX_INTERVAL_SECONDS=3600
```

Admin metadata endpoints:

- `POST /admin/providers/search` - provider search, admin auth required
- `POST /admin/providers/ingest` - fetch, normalize, and upsert provider metadata, admin auth required

---

## 🔄 Sync / Offline Mode

Clients write personal collection data to the local Drift database. The central backend intentionally stores only shared metadata, provider IDs, images, search indexes, auth/admin identity, and operational state.

Multi-device sync lives in a separate self-hosted service:

- `collectarr-sync`: user-hosted personal database bridge
- app clients can point mobile, desktop, and web builds at that service
- the central metadata server remains stateless with respect to personal libraries

See [docs/sync.md](docs/sync.md) for the boundary and service shape.

---

## 🗺 Roadmap

See [docs/implementation-plan.md](docs/implementation-plan.md) for the current phase plan, completed work, and next PR sequence.

---

## 🔄 Releases

Collectarr uses **semantic-release** with Conventional Commits. Releases are manual only through the GitHub `Release` workflow.

- Use Conventional Commits: `feat: ...`, `fix: ...`, `chore: ...`
- Breaking changes: use `!` or a `BREAKING CHANGE:` footer
- Release notes are grouped in the pylrcget style: Features, Fixes, Refactors, CI & Build, Docs, Tests, Breaking Changes, and Other Changes
- Initial release assets include source, Docker/OpenAPI metadata, and Flutter web artifacts

---

## 🛠 Troubleshooting

- **API cannot connect to Postgres** - run `docker compose ps` and verify the `postgres` service is healthy.
- **Search returns no results** - run the seed command, then wait for the worker to index items.
- **`column items.release_type does not exist`** - your Docker PostgreSQL volume was created from an older pre-release schema; run `.\scripts\dev-reset-stack.ps1 -WithSync`.
- **MinIO writes too much in dev** - keep `MIRROR_PROVIDER_IMAGES=false`; public provider covers will remain external URLs.
- **MinIO image URLs fail for hosted assets** - verify `S3_PUBLIC_URL` and bucket settings in `.env`.
- **Cover upload works but public URL fails** - keep `S3_MANAGE_PUBLIC_READ_POLICY=true` for local MinIO, or configure your external bucket/CDN policy manually.
- **Flutter cannot reach the API** - use a platform-specific base URL when testing on emulators or physical devices.

---

## 🤝 Contributing

PRs are welcome! Please:

- Keep commits small and conventional.
- Run backend and Flutter checks before submitting.
- Keep personal library data out of the central metadata backend.

---

## 📄 License

MIT © saitatter
