from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from app.models.base import ExternalProvider, ItemKind
from app.providers.base import ProviderCapabilities, ProviderSearchResult
from app.services.provider_seed_service import (
    ProviderSeedCase,
    ProviderSeedManifest,
    ProviderSeedOptions,
    ProviderSeedService,
)


@dataclass
class _FakeProvider:
    name: str
    kind: ItemKind
    search_results: list[ProviderSearchResult]
    configured: bool = True
    supports_search: bool = True
    supports_ingest: bool = True

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            kind=self.kind,
            display_name=self.name,
            kinds=(self.kind,),
            supports_search=self.supports_search,
            supports_ingest=self.supports_ingest,
        )

    @property
    def is_configured(self) -> bool:
        return self.configured

    @property
    def status_message(self) -> str:
        return "configured" if self.configured else "missing config"

    async def search(self, query: str, kind: ItemKind | None = None) -> list[ProviderSearchResult]:
        assert query
        if kind is not None:
            assert kind == self.kind
        return list(self.search_results)


class _FakeRegistry:
    def __init__(self, providers: dict[str, _FakeProvider]) -> None:
        self.providers = providers

    def get(self, name: str | ExternalProvider) -> _FakeProvider:
        key = name.value if isinstance(name, ExternalProvider) else name
        return self.providers[key]


class _FakeSearchClient:
    def __init__(self, hits: list[dict[str, object]]) -> None:
        self.hits = hits
        self.calls: list[tuple[str, ItemKind | None, int]] = []

    async def search(self, query: str, kind: ItemKind | None = None, limit: int = 25):
        self.calls.append((query, kind, limit))
        return list(self.hits)


class _FakeAdminService:
    def __init__(self) -> None:
        self.ingest_calls: list[tuple[ExternalProvider, str]] = []
        self.job_calls: list[tuple[ExternalProvider, str]] = []

    async def ingest(self, payload):
        self.ingest_calls.append((payload.provider, payload.provider_item_id))
        return type(
            "Response",
            (),
            {
                "item_id": uuid4(),
                "created": True,
            },
        )()

    async def create_ingest_job(self, payload):
        self.job_calls.append((payload.provider, payload.provider_item_id))
        return type("Job", (), {"id": uuid4()})()

    async def run_ingest_job(self, job_id: UUID):
        return type("JobResponse", (), {"resolved_entity_id": uuid4(), "id": job_id})()


class _FakeDb:
    async def rollback(self) -> None:
        return None


def _manifest() -> ProviderSeedManifest:
    case = ProviderSeedCase(
        id="movie.tmdb.blade-runner",
        provider=ExternalProvider.tmdb,
        kind=ItemKind.movie,
        query="Blade Runner",
        expected_title="Blade Runner",
    )
    return ProviderSeedManifest(cases={case.id: case}, profiles={"smoke": (case.id,)})


@pytest.mark.asyncio
async def test_seed_case_dry_run_selects_expected_candidate_without_writing():
    candidate = ProviderSearchResult(
        provider="tmdb",
        provider_item_id="tmdb-1",
        title="Blade Runner",
        kind=ItemKind.movie,
    )
    provider = _FakeProvider("tmdb", ItemKind.movie, [candidate])
    service = ProviderSeedService(
        providers=_FakeRegistry({"tmdb": provider}),
        search_client=_FakeSearchClient([{"title": "Blade Runner"}]),
        manifest=_manifest(),
    )

    result = await service.run_case(
        _manifest().cases["movie.tmdb.blade-runner"],
        profile="smoke",
        options=ProviderSeedOptions(dry_run=True),
    )

    assert result.status == "dry-run"
    assert result.selected_provider_item_id == "tmdb-1"
    assert result.selected_title == "Blade Runner"


@pytest.mark.asyncio
async def test_seed_case_skips_unconfigured_provider_by_default():
    provider = _FakeProvider("tmdb", ItemKind.movie, [], configured=False)
    service = ProviderSeedService(
        providers=_FakeRegistry({"tmdb": provider}),
        manifest=_manifest(),
    )

    result = await service.run_case(
        _manifest().cases["movie.tmdb.blade-runner"],
        profile="smoke",
        options=ProviderSeedOptions(),
    )

    assert result.status == "skip"
    assert "not configured" in (result.reason or "")


@pytest.mark.asyncio
async def test_seed_case_skip_existing_avoids_ingest():
    candidate = ProviderSearchResult(
        provider="tmdb",
        provider_item_id="tmdb-1",
        title="Blade Runner",
        kind=ItemKind.movie,
    )
    admin = _FakeAdminService()
    service = ProviderSeedService(
        db=_FakeDb(),
        providers=_FakeRegistry({"tmdb": _FakeProvider("tmdb", ItemKind.movie, [candidate])}),
        search_client=_FakeSearchClient([{"title": "Blade Runner"}]),
        admin_service_factory=lambda _db: admin,
        manifest=_manifest(),
    )

    async def _provider_item_exists(*_args, **_kwargs):
        return True

    service._provider_item_exists = _provider_item_exists  # type: ignore[method-assign]

    result = await service.run_case(
        _manifest().cases["movie.tmdb.blade-runner"],
        profile="smoke",
        options=ProviderSeedOptions(skip_existing=True),
    )

    assert result.status == "skip"
    assert result.reason == "already linked to catalog"
    assert admin.ingest_calls == []


@pytest.mark.asyncio
async def test_seed_case_run_jobs_creates_and_runs_job():
    candidate = ProviderSearchResult(
        provider="tmdb",
        provider_item_id="tmdb-1",
        title="Blade Runner",
        kind=ItemKind.movie,
    )
    admin = _FakeAdminService()
    service = ProviderSeedService(
        db=_FakeDb(),
        providers=_FakeRegistry({"tmdb": _FakeProvider("tmdb", ItemKind.movie, [candidate])}),
        search_client=_FakeSearchClient([{"title": "Blade Runner"}]),
        admin_service_factory=lambda _db: admin,
        manifest=_manifest(),
    )

    async def _provider_item_entity_id(*_args, **_kwargs):
        return str(uuid4())

    service._provider_item_entity_id = _provider_item_entity_id  # type: ignore[method-assign]

    result = await service.run_case(
        _manifest().cases["movie.tmdb.blade-runner"],
        profile="smoke",
        options=ProviderSeedOptions(run_jobs=True),
    )

    assert result.status == "pass"
    assert result.search_verified is True
    assert admin.job_calls == [(ExternalProvider.tmdb, "tmdb-1")]


def test_filter_cases_limits_per_kind_and_filters_values():
    manifest = _manifest()
    extra = ProviderSeedCase(
        id="book.openlibrary.dune",
        provider=ExternalProvider.openlibrary,
        kind=ItemKind.book,
        query="Dune",
        expected_title="Dune",
    )
    service = ProviderSeedService(
        manifest=ProviderSeedManifest(
            cases={manifest.cases["movie.tmdb.blade-runner"].id: manifest.cases["movie.tmdb.blade-runner"], extra.id: extra},
            profiles={"smoke": (manifest.cases["movie.tmdb.blade-runner"].id, extra.id)},
        ),
    )

    filtered = service.filter_cases(
        service.cases_for_profile("smoke"),
        providers={ExternalProvider.openlibrary},
        kinds={ItemKind.book},
        limit_per_kind=1,
    )

    assert [case.id for case in filtered] == ["book.openlibrary.dune"]
