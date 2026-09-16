# Copilot Instructions for collectarr-core

## Communication

- Raspunde in romana, concis si practic.
- Nu inventa comportamente; verifica in cod, teste sau documentatie locala.

## Project Context

- **collectarr-core** is a Python 3.14+ FastAPI backend for managing physical media collections.
- Serves the collectarr-app Flutter client via REST API.
- Runs in Docker Compose (WSL2 Ubuntu) with PostgreSQL 16, Redis 7, Meilisearch v1.13, MinIO S3.
- Entry point: `app/main.py`.

## Architecture

### Database Hierarchy
```
Item → Edition → Variant (+ Release)
```
- Keep the canonical catalog on the item/release spine; prefer per-kind work/release structures where they exist.
- Do not force shared legacy grouping layers onto kinds with native v1 models (music, boardgame, game).
- Models in `app/models/canonical.py` (SQLAlchemy 2.x async, `mapped_column`)
- Migrations: Alembic (`alembic/`). **Pre-2.0 policy: a single squashed baseline**
  (`alembic/versions/20260624_1000_clean_schema_baseline.py`, which runs
  `Base.metadata.create_all`). The server DB starts empty, so while the schema is
  still evolving we regenerate the baseline and recreate the DB instead of adding
  incremental migrations. `python -m app.scripts.bootstrap_alembic` builds a fresh
  DB from the baseline. Do NOT stack new migration files until the schema
  stabilizes — change the models and the baseline picks them up via `create_all`.
- Schema integrity lives in the models: non-negative CHECKs, a one-primary-per-edition
  partial unique index (`uq_variants_primary_per_edition`), and reverse foreign-key
  indexes on the polymorphic `entity_*` link tables. (A matching
  bundle membership is now modeled via `bundle_release_components`; update paths
  should delete removed members before inserting the new primary, otherwise the
  in-transaction primary swap trips the ordering invariant.)

### Provider contract (`app/providers/`)

Provider adapters and importers live in `collectarr-app`. Core owns the shared
normalized envelope, provenance, attribution, image references, and typed
canonical write contract. Keep provider-specific HTTP clients and credentials
out of Core.

### Services (`app/services/`)
- metadata services — typed catalog reads, search, and canonical writes
- admin services — corrections, duplicate review, image mirroring, and audit

### Image Pipeline (`app/storage/`)
```
Metadata image source → ImageMirror (download, validate, resize 1280px, WebP q82)
  → MinIO S3 (covers/{source}/{id}/{hash}.webp)
  → ImageCache (DB tracking, LRU eviction at 100GB)
  → Public URL
```

### API Routes (`app/api/routes/`)
- `auth.py` — JWT register/login
- `metadata.py` — typed catalog reads and normalized metadata submissions
- `admin.py` — metadata corrections, image cache, and audit

## Git and Releases

- Use conventional commits (`feat:`, `fix:`, `test:`, `chore:`, `refactor:`).
- Branch: `feat/file-reorg-and-hardcover`.

## Code Style

- Full type hints (`str | None`, not `Optional[str]`).
- All DB/HTTP operations async (`async def`, `await`).
- SQLAlchemy 2.x `mapped_column` style.
- Pydantic v2 for API schemas.

## Configuration (`app/core/config.py`)

Key env vars: `DATABASE_URL`, `REDIS_URL`, `MEILISEARCH_URL`, `S3_ENDPOINT_URL`, `MIRROR_PROVIDER_IMAGES`.

## Testing

- Run: `pytest` (inside Docker container or with venv)
- Test files in `tests/` mirror `app/` structure
- Contract tests cover normalized envelopes and typed canonical writes

## Docker Commands (from Windows)

```powershell
# Start
wsl -d Ubuntu -- docker compose -f /path/to/docker-compose.yml up -d

# Logs
wsl -d Ubuntu -- docker compose -f /path/to/docker-compose.yml logs -f app

# Restart backend
wsl -d Ubuntu -- docker compose -f /path/to/docker-compose.yml restart app

# Run tests
wsl -d Ubuntu -- docker compose -f /path/to/docker-compose.yml exec app pytest

# Get WSL2 IP (for Flutter client connection)
wsl hostname -I
```
