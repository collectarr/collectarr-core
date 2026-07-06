from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExternalProviderId
from app.models.base import ExternalProvider, ItemKind
from app.providers.base import MetadataProvider, ProviderSearchResult
from app.schemas.admin import ProviderIngestJobCreateRequest, ProviderIngestRequest
from app.search.client import SearchClient
from app.services.admin import AdminMetadataService

_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "scripts" / "provider_seed_manifest.json"


@dataclass(frozen=True)
class ProviderSeedCase:
    id: str
    provider: ExternalProvider
    kind: ItemKind
    query: str
    expected_title: str | None = None
    expected_title_contains: str | None = None


@dataclass(frozen=True)
class ProviderSeedCaseResult:
    id: str
    profile: str
    provider: str
    kind: str
    query: str
    status: str
    reason: str | None = None
    search_hits: int | None = None
    selected_provider_item_id: str | None = None
    selected_title: str | None = None
    item_id: str | None = None
    created: bool | None = None
    search_verified: bool | None = None
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderSeedManifest:
    cases: dict[str, ProviderSeedCase]
    profiles: dict[str, tuple[str, ...]]

    def cases_for_profile(self, profile: str) -> list[ProviderSeedCase]:
        case_ids = self.profiles.get(profile)
        if case_ids is None:
            raise KeyError(profile)
        return [self.cases[case_id] for case_id in case_ids]

    def profile_names(self) -> list[str]:
        return sorted(self.profiles)


@dataclass(frozen=True)
class ProviderSeedOptions:
    dry_run: bool = False
    skip_existing: bool = False
    run_jobs: bool = False
    require_configured: bool = False
    search_verify_limit: int = 5


