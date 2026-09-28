from __future__ import annotations

from collections import Counter

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canonical_catalog_items import CanonicalCatalogItem
from app.schemas.admin import (
    AdminCatalogItemIntegrityResponse,
    AdminCatalogItemIntegritySample,
)
from app.schemas.catalog_item_v1 import CATALOG_ITEM_DETAILS_BY_KIND


class AdminCatalogItemIntegrityService:
    """Checks persisted Catalog Item rows against the active v1 kind schemas."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def report(
        self,
        *,
        sample_limit: int = 100,
        scan_limit: int | None = None,
    ) -> AdminCatalogItemIntegrityResponse:
        statement = select(CanonicalCatalogItem).order_by(CanonicalCatalogItem.id.asc())
        if scan_limit is not None:
            statement = statement.limit(scan_limit)

        rows = (await self.db.execute(statement)).scalars()
        scanned_items = 0
        invalid_items = 0
        issue_counts: Counter[str] = Counter()
        samples: list[AdminCatalogItemIntegritySample] = []

        for item in rows:
            scanned_items += 1
            issues = self._validate_item(item)
            if not issues:
                continue

            invalid_items += 1
            issue_counts.update(issues)
            if len(samples) < sample_limit:
                details = item.details if isinstance(item.details, dict) else {}
                samples.append(
                    AdminCatalogItemIntegritySample(
                        item_id=item.id,
                        kind=item.kind,
                        issues=issues,
                        detail_keys=sorted(str(key) for key in details),
                    )
                )

        return AdminCatalogItemIntegrityResponse(
            scan_limit=scan_limit,
            scan_limited=scan_limit is not None,
            scanned_items=scanned_items,
            invalid_items=invalid_items,
            issue_counts=dict(sorted(issue_counts.items())),
            samples=samples,
        )

    @staticmethod
    def _validate_item(item: CanonicalCatalogItem) -> list[str]:
        issues: list[str] = []
        details = item.details if isinstance(item.details, dict) else None
        details_type = CATALOG_ITEM_DETAILS_BY_KIND.get(item.kind)
        if details_type is None:
            issues.append("unknown_kind")
        elif details is None:
            issues.append("details_not_object")
        else:
            try:
                validated = details_type.model_validate(details)
            except ValidationError as error:
                issues.extend(
                    "details_invalid:" + ".".join(str(part) for part in entry["loc"])
                    for entry in error.errors()
                )
            else:
                if validated.title != item.title:
                    issues.append("root_title_mismatch")
                if validated.sort_title != item.sort_title:
                    issues.append("root_sort_title_mismatch")

        if details is not None and details.get("kind") != item.kind:
            issues.append("kind_mismatch")
        return list(dict.fromkeys(issues))
