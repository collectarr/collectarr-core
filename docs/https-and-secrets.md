# HTTPS & Secrets Management

## TLS Termination

Collectarr Core does **not** terminate TLS itself. Place a reverse proxy in
front of the API and Admin Console:

| Proxy | Config snippet |
|-------|---------------|
| **Caddy** (recommended) | `reverse_proxy api:8080` — automatic HTTPS via Let's Encrypt |
| **Traefik** | Labels in `docker-compose.override.yml` with ACME resolver |
| **nginx** | `proxy_pass http://api:8080;` with `ssl_certificate` directives |

### Caddy example

```caddyfile
collectarr.example.com {
    reverse_proxy api:8080
}
```

Add the Caddy service to `docker-compose.override.yml`:

```yaml
services:
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
    depends_on:
      - api

volumes:
  caddy_data:
```

### Internal/LAN deployments

For LAN-only access without a public domain, use a self-signed certificate or a
local CA (e.g. [mkcert](https://github.com/FiloSottile/mkcert)):

```bash
mkcert -install
mkcert collectarr.local
```

Configure the proxy with the generated `.pem` files.

## Secrets Inventory

| Variable | Purpose | Rotation impact |
|----------|---------|-----------------|
| `SECRET_KEY` | JWT signing key | Invalidates all active sessions |
| `DATABASE_URL` | PostgreSQL connection string | Restart API + worker |
| `REDIS_URL` | Redis connection string | Restart API + worker |
| `MEILI_MASTER_KEY` | Meilisearch admin key | Restart API + worker, re-index |
| `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | MinIO/S3 credentials | Restart API + worker |
| `COMICVINE_API_KEY` | ComicVine provider | Restart API (hot-reloaded per request) |
| `IGDB_CLIENT_ID` / `IGDB_CLIENT_SECRET` | IGDB/Twitch credentials | Restart API |
| `TMDB_API_KEY` / `TMDB_API_READ_ACCESS_TOKEN` | TMDb provider | Restart API |
| `SYNC_API_KEY` | Sync service auth | Re-pair all devices |

## Secrets Rotation

### 1. `SECRET_KEY`

Changing the JWT signing key invalidates every issued token. Users must log in
again.

```bash
# Generate a new key
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Update `.env`, then restart:

```bash
docker compose up -d api worker
```

### 2. Database credentials

1. Create a new PostgreSQL role or update the password:
   ```sql
   ALTER ROLE collectarr WITH PASSWORD 'new-password';
   ```
2. Update `DATABASE_URL` in `.env`.
3. Restart API and worker.

### 3. MinIO/S3 credentials

1. Create new access keys in the MinIO console or your S3 provider.
2. Update `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` in `.env`.
3. Restart API and worker.
4. Revoke the old key.

### 4. Provider API keys

Provider keys (`COMICVINE_API_KEY`, `IGDB_CLIENT_SECRET`, `TMDB_API_KEY`) can be
rotated by updating `.env` and restarting. No data migration is needed — provider
metadata is cached locally.

### 5. `SYNC_API_KEY`

Changing the sync key requires all paired devices to re-authenticate. Update
`.env` in both `collectarr-core` and `collectarr-sync`, restart the sync
service, and re-pair devices from the Flutter app settings.

## Best Practices

- **Never commit `.env` to version control.** The `.gitignore` already excludes
  it.
- **Use different secrets per environment.** Development defaults in
  `.env.example` must not be reused in production.
- **Set `CORS_ORIGINS` explicitly for each deployment.** Match the allowed
  frontend origins for the environment you are running.
- **Back up `.env` separately** from database and image backups. Without the
  correct `SECRET_KEY`, existing sessions cannot be validated.
- **Restrict file permissions** on `.env`: `chmod 600 .env` on Linux.
- **Use Docker secrets or a vault** in orchestrated deployments (Swarm,
  Kubernetes). Mount secrets as files and reference them via `_FILE` suffix
  environment variables where supported.
- **Audit admin activity** via the built-in audit log (`/admin/audit-log`)
  after any credential rotation.
