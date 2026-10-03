# Collectarr Core

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![GitHub Release](https://img.shields.io/github/v/release/collectarr/collectarr-core)
[![Issues](https://img.shields.io/github/issues/collectarr/collectarr-core)](https://github.com/collectarr/collectarr-core/issues)
![Made with Python](https://img.shields.io/badge/Made%20with-Python-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?logo=sqlalchemy&logoColor=white)
![Docker](https://img.shields.io/badge/Deploy-Docker-2496ED?logo=docker&logoColor=white)

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

> Shared source-neutral catalog for Collectarr: canonical metadata, user-submitted catalog proposals, image delivery, admin tooling, and search infrastructure.

Collectarr Core owns canonical catalog data and its read/write contract. The
project has no provider search or ingest subsystem. User proposals remain
available: the App submits the same kind-owned catalog fields shown by manual
Add/Edit, and moderators review them as catalog data. Core must not receive
owned-copy or other personal state. Personal data stays in `collectarr-app` and
can optionally sync through `collectarr-sync`.

---

## ✨ Features

### 📚 Canonical Catalog

- Multi-media catalog covering comics, manga, anime, books, games, board games, movies, TV, and music
- One root item per concrete edition with typed, kind-owned JSONB documents for media, tracks, episodes, credits, identifiers, and other contained values
- Independent reusable people, organizations, series groupings, story arcs, and shared editorial tags where their identities are needed
- Kind-aware search and admin responses backed by Core-owned catalog fields
- Shared editorial metadata that complements local-first personal data in the app

### 🔎 Catalog Proposals And Search

- Source-neutral user proposals carry the same Catalog Item fields as manual Add/Edit
- Moderators can review, edit, approve, or reject submitted catalog data
- Optional Meilisearch indexing for catalog queries

### 🖼️ Image And Storage Infrastructure

- External image URLs by default, with optional MinIO / S3 mirroring for controlled hosting
- Image URL normalization, cache budgeting, and origin tracking
- Content-addressed image handling for uploaded assets and derived media variants
- Image cache health surfaced through admin tooling instead of ad hoc scripts

### 🛠️ Admin And Operations

- Admin dashboard in the Collectarr desktop app for catalog review, duplicate handling, user management, image cache stats, and audit logs
- Role-based access with viewer / editor / admin permissions
- OpenAPI docs at `/docs` for API exploration and schema-backed integration work
- Daily-refreshable catalog badges and machine-readable contract snapshots

---

## 🧱 Database Schema

The generated schema docs stay in sync with SQLAlchemy metadata and include
columns, enums, indexes, defaults, unique constraints, and cross-domain
references.

- [Open interactive schema explorer](https://collectarr.github.io/collectarr-core/schema.html)
- [Open generated markdown snapshot](docs/schema-full.md)
- Refresh locally with `python -m scripts.export_schema_site` or keep it live with `python -m scripts.export_schema_site --watch`.

### Schema bootstrap

The server database is created directly from the typed SQLAlchemy models. Use a
new, empty database for this baseline, then run
`python -m app.scripts.bootstrap_schema`. `create_all()` does not reshape an
existing schema. Keep existing databases and backups untouched; do not point
the new baseline at an existing database.

---

## 🚀 Quick Start

### Start the Docker stack

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose exec api python -m app.scripts.bootstrap_schema
docker compose exec api python -m app.scripts.seed_comics
```

Before bootstrapping, configure the stack to use a new empty PostgreSQL database.
Do not delete or reuse an existing database as part of this setup.

### Run local development tooling

```powershell
python -m pip install -e .[dev]
python -m ruff check .
python -m pytest
```

### Common helper commands

```powershell
.\tools\dev.ps1 start            # Start Docker stack
.\tools\dev.ps1 start -WithSync  # Start Core + collectarr-sync dev stack
.\tools\dev.ps1 schema           # Create the schema from SQLAlchemy models
.\tools\dev.ps1 seed             # Seed sample comics data
.\tools\dev.ps1 test             # Run test suite
.\tools\dev.ps1 check            # Lint + type check
.\tools\dev.ps1 reset-stack      # Clean reset of containers and volumes
```

---

## 🧩 Extending Metadata For New Libraries

Core is the canonical source of cross-library metadata. When a kind needs a new
catalog field, define it in the kind-owned schema and include it in the
source-neutral API and proposal contract.

1. Add the typed field to the kind's canonical schema and API contract.
2. Persist it in the appropriate kind-specific table or relation.
3. Add it to Meilisearch documents and display attributes when it should affect search UX.
4. Keep field names stable so `collectarr-app` can cache and render the same canonical shape offline.

---

## 🌐 Local URLs

| Service | URL |
|---------|-----|
| API | http://localhost:8010 |
| API docs (Swagger) | http://localhost:8010/docs |
| Sync service | http://localhost:8020 |
| Meilisearch | http://localhost:7700 |
| MinIO console | http://localhost:9001 |

---

## 🔄 Releases

Release publishing is manual-only. The `Release` GitHub Actions workflow uses
`workflow_dispatch`; pushing to `main` runs CI only and never auto-publishes.

Current beta release: `v0.2.0`

Current backend image tags:

- `ghcr.io/collectarr/collectarr-core:v0.2.0`
- `ghcr.io/collectarr/collectarr-core:latest`

Release docs and container tags are kept in sync with the GitHub release state
before publishing.

When a releasable version is detected, the workflow publishes a GitHub Release
and pushes the backend container image to `ghcr.io/collectarr/collectarr-core`
with both the semantic version tag and `latest`.

The first published GHCR package defaults to `private`. After the first real
release, open the package page in the `collectarr` organization and switch
`collectarr-core` to `public` before expecting anonymous `docker pull`
operations to work:

- `https://github.com/orgs/collectarr/packages/container/package/collectarr-core`

For personal LAN deployment on unRAID with Docker Compose, see
[docs/unraid.md](docs/unraid.md).

---

## 📈 Catalog Badges

The repo includes snapshot badges for total catalog items and per-kind item
counts. `.github/workflows/catalog-badges.yml` refreshes them on a daily
schedule or manual dispatch.

To switch from placeholder badges to live counts, configure:

- `COLLECTARR_BADGES_BASE_URL` for the public Core base URL (e.g., `COLLECTARR_BADGES_BASE_URL=http://localhost:8010`)
- `COLLECTARR_BADGES_TOKEN` for bearer-token access to `/api/v1/admin/catalog/summary`

Or, instead of a static token:

- `COLLECTARR_BADGES_EMAIL`
- `COLLECTARR_BADGES_PASSWORD`

The workflow logs in through `/api/v1/auth/login` when a bearer token is not provided.

---

## 🔗 Related Repos

| Repo | Purpose |
|------|---------|
| `collectarr-app` | Flutter client for local-first collection browsing, editing, and admin-facing UX |
| `collectarr-sync` | Optional personal sync service for multi-device shelf state |

## 🧭 Catalog Field Contract

See [docs/field-schema.md](docs/field-schema.md) for the generated editable
field schema, and [docs/implementation-plan.md](docs/implementation-plan.md)
for current cutover status. Music is grounded in the saved CLZ Music Edit form;
exact CLZ parity for the other eight kinds remains unverified pending their
Edit-form captures.

## 🗺️ Roadmap

See [docs/implementation-plan.md](docs/implementation-plan.md) for the full roadmap.

Current active tracks:

- move scalar editable field definitions from Core's shared metadata registry into kind-owned modules
- finish App's typed metadata and personal-data model while preserving its established UI
- finish the coordinated App/Sync payload cutover; Sync remains personal-data-only
- regenerate and pin the Core contract bundle after the field ownership changes
- expand duplicate review, keeping merge disabled until personal references can be remapped safely
- continue public-deployment hardening for internet-facing setups
- keep the interactive schema explorer clearer by separating general tables from kind-specific tables
- keep catalog proposals source-neutral and separate from App-owned personal data

---

## Support

If Collectarr is useful to you, you can support ongoing development on Ko-fi:

[![Support me on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/saitatter)
