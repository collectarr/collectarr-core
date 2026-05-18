# Collectarr

<p align="center">
  <img src="docs/assets/collectarr-icon.svg" alt="Collectarr app icon" width="96" height="96">
</p>

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

Branding source assets live in [docs/assets](docs/assets); generated app icons
are checked in for Flutter web, Android, and Windows.

---

## ✨ Features

### 📚 Metadata Catalog

- Canonical metadata kept separate from personal library data
- Generalized work, series, release, edition, and variant hierarchy
- External provider IDs for GCD, ComicVine, IGDB, TMDb, AniList, BGG, OpenLibrary, MusicBrainz, and future providers
- Public provider cover URLs kept as references by default, with MinIO/S3 reserved for manual or non-public assets
- Meilisearch-backed fuzzy search with PostgreSQL fallback when the search index is unavailable
- See [docs/schema.md](docs/schema.md) for the database boundary and catalog schema

### 🧾 Personal Libraries

- Owned items, wishlist, purchase dates, prices, condition, grading, and notes are stored in the Flutter app's local Drift database
- Edition-aware and variant-aware local ownership records
- Runtime media library switcher for comics, manga, anime, movies, TV, games,
  books, board games, and music, backed by `/metadata/media-types` with an
  offline fallback
- Shared CLZ-style library workspace shell for catalog-defined libraries,
  including reusable toolbar chrome, search, view controls, utility menu,
  sidebar buckets, grids/lists/cards, and inspector layout
- Generic Add flows can search Core, search the configured live provider for
  manga/books/games/movies/TV/anime/board games/music, save provider candidates
  as local drafts, queue Core ingest jobs with visible job feedback, and submit
  metadata proposals for Core review. Core barcode misses automatically fall
  through to provider search when a library has configured providers.
- Non-comics libraries use media-aware field labels for add/detail/table/edit
  flows, such as video `Format / Edition`, book `ISBN / Barcode`, and game
  `Platform / Edition`
- CSV / CLZ import-export wizard for quick local backup and matched-row import,
  with media type-aware CSV matching, CLZ-friendly headers, edition titles,
  physical format fields, and barcode matching scoped by media type
- Local catalog snapshots preserve edition title, normalized physical format,
  physical format label, barcode/UPC/ISBN, and variant display data so synced
  clients can browse physical releases without rehydrating from Core
- The central metadata server does not store personal collection or wishlist records

### 🔄 Offline-First Sync

- Flutter clients work offline against a local database first
- The central server is metadata-only and does not expose personal `/collection` or `/sync` APIs
- Multi-device personal sync is reserved for a separate self-hosted `collectarr-sync` service
- The sync service is opt-in, user-owned infrastructure
- Conflict review shows local rejected payloads beside the service payload that
  won, so users can choose Keep service or queue a Keep local retry

### 🧩 Provider Plugins

- Provider abstraction for search, item fetch, and normalization
- GCD provider supports issue search/fetch without an API key for CC BY-SA bibliographic comics metadata
- ComicVine provider supports live comics and manga issue search/fetch when `COMICVINE_API_KEY` is set
- ComicVine search expands issue `associated_images` into variant cover
  candidates, and GCD series searches can merge those ComicVine cover
  candidates as controlled enrichment when the key is configured
- AniList provider supports live public anime and manga search/fetch without OAuth
- OpenLibrary provider supports live book search/fetch without an API key
- BoardGameGeek provider supports live board game search/fetch when `BGG_API_TOKEN` is set
- MusicBrainz provider supports live music release search/fetch without an API key
- IGDB provider supports live game search/fetch when Twitch/IGDB credentials are set
- TMDb provider supports live movie, TV, and anime search/fetch when
  `TMDB_API_READ_ACCESS_TOKEN` or `TMDB_API_KEY` is set
- Provider status reports compliance metadata such as attribution, redistribution, user-key, and non-commercial flags
- Admin ingest upserts provider records into canonical series, volume, item,
  edition, variant, and release records
