from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAdmin, DbSession
from app.catalog.release_scope import ReleasedCatalogKind
from app.schemas.canonical_corrections import (
    CanonicalCorrectionApprovalResponse,
    CanonicalCorrectionProposalCreate,
    CanonicalCorrectionProposalResponse,
    CanonicalCorrectionTargetResponse,
)
from app.services.canonical_correction_targets import CanonicalCorrectionTargetService
from app.services.canonical_corrections import CanonicalCorrectionService

router = APIRouter(tags=["metadata"])


@router.get(
    "/metadata/correction-targets/{kind}/{entity_id}",
    response_model=CanonicalCorrectionTargetResponse,
)
async def get_canonical_correction_target(
    kind: ReleasedCatalogKind,
    entity_id: UUID,
    scope: str,
    db: DbSession,
) -> CanonicalCorrectionTargetResponse:
    entity_type = CanonicalCorrectionTargetService.entity_type_for_scope(kind, scope)
    return await CanonicalCorrectionTargetService(db).snapshot(
        kind=kind,
        entity_type=entity_type,
        entity_id=entity_id,
        scope=scope,
    )


@router.post(
    "/metadata/correction-proposals",
    response_model=CanonicalCorrectionProposalResponse,
    status_code=201,
)
async def create_canonical_correction_proposal(
    payload: CanonicalCorrectionProposalCreate,
    db: DbSession,
) -> CanonicalCorrectionProposalResponse:
    return await CanonicalCorrectionService(db).create(payload)


@router.post(
    "/metadata/correction-proposals/{proposal_id}/approve",
    response_model=CanonicalCorrectionApprovalResponse,
)
async def approve_canonical_correction_proposal(
    proposal_id: UUID,
    db: DbSession,
    admin: CurrentAdmin,
) -> CanonicalCorrectionApprovalResponse:
    return await CanonicalCorrectionService(db).approve(proposal_id, actor=admin)


@router.get(
    "/metadata/correction-proposals",
    response_model=list[CanonicalCorrectionProposalResponse],
)
async def list_canonical_correction_proposals(
    db: DbSession,
    admin: CurrentAdmin,
    status: Literal["pending", "approved", "rejected"] | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[CanonicalCorrectionProposalResponse]:
    return await CanonicalCorrectionService(db).list_proposals(status_filter=status, limit=limit)


@router.post(
    "/metadata/correction-proposals/{proposal_id}/reject",
    response_model=CanonicalCorrectionProposalResponse,
)
async def reject_canonical_correction_proposal(
    proposal_id: UUID,
    db: DbSession,
    admin: CurrentAdmin,
) -> CanonicalCorrectionProposalResponse:
    return await CanonicalCorrectionService(db).reject(proposal_id, actor=admin)