class ProviderSeedService:
    def __init__(
        self,
        db: AsyncSession | None = None,
        *,
        providers: Any | None = None,
        search_client: SearchClient | None = None,
        admin_service_factory: Callable[[AsyncSession], Any] | None = None,
        manifest: ProviderSeedManifest | None = None,
    ) -> None:
        from app.providers.registry import ProviderRegistry

        self.db = db
        self.providers = providers or ProviderRegistry()
        self._search_client = search_client
        self._admin_service_factory = admin_service_factory or (lambda session: AdminMetadataService(session))
        self.manifest = manifest or load_provider_seed_manifest()

    def cases_for_profile(self, profile: str) -> list[ProviderSeedCase]:
        return self.manifest.cases_for_profile(profile)

    def filter_cases(
        self,
        cases: list[ProviderSeedCase],
        *,
        providers: set[ExternalProvider] | None = None,
        kinds: set[ItemKind] | None = None,
        limit_per_kind: int | None = None,
    ) -> list[ProviderSeedCase]:
        filtered = [
            case
            for case in cases
            if (providers is None or case.provider in providers)
            and (kinds is None or case.kind in kinds)
        ]
        if limit_per_kind is None:
            return filtered
        counts: dict[ItemKind, int] = {}
        limited: list[ProviderSeedCase] = []
        for case in filtered:
            count = counts.get(case.kind, 0)
            if count >= limit_per_kind:
                continue
            counts[case.kind] = count + 1
            limited.append(case)
        return limited

    async def run(
        self,
        cases: list[ProviderSeedCase],
        *,
        profile: str,
        options: ProviderSeedOptions,
    ) -> list[ProviderSeedCaseResult]:
        results: list[ProviderSeedCaseResult] = []
        for case in cases:
            results.append(await self.run_case(case, profile=profile, options=options))
        return results

    async def run_case(
        self,
        case: ProviderSeedCase,
        *,
        profile: str,
        options: ProviderSeedOptions,
    ) -> ProviderSeedCaseResult:
        provider = self._resolve_provider(case.provider)
        if provider is None:
            return self._result(
                case,
                profile,
                "skip",
                reason=f"provider '{case.provider.value}' is not configured",
            )
        if not provider.is_configured:
            status = "fail" if options.require_configured else "skip"
            return self._result(
                case,
                profile,
                status,
                reason=f"provider '{case.provider.value}' is not configured",
            )
        if not provider.capabilities.supports_search:
            return self._result(
                case,
                profile,
                "fail",
                reason=f"provider '{case.provider.value}' does not support search",
            )
        if not provider.capabilities.supports_ingest:
            return self._result(
                case,
                profile,
                "fail",
                reason=f"provider '{case.provider.value}' does not support ingest",
            )

        try:
            search_results = await provider.search(case.query, kind=case.kind)
        except Exception as exc:
            return self._result(case, profile, "fail", reason=f"search failed: {exc}")

        candidate = self._select_candidate(case, search_results)
        if candidate is None:
            return self._result(
                case,
                profile,
                "fail",
                reason="no matching provider candidate found",
                search_hits=len(search_results),
            )

        if options.dry_run:
            return self._result(
                case,
                profile,
                "dry-run",
                search_hits=len(search_results),
                selected_provider_item_id=candidate.provider_item_id,
                selected_title=candidate.title,
                notes=["no writes performed"],
            )

        if self.db is None:
            raise RuntimeError("provider seed requires a database session outside dry-run mode")

        if options.skip_existing and await self._provider_item_exists(case.provider, candidate.provider_item_id):
            return self._result(
                case,
                profile,
                "skip",
                reason="already linked to catalog",
                search_hits=len(search_results),
                selected_provider_item_id=candidate.provider_item_id,
                selected_title=candidate.title,
            )

        admin = self._admin_service_factory(self.db)
        try:
            if options.run_jobs:
                job = await admin.create_ingest_job(
                    ProviderIngestJobCreateRequest(
                        provider=case.provider,
                        provider_item_id=candidate.provider_item_id,
                    )
                )
                job_response = await admin.run_ingest_job(job.id)
                item_id = str(job_response.resolved_entity_id or job_response.id)
                created = None
            else:
                response = await admin.ingest(
                    ProviderIngestRequest(
                        provider=case.provider,
                        provider_item_id=candidate.provider_item_id,
                        kind=case.kind,
                    )
                )
                item_id = str(response.item_id)
                created = response.created
        except Exception as exc:
            await self.db.rollback()
            return self._result(
                case,
                profile,
                "fail",
                reason=f"ingest failed: {exc}",
                search_hits=len(search_results),
                selected_provider_item_id=candidate.provider_item_id,
                selected_title=candidate.title,
            )

        db_item_id = await self._provider_item_entity_id(case.provider, candidate.provider_item_id)
        search_verified = await self._verify_search(candidate, case, options.search_verify_limit)
        if not search_verified:
            return self._result(
                case,
                profile,
                "fail",
                reason="search index did not surface the ingested item",
                search_hits=len(search_results),
                selected_provider_item_id=candidate.provider_item_id,
                selected_title=candidate.title,
                item_id=str(db_item_id or item_id),
                created=created,
                notes=["ingest succeeded but search verification failed"],
            )

        return self._result(
            case,
            profile,
            "pass",
            search_hits=len(search_results),
            selected_provider_item_id=candidate.provider_item_id,
            selected_title=candidate.title,
            item_id=str(db_item_id or item_id),
            created=created,
            search_verified=True,
        )

    async def _verify_search(
        self,
        candidate: ProviderSearchResult,
        case: ProviderSeedCase,
        attempts: int,
    ) -> bool:
        search_client = self.search_client
        if search_client is None:
            return False
        query = case.expected_title or candidate.title or case.query
        for _ in range(max(1, attempts)):
            hits = await search_client.search(query, kind=case.kind, limit=10)
            if hits and any(self._hit_matches(hit, case, candidate) for hit in hits):
                return True
        return False

    def _hit_matches(
        self,
        hit: dict[str, Any],
        case: ProviderSeedCase,
        candidate: ProviderSearchResult,
    ) -> bool:
        title = str(hit.get("title") or "").casefold()
        expected_title = (case.expected_title or candidate.title).casefold()
        expected_contains = (case.expected_title_contains or "").casefold()
        if title == expected_title:
            return True
        if expected_contains and expected_contains in title:
            return True
        return case.query.casefold() in title

    async def _provider_item_exists(
        self,
        provider: ExternalProvider,
        provider_item_id: str,
    ) -> bool:
        if self.db is None:
            return False
        result = await self.db.scalar(
            select(ExternalProviderId.id).where(
                ExternalProviderId.provider == provider,
                ExternalProviderId.provider_item_id == provider_item_id,
            )
        )
        return result is not None

    async def _provider_item_entity_id(
        self,
        provider: ExternalProvider,
        provider_item_id: str,
    ) -> str | None:
        if self.db is None:
            return None
        entity_id = await self.db.scalar(
            select(ExternalProviderId.entity_id).where(
                ExternalProviderId.provider == provider,
                ExternalProviderId.provider_item_id == provider_item_id,
            )
        )
        return str(entity_id) if entity_id is not None else None

    @property
    def search_client(self) -> SearchClient | None:
        if self._search_client is None:
            try:
                self._search_client = SearchClient()
            except Exception:
                self._search_client = None
        return self._search_client

    def _resolve_provider(self, provider: ExternalProvider) -> MetadataProvider | None:
        try:
            return self.providers.get(provider)
        except KeyError:
            return None

    def _select_candidate(
        self,
        case: ProviderSeedCase,
        search_results: list[ProviderSearchResult],
    ) -> ProviderSearchResult | None:
        if not search_results:
            return None

        exact_title = case.expected_title.casefold() if case.expected_title else None
        contains_title = case.expected_title_contains.casefold() if case.expected_title_contains else None

        if exact_title is None and contains_title is None:
            return search_results[0]

        for result in search_results:
            title = result.title.casefold()
            if exact_title is not None and title == exact_title:
                return result
            if contains_title is not None and contains_title in title:
                return result
        return None

    def _result(
        self,
        case: ProviderSeedCase,
        profile: str,
        status: str,
        *,
        reason: str | None = None,
        search_hits: int | None = None,
        selected_provider_item_id: str | None = None,
        selected_title: str | None = None,
        item_id: str | None = None,
        created: bool | None = None,
        search_verified: bool | None = None,
        notes: list[str] | None = None,
    ) -> ProviderSeedCaseResult:
        return ProviderSeedCaseResult(
            id=case.id,
            profile=profile,
            provider=case.provider.value,
            kind=case.kind.value,
            query=case.query,
            status=status,
            reason=reason,
            search_hits=search_hits,
            selected_provider_item_id=selected_provider_item_id,
            selected_title=selected_title,
            item_id=item_id,
            created=created,
            search_verified=search_verified,
            notes=notes or [],
        )


