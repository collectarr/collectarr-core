# Collectarr Core

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub Release](https://img.shields.io/github/v/release/collectarr/collectarr-core)](https://github.com/collectarr/collectarr-core/releases)
[![Issues](https://img.shields.io/github/issues/collectarr/collectarr-core)](https://github.com/collectarr/collectarr-core/issues)
![Python](https://img.shields.io/badge/Python-3.14+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)

Collectarr Core owns the **source-neutral canonical catalog**: typed metadata,
catalog search, proposals/corrections, image delivery and administration. It
serves the nine kinds Music, Book, Comic, Manga, Movie, TV, Anime, Game and Board
Game. The Flutter app owns complete local entries; Sync carries personal library
snapshots between devices.

## Catalog architecture

Each kind has a separate typed root table and one aggregate per concrete
collectible edition/version/variant. Kind-specific repeated contents are typed
values in that root's JSONB document, not a generic Work/Release graph or
standalone disc/track/episode tables.

`CatalogKindDefinition` composes the model, document schemas, field declarations,
responses, proposal writers and routes. Truly independent reusable people,
organizations and groupings can retain identities where active workflows need them.

Music v2 keeps edition details and artist attribution on the album. Discs own
recording date, recording locations, Live/Studio, SPARS, technical data, credits
and tracks. Generic role credits can belong to album or disc; Composition is
track metadata. Format family is coarse, with an explicit family for a format.
Canonical APIs validate the declared shape and reject unsupported fields rather
than guessing old payload semantics.

Core has no provider-search/ingest runtime. User proposals contain the kind-owned
catalog fields accepted by Add/Edit. Personal status, copies, purchases, loans,
tracking, private notes and custom-field values belong to App/Sync.

## Services

- FastAPI API and worker, with PostgreSQL for typed catalog persistence.
- Meilisearch catalog indexing/query support and a scheduled index worker.
- Redis-backed infrastructure where configured.
- MinIO/S3 image storage, uploads, derived variants and admin cache diagnostics.
- Authentication, catalog review, duplicate inspection and audit/admin routes.
- Generated OpenAPI, field/identity contracts and database schema documentation.

Search supports stable offset pages (`items`, `next_offset`, `has_more`) and
kind-owned identifier matching. Duplicate merge is not available until references
can be remapped safely. Exact UI parity with CLZ is not a guarantee of this API.

## Start the local Docker stack

Docker Compose is the easiest way to run the services together. Configure a
**new, empty PostgreSQL database** for this model baseline. `create_all()` creates
missing objects; it does not reshape existing tables.

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose exec api python -m app.scripts.bootstrap_schema

# Optional deterministic development entries for all nine kinds:
docker compose exec api python -m app.scripts.seed_all_libraries
```

The seed also reindexes search unless `--skip-search-reindex` is supplied.
Use it in development, not against an existing user catalog. Preserve existing
databases/backups; there is no runtime schema conversion.

| Service | Local address |
| --- | --- |
| Core API | http://localhost:8010 |
| Swagger / OpenAPI | http://localhost:8010/docs / http://localhost:8010/openapi.json |
| Meilisearch | http://localhost:7700 |
| MinIO API / console | http://localhost:9000 / http://localhost:9001 |

Sync is **not** in the default Compose stack. To include its sibling checkout:

```powershell
$env:SYNC_PYTHON_BASE_IMAGE='python:3.14-slim'
.\tools\dev.ps1 start -WithSync
```

Review [docker-compose.devstack.yml](docker-compose.devstack.yml) for Sync's port,
volume and environment configuration.

## Configuration

[app/core/config.py](app/core/config.py) is the active configuration contract.
Important environment settings include:

| Settings | Purpose |
| --- | --- |
| `DATABASE_URL` | Async PostgreSQL connection |
| `SECRET_KEY`, `ENVIRONMENT`, `BOOTSTRAP_ADMIN_EMAILS` | Authentication and environment setup |
| `CORS_ORIGINS` | Allowed browser origins (JSON array) |
| `REDIS_URL`, `REDIS_TIMEOUT_SECONDS` | Redis connection/timeout |
| `MEILI_URL`, `MEILI_MASTER_KEY` | Search connection |
| `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_PUBLIC_URL`, S3 credentials | Image storage and public image base |
| `IMAGE_MAX_LONG_EDGE`, `IMAGE_QUALITY`, `MAX_IMAGE_BYTES`, `MAX_IMAGE_PIXELS` | Image processing bounds |
| `WORKER_INDEX_INTERVAL_SECONDS` | Index refresh interval |

Use Docker service hostnames inside the Compose network and localhost/LAN hosts
for tools running outside it. Set production secrets and public image URLs for
your deployment. See [deployment](docs/deployment.md),
[HTTPS and secrets](docs/https-and-secrets.md), [image pipeline](docs/image-pipeline.md)
and [unRAID setup](docs/unraid.md).

## Local development and checks

Use **Python 3.14+**, matching the package and CI configuration:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pip check
python -m ruff check .
python -m scripts.export_contract_bundle --check
```

Tests require an isolated PostgreSQL database. Point `DATABASE_URL` at that
existing test database, not your development/production catalog:

```powershell
$env:ENVIRONMENT='test'
$env:SECRET_KEY='test-secret'
$env:DATABASE_URL='postgresql+asyncpg://collectarr:collectarr@localhost:5432/collectarr_test'
python -m pytest
```

CI runs contract checks and PostgreSQL tests; its mypy step is informational.
See [.github/workflows/tests.yml](.github/workflows/tests.yml) for the exact gate.

## Generated contracts and schema docs

The authoritative bundle is [contracts](contracts): OpenAPI, active kinds,
metadata field schema, Catalog Item v2, Music v2 and a hash/version manifest.
Generate from source after changing a schema/route, then pin the bundle in App:

```powershell
python -m scripts.export_contract_bundle
python -m scripts.export_contract_bundle --check
python -m scripts.export_schema_site
python -m scripts.export_openapi
```

App's `tool/update_core_contracts.ps1` copies and verifies the bundle. Shared
contracts come from Core sources, not hand-maintained frontend allowlists.

- [Generated database snapshot](docs/schema-full.md).
- [Interactive schema explorer](https://collectarr.github.io/collectarr-core/schema.html).
- [Field schema](docs/field-schema.md).
- [Music canonical contract](docs/architecture/music-catalog-contract.md).
- [Search/index audit](docs/architecture/catalog-search-and-index-audit.md).
- [Current status](docs/current-status.md).

Historical status reports are dated evidence, not a substitute for current
source definitions or the active contract manifest.

## Releases and catalog badges

Pushes to `main` run CI. Container/release publication is triggered by
`workflow_dispatch` or a published GitHub release. The workflow supports build-only
and existing-release publication modes; see
[release.yml](.github/workflows/release.yml). Published images use
`ghcr.io/collectarr/collectarr-core`; choose an actual version from
[GitHub Releases](https://github.com/collectarr/collectarr-core/releases).

Catalog count badges are generated under [docs/badges](docs/badges).
[catalog-badges.yml](.github/workflows/catalog-badges.yml) can refresh them daily
or manually using the configured Core base URL and authorized credentials. They
are snapshots, not live counts embedded in this README.

## Related repositories and user documentation

| Repository | Responsibility |
| --- | --- |
| [collectarr-app](https://github.com/collectarr/collectarr-app) | Local entry storage, collection UI, editing, attachments and activity |
| [collectarr-sync](https://github.com/collectarr/collectarr-sync) | Optional complete-entry personal sync and explicit collection publications |
| `collectarr-site` | Product website and shared end-user manual, prepared in a separate local repo |

The user manual is opened by **Help → User Manual** in App. Initial site
publication is pending; Core's API/schema documentation remains separate.

## Support

[![Support on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/saitatter)
