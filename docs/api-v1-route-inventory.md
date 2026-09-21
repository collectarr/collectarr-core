# API v1 route inventory

`/api/v1` is the canonical composition root for Core. The route inventory is
generated from the mounted FastAPI application by
`app.api.route_inventory.build_route_inventory`.

## Composition

The v1 root mounts the system, auth, images, metadata, and admin route
contributors. The old paths are mounted separately by `app.api.legacy` only as
explicit aliases for routes that already existed before v1.

New endpoints must be added to the v1 composition root first. They must not be
added to the legacy alias router.

## Canonical examples

| Area | Canonical path | Existing alias |
| --- | --- | --- |
| Health | `/api/v1/health` | `/health` |
| Auth | `/api/v1/auth/login` | `/auth/login` |
| Typed catalog | `/api/v1/metadata/books/works/{work_id}` | `/metadata/books/works/{work_id}` |
| Search | `/api/v1/search` | `/search` |
| Canonical correction proposal | `/api/v1/metadata/correction-proposals` | none |

The correction proposal endpoint is intentionally v1-only: it is a new
provider-independent contract and is not exposed as a legacy alias.
