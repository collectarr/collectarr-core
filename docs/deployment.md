# Deployment

## Single Machine

Use Docker Compose for a self-hosted deployment on consumer hardware:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m app.scripts.seed_comics
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

## Readiness

The Compose stack uses health checks for PostgreSQL, Redis, Meilisearch, and MinIO. The API exposes `/health`, which checks all backing services and returns `degraded` when one is unavailable.
