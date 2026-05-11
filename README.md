# Collectarr

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![GitHub Release](https://img.shields.io/github/v/release/saitatter/collectarr)
[![Issues](https://img.shields.io/github/issues/saitatter/collectarr)](https://github.com/saitatter/collectarr/issues)
![Made with Python](https://img.shields.io/badge/Made%20with-Python-3776AB?logo=python&logoColor=white)
![Flutter](https://img.shields.io/badge/Flutter-02569B?logo=flutter&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Web%20%7C%20Mobile%20%7C%20Desktop-lightgrey)

> Self-hosted metadata and library management for comics, games, Blu-rays, manga, and other collectibles.

Collectarr is a centralized collector metadata hub with personal libraries, variant-aware catalog records, offline-first sync, and plugin-based metadata providers. It starts with a comics MVP while keeping the schema and client architecture ready for more collectible types.

---

## ✨ Features

### 📚 Metadata Catalog

- Canonical metadata separated from user-owned library data
- Franchise, series, volume, item, edition, variant, and release hierarchy
- External provider IDs for ComicVine, IGDB, TMDb, and future providers
- Meilisearch-backed fuzzy search with PostgreSQL fallback

### 🧾 Personal Libraries

- User collections with owned items, wishlist-ready schema, notes, tags, condition, and grading
- Edition-aware and variant-aware ownership records
- Soft-delete tombstones for syncable user data

### 🔄 Offline-First Sync

- Flutter client stores local data and pending changes
- Server accepts diffs and returns ordered updates since a timestamp
- Initial conflict policy is last-write-wins
- Device IDs are included in the sync contract for multi-device workflows

### 🧩 Provider Plugins

- Provider abstraction for search, item fetch, and normalization
- ComicVine provider is the first live target
- IGDB and TMDb providers are scaffolded for future game and Blu-ray metadata

---

## 🏗 Architecture

The backend is a FastAPI modular monolith:

- `api`: routers and HTTP schemas
- `services`: business logic and sync rules
- `repositories`: SQLAlchemy database access
- `providers`: external metadata adapters
- `worker`: background indexing and image jobs
- `search`: Meilisearch integration
- `storage`: MinIO/S3 object storage

The Flutter app keeps client models separate from backend database models:

- `core/api`: REST client
- `core/db`: Drift local database
- `core/sync`: offline queue and sync orchestration
- `features/comics`: first MVP feature
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

---

## 🚀 Quick Start

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Apply migrations and seed development comics data:

```powershell
docker compose exec api alembic upgrade head
docker compose exec api python -m app.scripts.seed_comics
```

To bootstrap an admin account, set `BOOTSTRAP_ADMIN_EMAILS=["you@example.com"]` before registering that email.

Open:

- API: http://localhost:8010
- Docs: http://localhost:8010/docs
- Meilisearch: http://localhost:7700
- MinIO Console: http://localhost:9001

---

## 🐳 Docker

The local stack includes:

- FastAPI backend
- background worker
- PostgreSQL
- Redis
- Meilisearch
- MinIO

Common commands:

```powershell
.\tools\dev.ps1 start
.\tools\dev.ps1 migrate
.\tools\dev.ps1 seed
.\tools\dev.ps1 test-backend
```

---

## 🔄 Sync / Offline Mode

Clients write local changes to a Drift-backed sync queue. The backend exposes:

- `POST /sync/push`
- `POST /sync/pull`
- `GET /sync/changes?since=`

See [docs/sync.md](docs/sync.md) for the wire format and conflict policy.

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
- **MinIO image URLs fail** - verify `S3_PUBLIC_URL` and bucket settings in `.env`.
- **Flutter cannot reach the API** - use a platform-specific base URL when testing on emulators or physical devices.

---

## 🤝 Contributing

PRs are welcome! Please:

- Keep commits small and conventional.
- Run backend and Flutter checks before submitting.
- Keep canonical metadata separate from personal library data.

---

## 📄 License

MIT © saitatter
