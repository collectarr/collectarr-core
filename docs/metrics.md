# Metrics & Monitoring

Collectarr Core exposes operational data through built-in endpoints. No external
metrics stack is required, but the data can feed Prometheus, Grafana, or simple
cron-based checks.

## Health Endpoint

```
GET /health
```

Returns `200` with `{"status": "ok"}` when the API process is running. Use this
for Docker health checks, load balancer probes, and uptime monitors.

Docker Compose already configures a health check against this endpoint.

## Provider Health

```
GET /admin/providers/status
```

Returns per-provider configuration status, including whether each provider is
configured, its display name, and a human-readable status message. Use this to
verify that API keys are set correctly after deployment or rotation.

## Ingest Queue Metrics

```
GET /admin/providers/ingest/jobs/summary
```

Returns counts by job status (`queued`, `running`, `completed`, `failed`). Key
signals:

| Metric | Healthy | Investigate |
|--------|---------|-------------|
| `queued` | 0–20 | >100 sustained |
| `running` | 0–batch_size | stuck >30min |
| `failed` | 0 | any non-zero |

### Job list with filters

```
GET /admin/providers/ingest/jobs?status=failed&provider=comicvine&search=timeout
```

Filter by status, provider, or free-text search across provider_item_id and
error messages.

## Image Cache Stats

```
GET /admin/images/stats
```

Returns current cache size, entry count, and budget utilization. Monitor
`used_bytes` against `max_bytes` to anticipate storage pressure.

## Search Index Status

```
GET /admin/search/status
```

Returns Meilisearch connectivity, index document count, and last index time.

## Catalog Summary

```
GET /admin/catalog/summary
```

Returns total counts for items, editions, variants, releases, series, volumes,
people, organizations, and tags.

## Audit Log

```
GET /admin/audit-log
```

Returns recent admin actions (ingest, merge, corrections, queue operations).
Review after credential rotations or unexpected catalog changes.

## Prometheus Integration

The built-in endpoints return JSON. To expose Prometheus-format metrics, add a
lightweight exporter sidecar that polls the JSON endpoints:

```python
# Example: minimal /metrics scraper (not included in Core)
import httpx, time

while True:
    summary = httpx.get("http://api:8080/admin/providers/ingest/jobs/summary",
                        headers={"Authorization": f"Bearer {TOKEN}"}).json()
    # Emit prometheus text format lines
    for status, count in summary.items():
        print(f'collectarr_ingest_jobs{{status="{status}"}} {count}')
    time.sleep(60)
```

Alternatively, use a generic JSON-to-Prometheus exporter like
[json_exporter](https://github.com/prometheus-community/json_exporter).

## Alerting Suggestions

| Condition | Check | Action |
|-----------|-------|--------|
| API down | `/health` returns non-200 | Restart API container |
| Failed ingest jobs | `summary.failed > 0` | Check job list for errors |
| Queue backlog | `summary.queued > 50` | Increase batch size or check worker |
| Image cache full | `stats.used_bytes > 0.95 * max_bytes` | Trigger purge or increase budget |
| Search stale | `search.document_count == 0` | Check Meilisearch connectivity |
| Provider unconfigured | `status[provider].is_configured == false` | Set API keys in `.env` |
