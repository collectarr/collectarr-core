# unRAID Deployment

This guide targets a personal unRAID host with Docker Compose, no public
domain, and no reverse proxy. It assumes you are exposing services on LAN IP
and port combinations such as `http://192.168.1.10:8010`.

## Topology

- `collectarr-app web` on `http://LAN_IP:8080`
- `collectarr-core` on `http://LAN_IP:8010`
- MinIO API on `http://LAN_IP:9000`
- MinIO console on `http://LAN_IP:9001`

PostgreSQL, Redis, and Meilisearch stay internal to the Compose network.

## Constraints

- This layout is appropriate for trusted LAN or VPN access.
- Without HTTPS, browser features are more fragile than desktop/mobile.
- The current web app talks to Sync directly, so the sync key is present in the
  browser client. Treat this deployment as personal-use, not public internet.
- If you need remote access, prefer VPN or Tailscale over direct port-forwarding.

## Prepare host storage

Create these directories on unRAID or update the paths in
`.env.unraid.example` before deploying:

- `/mnt/user/appdata/collectarr/postgres`
- `/mnt/user/appdata/collectarr/meili`
- `/mnt/user/appdata/collectarr/minio`

## Configure environment

1. Copy `.env.unraid.example` to `.env.unraid`.
2. Replace every placeholder secret.
3. Update `CORS_ORIGINS` to the exact app web origin you will serve.
4. Update `S3_PUBLIC_URL` to your unRAID LAN IP and MinIO port.
5. Set `BOOTSTRAP_ADMIN_EMAILS` if you want admin access bootstrapped.

Example values for a host at `192.168.1.10`:

```env
CORS_ORIGINS=["http://192.168.1.10:8080"]
S3_PUBLIC_URL=http://192.168.1.10:9000/collectarr-images
```

## Deploy the stack

From this repository root:

```bash
cp .env.unraid.example .env.unraid
docker compose --env-file .env.unraid -f docker-compose.unraid.yml up -d
docker compose --env-file .env.unraid -f docker-compose.unraid.yml exec api python -m app.scripts.bootstrap_alembic
```

Then verify:

```bash
curl http://LAN_IP:8010/health
```

`collectarr-sync` is intentionally not bundled in this Core stack. If you need
multi-device sync, deploy `collectarr-sync` separately from its own repository.

## Publish the web app

The `app_web` service pulls a prebuilt static web image from GHCR.

Default image:

- `ghcr.io/collectarr/collectarr-app-web:latest`

You can pin a specific release by setting `APP_WEB_IMAGE` in `.env.unraid`,
for example:

```env
APP_WEB_IMAGE=ghcr.io/collectarr/collectarr-app-web:v0.2.0
```

After changing image tags, redeploy the stack:

```bash
docker compose --env-file .env.unraid -f docker-compose.unraid.yml pull app_web
docker compose --env-file .env.unraid -f docker-compose.unraid.yml up -d app_web
```

## Pairing and clients

- Desktop and Android clients should use `http://LAN_IP:8010` for metadata and
  configure sync to point to your separate `collectarr-sync` deployment (if you run one).
- Web clients should use the same IP-based endpoints.
- Pairing codes are still useful on LAN, but they should only circulate inside
  your trusted environment.

## Backups

Back up separately:

- PostgreSQL data directory
- MinIO data directory
- `.env.unraid`
- exported web build if you want to restore the exact hosted UI revision

For restore procedures and service-specific backup details, see
`docs/deployment.md` and `../collectarr-sync/docs/sync.md`.