- Admin catalog detail surfaces provider links, edition/variant cover status,
  item audit history, ingest job timelines, retry/backoff state, and cover URL
  inspection/replacement tools
- DVD, Blu-ray, 4K UHD, VHS, LaserDisc, and digital video are modeled as
  physical/digital formats on movie and TV editions/variants, not as top-level
  media types
- Flutter loads `/metadata/media-types` at runtime for media labels, route
  aliases, provider defaults, provider ordering, and physical format options;
  a local fallback keeps the app usable when Core is offline
- Admin catalog corrections can set a normalized video `physical_format`
  (`dvd`, `blu-ray`, `4k-uhd`, `vhs`, `laserdisc`, or `digital`) without a
  schema migration; the value is stored in edition/variant metadata and exposed
  in metadata responses and Flutter local snapshots
- Search and barcode lookup normalize UPC/ISBN/barcode punctuation and can match
  variant SKU values for game/video-style physical editions.
- Provider image URLs are preferred by default; set `MIRROR_PROVIDER_IMAGES=true`
  only when you want Core to copy provider covers into MinIO/S3 as one
  normalized WebP cover per source image, tracked in a bounded LRU cache. Core
  can apply that to provider ingest, external provider search results, and the
  GCD cover proxy. Core only mirrors providers explicitly marked
  image-mirroring safe unless `MIRROR_PROVIDER_IMAGES_ALLOW_RESTRICTED=true` is
  also set.
- Provider search is guarded by a dedicated Core rate limit, short-lived
  provider/kind/query caching, and provider cooldown after 401/429/5xx upstream
  errors. When `REDIS_URL` is set, those guardrails are shared across API
  processes; otherwise they fall back to local in-memory state. GCD can use
  ComicVine as controlled fallback/enrichment when enabled, and the Flutter add
  flow labels those provider results clearly.
- If GCD cover URLs are blocked by a browser or network, run `python -m app.scripts.enrich_comicvine_covers --replace-gcd-covers` with `COMICVINE_API_KEY` set to replace those cover references with ComicVine image URLs

---

## 🏗 Architecture

The backend is a FastAPI modular monolith:

- `api`: routers and HTTP schemas
- `services`: business logic and metadata ingest rules
- `repositories`: SQLAlchemy database access
- `providers`: external metadata adapters
- `worker`: background indexing, provider-ingest queue, and image jobs
- `search`: Meilisearch integration
- `storage`: MinIO/S3 object storage

The Flutter app keeps client models separate from backend database models:

- `core/api`: REST client
- `core/db`: Drift local database
- `features/comics`: first MVP feature
- `features/collection`: local-only ownership and wishlist state
- `features/library`: reusable media type configs, workspace adapters, shared
  workspace chrome, and local collection behavior
- `features/games`: expansion placeholder
- `state`: Riverpod providers
- `ui`: shared UI components

---

## 🎯 Supported Collectible Types

| Type | MVP Status | Provider |
|------|------------|----------|
| Comics | Active MVP, richest UX | GCD + ComicVine |
| Manga | Provider-ready, generic workspace | AniList + ComicVine |
| Books | Provider-ready, generic workspace | OpenLibrary |
| Games | Provider-ready, generic workspace | IGDB |
| Movies | Provider-ready, generic workspace | TMDb |
| Physical video | Edition/variant format | DVD, Blu-ray, 4K UHD, VHS, LaserDisc, digital |
| Anime | Provider-ready, generic workspace | AniList + TMDb |
| TV | Provider-ready, generic workspace | TMDb |
| Board games | Provider-ready, generic workspace | BGG |
| Music | Provider-ready, generic workspace | MusicBrainz |

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

To populate the catalog from live GCD issue metadata:

