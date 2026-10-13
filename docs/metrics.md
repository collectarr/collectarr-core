# Metrics & Monitoring

Collectarr Core exposes operational data through built-in endpoints. No
external metrics stack is required, but the JSON responses can feed
Prometheus, Grafana, or simple scheduled checks.

## Health

```text
GET /api/v1/health
```

Use this for Docker health checks, load-balancer probes, and uptime monitors.

## Image Cache

```text
GET /api/v1/admin/images/stats
```

Returns cache size, entry count, and budget utilization. Monitor `used_bytes`
against `max_bytes` to anticipate storage pressure.

## Search Index

```text
GET /api/v1/admin/search/status
```

Returns Meilisearch connectivity, document count, and the last index time.

## Catalog

```text
GET /api/v1/admin/catalog/summary
```

Returns counts for canonical kind-specific entities, releases, people,
organizations, and tags.

## Audit Log

```text
GET /api/v1/admin/audit/logs
```

Returns recent admin actions. Review it after unexpected catalog changes or
administrative operations.

## Alerting Suggestions

| Condition | Check | Action |
|-----------|-------|--------|
| API down | `/api/v1/health` returns non-200 | Restart the API container |
| Image cache full | `stats.used_bytes > 0.95 * max_bytes` | Purge or increase the cache budget |
| Search unavailable | Search status reports a failed backend | Check Meilisearch connectivity |
| Search empty | `document_count == 0` with catalog data present | Trigger a reindex |
