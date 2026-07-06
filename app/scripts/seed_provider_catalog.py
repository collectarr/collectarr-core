from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from pathlib import Path

from app.db.session import AsyncSessionLocal
from app.models.base import ExternalProvider, ItemKind
from app.services.provider_seed_service import (
    ProviderSeedOptions,
    ProviderSeedService,
    results_to_json,
)


def non_empty_text(value: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise argparse.ArgumentTypeError("must not be empty")
    return normalized


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def csv_providers(value: str) -> set[ExternalProvider]:
    providers: set[ExternalProvider] = set()
    for raw in value.split(","):
        normalized = raw.strip()
        if not normalized:
            continue
        providers.add(ExternalProvider(normalized))
    if not providers:
        raise argparse.ArgumentTypeError("must contain at least one provider")
    return providers


def csv_kinds(value: str) -> set[ItemKind]:
    kinds: set[ItemKind] = set()
    for raw in value.split(","):
        normalized = raw.strip()
        if not normalized:
            continue
        kinds.add(ItemKind(normalized))
    if not kinds:
        raise argparse.ArgumentTypeError("must contain at least one kind")
    return kinds


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    service = ProviderSeedService()
    parser = argparse.ArgumentParser(
        description="Seed the catalog through provider search and ingest flows."
    )
    parser.add_argument(
        "--profile",
        choices=service.manifest.profile_names(),
        default="smoke",
        help="Seed profile to run from the manifest.",
    )
    parser.add_argument(
        "--providers",
        type=csv_providers,
        help="Comma-separated provider filter, e.g. tmdb,comicvine,gcd.",
    )
    parser.add_argument(
        "--kinds",
        type=csv_kinds,
        help="Comma-separated kind filter, e.g. movie,tv,comic,book.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve candidates without writing anything.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip provider ids already linked to catalog rows.",
    )
    parser.add_argument(
        "--limit-per-kind",
        type=positive_int,
        help="Limit the number of manifest cases run per kind.",
    )
    parser.add_argument(
        "--run-jobs",
        action="store_true",
        help="Queue provider ingest jobs and execute them instead of calling ingest directly.",
    )
    parser.add_argument(
        "--require-configured",
        action="store_true",
        help="Fail instead of skipping unconfigured providers.",
    )
    parser.add_argument(
        "--report",
        type=non_empty_text,
        help="Write a JSON report to this path.",
    )
    return parser.parse_args(argv)


async def run(args: argparse.Namespace) -> int:
    service = ProviderSeedService()
    cases = service.cases_for_profile(args.profile)
    cases = service.filter_cases(
        cases,
        providers=args.providers,
        kinds=args.kinds,
        limit_per_kind=args.limit_per_kind,
    )
    if not cases:
        raise RuntimeError("No provider seed cases matched the requested filters")

    options = ProviderSeedOptions(
        dry_run=args.dry_run,
        skip_existing=args.skip_existing,
        run_jobs=args.run_jobs,
        require_configured=args.require_configured,
    )

    async with AsyncSessionLocal() as db:
        service = ProviderSeedService(db)
        results = await service.run(cases, profile=args.profile, options=options)

    report = {
        "profile": args.profile,
        "options": {
            "dry_run": args.dry_run,
            "skip_existing": args.skip_existing,
            "run_jobs": args.run_jobs,
            "require_configured": args.require_configured,
            "limit_per_kind": args.limit_per_kind,
            "providers": sorted(p.value for p in args.providers) if args.providers else None,
            "kinds": sorted(k.value for k in args.kinds) if args.kinds else None,
        },
        "summary": {
            "total": len(results),
            "pass": sum(1 for result in results if result.status == "pass"),
            "skip": sum(1 for result in results if result.status == "skip"),
            "fail": sum(1 for result in results if result.status == "fail"),
            "dry_run": sum(1 for result in results if result.status == "dry-run"),
        },
        "results": results_to_json(results),
    }

    print(json.dumps(report, indent=2, ensure_ascii=True))

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")

    return 0 if report["summary"]["fail"] == 0 else 1


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
