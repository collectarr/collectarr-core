from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.canonical_corrections import (
    CanonicalCorrectionProposalCreate,
    CanonicalCorrectionProposalResponse,
)
from app.services.canonical_corrections import CanonicalCorrectionService

router = APIRouter(tags=["metadata"])


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
