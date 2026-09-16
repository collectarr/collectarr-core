from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas import (
    MetadataProposalCreate,
    MetadataProposalResponse,
)
from app.services.facade import MetadataFacade as MetadataService

router = APIRouter(tags=["metadata"])


@router.post("/metadata/proposals", response_model=MetadataProposalResponse, status_code=201)
async def create_metadata_proposal(
    payload: MetadataProposalCreate,
    db: DbSession,
) -> MetadataProposalResponse:
    return await MetadataService(db).create_proposal(payload)