def load_provider_seed_manifest(path: Path | None = None) -> ProviderSeedManifest:
    manifest_path = path or _MANIFEST_PATH
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = {
        case_id: ProviderSeedCase(
            id=case_id,
            provider=ExternalProvider(case["provider"]),
            kind=ItemKind(case["kind"]),
            query=case["query"],
            expected_title=case.get("expected_title"),
            expected_title_contains=case.get("expected_title_contains"),
        )
        for case_id, case in raw["cases"].items()
    }
    profiles = {
        profile: tuple(case_ids)
        for profile, case_ids in raw["profiles"].items()
    }
    return ProviderSeedManifest(cases=cases, profiles=profiles)


def manifest_to_json(manifest: ProviderSeedManifest) -> dict[str, Any]:
    return {
        "cases": {
            case_id: {
                "provider": case.provider.value,
                "kind": case.kind.value,
                "query": case.query,
                "expected_title": case.expected_title,
                "expected_title_contains": case.expected_title_contains,
            }
            for case_id, case in manifest.cases.items()
        },
        "profiles": {profile: list(case_ids) for profile, case_ids in manifest.profiles.items()},
    }


def results_to_json(results: list[ProviderSeedCaseResult]) -> list[dict[str, Any]]:
    return [asdict(result) for result in results]
