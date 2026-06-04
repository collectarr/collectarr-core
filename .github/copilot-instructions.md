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
Franchise (optional) → Series → Volume → Item → Edition → Variant (+ Release)
```
- Models in `app/models/canonical.py` (SQLAlchemy 2.x async, `mapped_column`)
- Migrations: Alembic (`alembic/`)

### 10 Metadata Providers (`app/providers/`)
| Provider | File | Kinds | Auth |
|----------|------|-------|------|
| ComicVine | `comicvine.py` | comic, manga | API key |
| GCD | `gcd.py` | comic | None |
| Hardcover | `hardcover.py` | manga, book | API key |
| AniList | `anilist.py` | anime, manga | None (GraphQL) |
| MangaDex | `mangadex.py` | manga | None |
| TMDB | `tmdb.py` | movie, tv, anime | API key |
| OpenLibrary | `openlibrary.py` | book | None |
| IGDB | `igdb.py` | game | Twitch creds |
| BGG | `bgg.py` | boardgame | API token |
| MusicBrainz | `musicbrainz.py` | music | None |

Each provider implements: `search()` → `get_item()` → `normalize()` → `NormalizedItem`

### Services (`app/services/`)
- `metadata.py` — MetadataService: core search, provider coordination
- `admin.py` — AdminMetadataService: ingest, upsert, image mirroring
- `collection.py` — CollectionService: owned/wishlist CRUD
- `sync.py` — SyncService: client sync protocol

### Image Pipeline (`app/storage/`)
```
Provider URL → ImageMirror (download, validate, resize 1280px, WebP q82)
  → MinIO S3 (covers/{provider}/{id}/{hash}.webp)
  → ImageCache (DB tracking, LRU eviction at 100GB)
  → Public URL
```

### API Routes (`app/api/routes/`)
- `auth.py` — JWT register/login
- `metadata.py` — search, volumes, provider candidates
- `admin.py` — ingest, metadata corrections, image cache
- `collection.py` — owned items, wishlist, sync, facets

## Git and Releases

- Use conventional commits (`feat:`, `fix:`, `test:`, `chore:`, `refactor:`).
- Branch: `feat/file-reorg-and-hardcover`.

## Code Style

- Full type hints (`str | None`, not `Optional[str]`).
- All DB/HTTP operations async (`async def`, `await`).
- SQLAlchemy 2.x `mapped_column` style.
- Pydantic v2 for API schemas.
- Provider methods follow pattern: `_cover_url()`, `_normalize_credits()`, `_build_editions()`.

## Configuration (`app/core/config.py`)

Key env vars: `DATABASE_URL`, `REDIS_URL`, `MEILISEARCH_URL`, `S3_ENDPOINT_URL`, `COMICVINE_API_KEY`, `TMDB_API_KEY`, `TWITCH_CLIENT_ID/SECRET`, `MIRROR_PROVIDER_IMAGES`.

## Testing

- Run: `pytest` (inside Docker container or with venv)
- Test files in `tests/` mirror `app/` structure
- Provider tests mock HTTP responses
- Use `pytest -v tests/providers/test_musicbrainz_provider.py` for specific tests

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