```powershell
docker compose exec api python -m app.scripts.ingest_gcd --series "Batman" --issue 12 --dry-run
docker compose exec api python -m app.scripts.ingest_gcd --series "Batman" --from-issue 1 --to-issue 12 --skip-existing
docker compose exec api python -m app.scripts.ingest_gcd --provider-item-id 256114 --skip-existing
```

To bootstrap an admin account, set `BOOTSTRAP_ADMIN_EMAILS=["you@example.com"]`
before registering that email. Existing accounts can be promoted or demoted from
the Core container:

```powershell
docker compose exec api python -m app.commands.set_admin you@example.com true
docker compose exec api python -m app.commands.set_admin you@example.com false
```

The Flutter Admin tab is shown only after signing in with an admin account. If
permissions are changed while a device is already signed in, refresh them from
Settings > Account or sign in again.

GCD live comics metadata works without a key. Optional ComicVine enrichment requires a personal
non-commercial API key:

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
.\tools\dev.ps1 smoke-web
.\tools\dev.ps1 smoke-providers
.\tools\dev.ps1 reset-pipeline
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

To automate the local Core + Sync + Flutter web smoke loop:

```powershell
.\scripts\dev-smoke-web.ps1 -WebPort 8083
```

The smoke script starts the sync profile, applies migrations, seeds dev comics,
adds the selected web origin to local CORS, builds Flutter web with local Core
and Sync URLs, serves `frontend/build/web`, and checks the health endpoints.

For a fully clean pre-release smoke pass, including Docker volumes, Flutter web
build output, provider search, a GCD-backed ingest job, and sync snapshot
roundtrip:

```powershell
.\scripts\dev-reset-pipeline.ps1 -Force -WebPort 8083
```

Useful narrower cleanup and smoke helpers:

```powershell
.\scripts\dev-clean-state.ps1 -CoreDb -SearchIndex -Sync -FlutterBuild -Logs -Force
.\scripts\dev-smoke-providers.ps1
```

`dev-clean-state.ps1` is scoped to local development volumes and repo-local
generated folders. It never removes Docker images. Use `-Images` only when you
want to clear the local MinIO image cache as well.

The local helper scripts auto-detect Docker Desktop failures and fall back to
`wsl docker` when a WSL Docker Engine is available, which keeps the dev loop
usable on corporate machines where Docker Hub/Desktop sign-in is blocked.
After a Core database reset, any already-open Flutter browser session may hold
an old metadata auth token; the app clears that stale session on the next
metadata 401 and asks for a fresh sign-in. If the browser was pointed at an
old local metadata or sync URL, open
`http://localhost:8083/?resetConnection=1` to clear only the saved connection
endpoints and return to the build defaults.

Low-write development settings for SSDs:

```env
MIRROR_PROVIDER_IMAGES=false
WORKER_INDEX_INTERVAL_SECONDS=3600
```

When `MIRROR_PROVIDER_IMAGES=true`, provider covers are normalized to one WebP
asset and tracked by `image_cache_entries`. Restricted providers such as
ComicVine, AniList, TMDb, BGG, IGDB, and GCD stay as external URLs by default;
set `MIRROR_PROVIDER_IMAGES_ALLOW_RESTRICTED=true` only for a self-hosted
instance where you accept the provider-specific image terms. The default cache
budget is 100 GB (`IMAGE_CACHE_MAX_BYTES`), with cleanup evicting
least-recently-used cached objects down to 85 GB
(`IMAGE_CACHE_EVICT_TARGET_BYTES`). See [docs/image-pipeline.md](docs/image-pipeline.md)
for the delivery modes and cover smoke checklist.

The worker also drains DB-backed provider ingest jobs. Tune the polling cadence
and batch size with `WORKER_PROVIDER_INGEST_INTERVAL_SECONDS` and
`WORKER_PROVIDER_INGEST_BATCH_SIZE`; jobs left in `running` longer than
`WORKER_PROVIDER_INGEST_STALE_AFTER_SECONDS` are requeued automatically. Admin
operators can inspect queue health, filter by status/provider/error text, retry
failed jobs, and run due queued jobs manually.

