# Deployment

## Single Machine

Use Docker Compose for a self-hosted deployment on consumer hardware:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m app.scripts.seed_comics
```

For live GCD-backed comics metadata, run a dry run first and then ingest with
duplicate skipping:

```powershell
docker compose exec api python -m app.scripts.ingest_gcd --series "Batman" --issue 12 --dry-run
docker compose exec api python -m app.scripts.ingest_gcd --series "Batman" --from-issue 1 --to-issue 12 --skip-existing
```

Back up:

- PostgreSQL volume or logical `pg_dump`
- MinIO bucket data
- `.env` secrets outside the repository.

## Corporate Networks Without Docker Hub

The Compose stack references public base/service images for PostgreSQL, Redis,
Meilisearch, MinIO, and the Python build images used by the backend and sync
Dockerfiles. In networks where Docker Hub is blocked, do not rely on first-run
pulls during deployment.

Recommended options:

- mirror the required images into an internal registry and point Compose at
  those names with the image variables from `.env`
- pre-load approved image tarballs on the host before running Compose
- run the backend and `collectarr-sync` directly with Python 3.12 when managed
  PostgreSQL, Redis, Meilisearch, and S3-compatible storage are available.

GitHub Container Registry is a viable mirror target when `ghcr.io` is allowed by
the corporate network, but the Docker Hub image names are not automatically
available there. This repository includes a `Mirror Container Images` GitHub
Actions workflow that copies the required Docker Hub images into GHCR under the
repository owner. After it runs, set values such as:

```env
POSTGRES_IMAGE=ghcr.io/your-org/collectarr-postgres:16-alpine
REDIS_IMAGE=ghcr.io/your-org/collectarr-redis:7-alpine
MEILI_IMAGE=ghcr.io/your-org/collectarr-meilisearch:v1.13
MINIO_IMAGE=ghcr.io/your-org/collectarr-minio:RELEASE.2025-04-22T22-12-26Z
API_PYTHON_BASE_IMAGE=ghcr.io/your-org/collectarr-python:3.14-slim
SYNC_PYTHON_BASE_IMAGE=ghcr.io/your-org/collectarr-python:3.12-slim
```

Run it manually from GitHub Actions after the workflow is on the default branch.
If Docker Hub rate limits become a problem, add `DOCKERHUB_USERNAME` and
`DOCKERHUB_TOKEN` repository secrets; the workflow will use them automatically.
For local pulls from private GHCR packages, log in with a token that has
`read:packages`, or make the mirrored packages public in GitHub Packages.

Keep the production `.env` separate from development defaults. The local Compose
configuration uses bind mounts, reload processes, and sample credentials; treat
it as a development baseline rather than a hardened production manifest.

## Cloud

The API and worker are stateless containers. Scale them separately from storage:

- PostgreSQL for source-of-truth metadata and operational data
- Redis for cache/queues
- Meilisearch for derived search indexes
- S3-compatible storage for images
- optional CDN in front of image URLs.

Run migrations explicitly during deployment. Do not let app startup mutate schema.

## Local Schema Reset

Before the first public release, local schema changes may be destructive. If the API reports missing columns such as `items.release_type`, the Docker PostgreSQL volume was created from an older development schema. Reset the local stack:

```powershell
.\scripts\dev-reset-stack.ps1 -WithSync
```

Use `-KeepImages` to preserve MinIO data, or `-KeepSearchIndex` to preserve Meilisearch data.

## SSD And Logs

The default Compose stack is tuned for local development:

- PostgreSQL checkpoints are less frequent than the image default.
- Checkpoint log lines are disabled.
- API and sync access logs are disabled to avoid writing one Docker log line for every health/status request.
- Docker JSON logs are rotated at `10m` with three retained files per service.
- The metadata worker polls every `WORKER_INDEX_INTERVAL_SECONDS` seconds and only rebuilds the Meilisearch index when catalog tables changed.
- Public provider image URLs are stored as URLs by default, without copying covers into MinIO.
- Object storage bucket setup is cached per process, so repeated image uploads do not rewrite MinIO bucket policy each time.

PostgreSQL checkpoint lines such as `wrote 331 buffers` are normal and usually small. The `write=33s` value means PostgreSQL spread the write work over that interval; the `sync` duration is the part that more directly reflects waiting for disk flushes.

For a lower-write development stack, keep this in `.env`:

```env
MIRROR_PROVIDER_IMAGES=false
WORKER_INDEX_INTERVAL_SECONDS=3600
```

With image mirroring disabled, provider ingest keeps external cover URLs and avoids downloading covers into MinIO. MinIO/S3 remains the place for manual uploads, generated assets, or providers without stable public cover URLs. If you want a fully self-contained catalog, set `MIRROR_PROVIDER_IMAGES=true` and place MinIO/S3 data on storage you are comfortable writing to. Mirrored provider covers are normalized to a single WebP asset per source image; clients reuse that same asset for grids and detail views.

## Readiness

The Compose stack uses health checks for PostgreSQL, Redis, Meilisearch, and MinIO. The API exposes `/health`, which checks all backing services and returns `degraded` when one is unavailable.
