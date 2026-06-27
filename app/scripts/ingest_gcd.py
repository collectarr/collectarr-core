from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.base import ExternalProvider
from app.models.canonical import ExternalProviderId
from app.providers.gcd import GCDProvider
from app.schemas.admin import ProviderIngestRequest
from app.services.admin import AdminMetadataService

DEFAULT_SEARCH_LIMIT = 20


@dataclass(frozen=True)
class GCDIngestCandidate:
    provider_item_id: str
    title: str | None = None
    summary: str | None = None
    query: str | None = None


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


def issue_queries(
    series: str | None,
    issue: str | None,
    from_issue: int | None,
    to_issue: int | None,
) -> list[str]:
    if series is None:
        return []
    if issue is not None:
        return [f"{series} #{issue}"]
    if from_issue is None or to_issue is None:
        return []
    return [f"{series} #{issue_number}" for issue_number in range(from_issue, to_issue + 1)]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search and ingest GCD comic issues into the Collectarr metadata database."
    )
    parser.add_argument(
        "--provider-item-id",
        dest="provider_item_ids",
        action="append",
        default=[],
        type=non_empty_text,
        help="GCD issue id to ingest. Can be provided multiple times.",
    )
    parser.add_argument("--series", type=non_empty_text, help="Series title for GCD search.")
    parser.add_argument("--issue", type=non_empty_text, help="Single issue number to search.")
    parser.add_argument(
        "--from-issue",
        type=positive_int,
        help="First issue number for a numeric search range.",
    )
    parser.add_argument(
        "--to-issue",
        type=positive_int,
        help="Last issue number for a numeric search range.",
    )
    parser.add_argument(
        "--limit",
        default=DEFAULT_SEARCH_LIMIT,
        type=positive_int,
        help="Maximum search results to ingest per issue query.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip provider ids that are already linked to catalog items.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve candidates and print what would be ingested without writing data.",
    )
    args = parser.parse_args(argv)
    validate_args(parser, args)
    return args


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    has_ids = bool(args.provider_item_ids)
    has_search_fields = any(
        value is not None for value in (args.series, args.issue, args.from_issue, args.to_issue)
    )
    if not has_ids and not has_search_fields:
        parser.error("provide --provider-item-id or --series with --issue/--from-issue/--to-issue")
    if has_search_fields and args.series is None:
        parser.error("--series is required when using issue search arguments")
    if args.series is None:
        return
    has_single_issue = args.issue is not None
    has_range_start = args.from_issue is not None
    has_range_end = args.to_issue is not None
    if has_single_issue and (has_range_start or has_range_end):
        parser.error("use either --issue or --from-issue/--to-issue, not both")
    if not has_single_issue and not (has_range_start and has_range_end):
        parser.error("--series requires --issue or both --from-issue and --to-issue")
    if has_range_start != has_range_end:
        parser.error("--from-issue and --to-issue must be provided together")
    if has_range_start and args.from_issue > args.to_issue:
        parser.error("--from-issue must be less than or equal to --to-issue")


async def collect_candidates(
    args: argparse.Namespace,
    provider: GCDProvider,
    write: Callable[[str], None],
) -> list[GCDIngestCandidate]:
    candidates = [
        GCDIngestCandidate(provider_item_id=provider_item_id)
        for provider_item_id in args.provider_item_ids
    ]
    for query in issue_queries(args.series, args.issue, args.from_issue, args.to_issue):
        results = await provider.search(query)
        if not results:
            write(f"NO RESULTS {query}")
            continue
        for result in results[: args.limit]:
            candidates.append(
                GCDIngestCandidate(
                    provider_item_id=result.provider_item_id,
                    title=result.title,
                    summary=result.summary,
                    query=query,
                )
            )
    return dedupe_candidates(candidates)


def dedupe_candidates(candidates: list[GCDIngestCandidate]) -> list[GCDIngestCandidate]:
    deduped: list[GCDIngestCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        provider_item_id = candidate.provider_item_id.strip()
        if not provider_item_id or provider_item_id in seen:
            continue
        seen.add(provider_item_id)
        deduped.append(
            GCDIngestCandidate(
                provider_item_id=provider_item_id,
                title=candidate.title,
                summary=candidate.summary,
                query=candidate.query,
            )
        )
    return deduped


async def provider_item_exists(db: AsyncSession, provider_item_id: str) -> bool:
    existing_id = await db.scalar(
        select(ExternalProviderId.id).where(
            ExternalProviderId.provider == ExternalProvider.gcd,
            ExternalProviderId.provider_item_id == provider_item_id,
            ExternalProviderId.entity_type == "comic_issue",
        )
    )
    return existing_id is not None


async def run_ingest(
    args: argparse.Namespace,
    write: Callable[[str], None] = print,
) -> int:
    provider = GCDProvider()
    original_search_limit = provider.settings.gcd_search_limit
    provider.settings.gcd_search_limit = max(original_search_limit, args.limit)
    try:
        candidates = await collect_candidates(args, provider, write)
    finally:
        provider.settings.gcd_search_limit = original_search_limit
    if not candidates:
        write("No GCD candidates found.")
        return 1
    if args.dry_run:
        for candidate in candidates:
            write(f"DRY-RUN {format_candidate(candidate)}")
        return 0

    async with AsyncSessionLocal() as db:
        service = AdminMetadataService(db)
        for candidate in candidates:
            label = format_candidate(candidate)
            if args.skip_existing and await provider_item_exists(db, candidate.provider_item_id):
                write(f"SKIPPED {label} already linked")
                continue
            response = await service.ingest(
                ProviderIngestRequest(
                    provider=ExternalProvider.gcd,
                    provider_item_id=candidate.provider_item_id,
                )
            )
            status = "INGESTED" if response.created else "EXISTS"
            write(f"{status} {label} item_id={response.item_id}")
    return 0


def format_candidate(candidate: GCDIngestCandidate) -> str:
    parts = [f"gcd:{candidate.provider_item_id}"]
    if candidate.title:
        parts.append(candidate.title)
    if candidate.summary:
        parts.append(f"({candidate.summary})")
    if candidate.query:
        parts.append(f"query={candidate.query!r}")
    return " ".join(parts)


def main(argv: Sequence[str] | None = None) -> int:
    return asyncio.run(run_ingest(parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
