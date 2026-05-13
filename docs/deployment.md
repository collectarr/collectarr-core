# Deployment

## Single Machine

Use Docker Compose for a self-hosted deployment on consumer hardware:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m app.commands.seed_comics
```

Back up:

- PostgreSQL volume or logical `pg_dump`
- MinIO bucket data
- `.env` secrets outside the repository.

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

PostgreSQL checkpoint lines such as `wrote 331 buffers` are normal and usually small. The `write=33s` value means PostgreSQL spread the write work over that interval; the `sync` duration is the part that more directly reflects waiting for disk flushes.

## Readiness

The Compose stack uses health checks for PostgreSQL, Redis, Meilisearch, and MinIO. The API exposes `/health`, which checks all backing services and returns `degraded` when one is unavailable.