Core API errors include a stable `code` field next to `detail`. Auth endpoints,
provider search, and admin provider-triggering endpoints also have rate limits.
When `REDIS_URL` is configured those limits are shared through Redis; otherwise
Core falls back to in-process limits:

```env
AUTH_RATE_LIMIT_REQUESTS=20
AUTH_RATE_LIMIT_WINDOW_SECONDS=60
ADMIN_PROVIDER_RATE_LIMIT_REQUESTS=60
ADMIN_PROVIDER_RATE_LIMIT_WINDOW_SECONDS=60
PROVIDER_SEARCH_RATE_LIMIT_REQUESTS=30
PROVIDER_SEARCH_RATE_LIMIT_WINDOW_SECONDS=60
```

Admin metadata endpoints:

- `GET /metadata/media-types` - shared media type catalog, provider defaults, and physical format metadata
- `POST /admin/providers/search` - provider search, admin auth required
- `POST /admin/providers/ingest` - fetch, normalize, and upsert provider metadata, admin auth required
- `GET /admin/providers/ingest/jobs` - list DB-backed provider ingest jobs, optionally filtered by `status`, `provider`, and `q`
- `GET /admin/providers/ingest/jobs/summary` - inspect queued/running/failed/done counts, due jobs, stale running jobs, and recent failures
- `POST /admin/providers/ingest/jobs/run-pending` - run queued provider ingest jobs, admin auth required
- `GET /admin/audit/logs` - inspect persistent admin audit events for metadata corrections, duplicate actions, proposal decisions, and ingest queue actions

---

## 🔄 Sync / Offline Mode

Clients write personal collection data to the local Drift database. The central backend intentionally stores only shared metadata, provider IDs, images, search indexes, auth/admin identity, and operational state.

Multi-device sync lives in a separate self-hosted service:

- `collectarr-sync`: user-hosted personal database bridge
- app clients can point mobile, desktop, and web builds at that service
- Settings can keep the service version or queue a local retry when sync
  rejects a stale local change
- the central metadata server remains stateless with respect to personal libraries

See [docs/sync.md](docs/sync.md) for the boundary and service shape.

Import/export format decisions live in [docs/import-export.md](docs/import-export.md).

Barcode scanner release smoke tests live in
[docs/barcode-smoke-tests.md](docs/barcode-smoke-tests.md).

Backend tests are grouped by ownership under `backend/tests/admin`,
`backend/tests/providers`, `backend/tests/metadata`, `backend/tests/storage`,
`backend/tests/core`, and `backend/tests/scripts`; shared fixtures stay in
`backend/tests/conftest.py` and `backend/tests/helpers.py`.

---

## 🗺 Roadmap

See [docs/implementation-plan.md](docs/implementation-plan.md) for the current phase plan, completed work, and next PR sequence.

Current near-term focus:

- merge the admin/provider UI slice and run a full Core + Sync + Flutter smoke
- verify the provider candidate -> admin ingest/proposal -> Core search hit ->
  local add workflow against real providers
- verify GCD/ComicVine comics variant covers plus one generic provider flow for
  manga/books/games/video/music/board games as credentials allow
- continue richer media-specific edit/import templates after the current
  catalog snapshot fields

---

## 🔄 Releases

Collectarr uses **semantic-release** with Conventional Commits. Releases are manual only through the GitHub `Release` workflow.

- Use Conventional Commits: `feat: ...`, `fix: ...`, `chore: ...`
- Breaking changes: use `!` or a `BREAKING CHANGE:` footer
- Release notes are grouped in the pylrcget style: Features, Fixes, Refactors, CI & Build, Docs, Tests, Breaking Changes, and Other Changes
- Initial release assets include source, Docker/OpenAPI metadata, and Flutter web artifacts
- Pre-merge and post-release validation live in [docs/release-checklist.md](docs/release-checklist.md)

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
