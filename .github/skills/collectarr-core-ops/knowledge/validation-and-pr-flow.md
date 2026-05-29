# Validation And PR Flow Knowledge

## Focused validation commands

For image and worker changes that touch perceptual hashing or upload/search flows:

```powershell
python -m pytest tests/core/test_images_api.py -q
python -m pytest tests/core/test_worker.py -q
```

For provider-ingest follow-ups:

```powershell
python -m pytest tests/admin/test_admin_ingest.py -q
```

For admin-domain refactors without needing the full DB-backed suite:

```powershell
pytest tests/admin/test_admin_services.py -q
```

For lint-only cleanup in touched backend files:

```powershell
python -m ruff check app/services/admin.py app/services/admin_domains/overview.py app/services/admin_domains/support.py --select F401
```

When the touched slice is green and the task warrants it:

```powershell
python -m pytest
```

Known recent baseline:
- a full post-integration run passed with `273 passed`

## Protected main flow

`origin/main` is protected:
- direct pushes are rejected
- merge commits are not allowed
- required checks must pass through a PR

For larger landing work:
1. sync from `origin/main`
2. create a linear branch from it
3. apply the validated diff there
4. push the branch
5. open or update the PR

## Known backend gotchas

- Typed provider-link models expose `entity_type` as a Python property for serialization compatibility; do not select it directly in SQLAlchemy queries.
- Use eager-loaded or separately-fetched provider-link rows instead of relying on lazy loads during response serialization.
