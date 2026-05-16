import pytest

from app.db.session import AsyncSessionLocal
from app.schemas.admin import ProviderIngestJobRunResponse
from app.worker.main import (
    catalog_fingerprint,
    index_changed_catalog,
    run_pending_provider_ingest_jobs_best_effort,
)
from tests.helpers import seed_comic


@pytest.mark.asyncio
async def test_catalog_fingerprint_changes_when_catalog_changes():
    async with AsyncSessionLocal() as db:
        initial = await catalog_fingerprint(db)

    await seed_comic()

    async with AsyncSessionLocal() as db:
        updated = await catalog_fingerprint(db)

    assert updated != initial
    assert updated.item_count == 1
    assert updated.edition_count == 1
    assert updated.variant_count == 1
    assert updated.release_count == 0


@pytest.mark.asyncio
async def test_index_changed_catalog_keeps_last_fingerprint_on_index_failure():
    class FailingSearch:
        async def index_documents(self, documents):
            raise RuntimeError("index unavailable")

    async with AsyncSessionLocal() as db:
        initial = await catalog_fingerprint(db)

    await seed_comic()

    next_fingerprint = await index_changed_catalog(FailingSearch(), initial)

    assert next_fingerprint == initial


@pytest.mark.asyncio
async def test_run_pending_provider_ingest_jobs_best_effort_returns_result(monkeypatch):
    async def fake_run_pending_provider_ingest_jobs(limit):
        return ProviderIngestJobRunResponse(processed=2, recovered=1, jobs=[])

    monkeypatch.setattr(
        "app.worker.main.run_pending_provider_ingest_jobs",
        fake_run_pending_provider_ingest_jobs,
    )

    result = await run_pending_provider_ingest_jobs_best_effort(5)

    assert result is not None
    assert result.processed == 2
    assert result.recovered == 1


@pytest.mark.asyncio
async def test_run_pending_provider_ingest_jobs_best_effort_swallows_errors(monkeypatch):
    async def fail_run_pending_provider_ingest_jobs(limit):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        "app.worker.main.run_pending_provider_ingest_jobs",
        fail_run_pending_provider_ingest_jobs,
    )

    result = await run_pending_provider_ingest_jobs_best_effort(5)

    assert result is None
