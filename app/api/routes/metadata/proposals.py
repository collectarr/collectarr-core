"""Source-neutral submission of Add/Edit Catalog Item data for review."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import DbSession
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.catalog_item_proposals import (
    CatalogItemProposalCreate,
    CatalogItemProposalResponse,
)
from app.services.catalog_item_proposals import CatalogItemProposalService

router = APIRouter(tags=["metadata"])
bearer_scheme = HTTPBearer(auto_error=False)


async def _optional_submitter(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> User | None:
    if credentials is None:
        return None
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        return None
    user = await UserRepository(db).get_by_id(user_id)
    return user if user is not None and user.is_active else None


@router.post(
    "/metadata/proposals",
    response_model=CatalogItemProposalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_catalog_item_proposal(
    payload: CatalogItemProposalCreate,
    db: DbSession,
    submitter: Annotated[User | None, Depends(_optional_submitter)],
) -> CatalogItemProposalResponse:
    return await CatalogItemProposalService(db).submit(
        payload,
        submitted_by_user_id=submitter.id if submitter is not None else None,
    )
