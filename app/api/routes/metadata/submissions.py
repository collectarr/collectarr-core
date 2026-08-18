"""Normalized metadata submission route.

Accepts NormalizedProviderEnvelopeV1 submissions.
- Editors and Admins: Executes immediate canonical write via CanonicalCatalogWriter.
- Standard users: Creates a MetadataProposal for editorial review.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import DbSession
from app.core.errors import ApiHTTPException
from app.core.security import decode_access_token
from app.models.base import ExternalProvider, ItemKind, UserRole
from app.models.canonical_support import MetadataProposal
from app.models.user import User
from app.providers.envelope import (
    NormalizedProviderEnvelopeV1,
    ProviderAttribution,
    ProviderImageRef,
    ProviderProvenance,
)
from app.repositories.users import UserRepository
from app.schemas.metadata_submissions import (
    MetadataSubmissionRequest,
    MetadataSubmissionResponse,
)
from app.services.canonical_catalog_writer import CanonicalCatalogWriter

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)

router = APIRouter(tags=["metadata"])


async def get_submission_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> User | None:
    """Resolve current user if a valid bearer token is present, else None."""
    if credentials is None:
        return None
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        return None
    user = await UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        return None
    return user


@router.post(
    "/metadata/submissions",
    response_model=MetadataSubmissionResponse,
    status_code=status.HTTP_200_OK,
)
async def submit_normalized_metadata(
    payload: MetadataSubmissionRequest,
    db: DbSession,
    user: Annotated[User | None, Depends(get_submission_user)],
) -> MetadataSubmissionResponse:
    """Submit a normalized provider envelope for ingestion or proposal review."""
    # 1. Validate schema version
    if payload.schema_version != "v1":
        raise ApiHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_schema_version",
            detail=f"Unsupported schema version: '{payload.schema_version}'. Expected 'v1'.",
        )

    # 2. Validate kind
    valid_kinds = {k.value for k in ItemKind}
    if payload.kind not in valid_kinds:
        raise ApiHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_kind",
            detail=f"Unknown kind '{payload.kind}'. Valid kinds are: {sorted(valid_kinds)}.",
        )

    # 3. Validate provider
    if not payload.provider.strip():
        raise ApiHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_provider",
            detail="Provider cannot be empty.",
        )

    # 4. Validate payload normalized dictionary
    title = str(payload.normalized.get("title") or "").strip()
    if not title:
        raise ApiHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="missing_title",
            detail="Normalized payload must contain a non-empty 'title'.",
        )

    # Construct NormalizedProviderEnvelopeV1
    provenance = ProviderProvenance.from_dict(payload.provenance if payload.provenance else {"fetched_at": ""})
    images = [ProviderImageRef.from_dict(img) for img in payload.images]
    attribution = ProviderAttribution.from_dict(payload.attribution if payload.attribution else {})

    envelope = NormalizedProviderEnvelopeV1(
        schema_version=payload.schema_version,
        provider=payload.provider,
        provider_item_id=payload.provider_item_id,
        kind=payload.kind,
        normalized=payload.normalized,
        provenance=provenance,
        images=images,
        attribution=attribution,
    )

    # 5. Permission / Policy routing:
    is_editor_or_admin = (
        user is not None
        and (user.role in {UserRole.editor, UserRole.admin} or user.is_admin)
    )

    if is_editor_or_admin:
        # Canonical write
        writer = CanonicalCatalogWriter(db)
        result = await writer.write_envelope(envelope)
        return MetadataSubmissionResponse(
            status="canonical_write",
            item_id=result.item_id,
            kind=result.kind,
            created=result.created,
            item=result.item,
            message="Canonical catalog write completed.",
        )
    else:
        # User proposal policy
        p_enum = (
            ExternalProvider(payload.provider)
            if payload.provider in ExternalProvider._value2member_map_
            else ExternalProvider.custom if hasattr(ExternalProvider, "custom") else ExternalProvider.gcd
        )
        proposal = MetadataProposal(
            provider=p_enum,
            provider_item_id=payload.provider_item_id,
            query=title,
            title=title,
            summary=payload.normalized.get("synopsis") or payload.normalized.get("description"),
            image_url=payload.normalized.get("cover_image_url"),
            metadata_payload=envelope.to_dict(),
            status="pending",
        )
        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)

        return MetadataSubmissionResponse(
            submission_id=proposal.id,
            status="proposal_created",
            kind=payload.kind,
            created=True,
            message="Metadata submission recorded as proposal for editorial review.",
        )
