from __future__ import annotations

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.metadata_fields import canonical_correction_target
from app.core.errors import ApiHTTPException
from app.models import CanonicalCorrectionProposal, CanonicalCorrectionProposalValue
from app.schemas.canonical_corrections import (
    CanonicalCorrectionProposalCreate,
    CanonicalCorrectionProposalResponse,
)
from app.services.typed_values import flatten_typed_values, materialize_typed_values


class CanonicalCorrectionService:
    """Store validated canonical corrections without resolving their target."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        payload: CanonicalCorrectionProposalCreate,
    ) -> CanonicalCorrectionProposalResponse:
        self._validate_target(payload)

        proposal = CanonicalCorrectionProposal(
            kind=payload.kind,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            scope=payload.scope,
            base_revision=payload.base_revision,
            base_hash=payload.base_hash,
            status="pending",
        )
        self.db.add(proposal)
        await self.db.flush()
        self.db.add_all(
            CanonicalCorrectionProposalValue(proposal_id=proposal.id, **row)
            for row in flatten_typed_values(payload.proposed_fields)
        )
        await self.db.commit()
        await self.db.refresh(proposal, attribute_names=["values"])
        return CanonicalCorrectionProposalResponse(
            id=proposal.id,
            kind=proposal.kind,
            entity_type=proposal.entity_type,
            entity_id=proposal.entity_id,
            scope=proposal.scope,
            base_revision=proposal.base_revision,
            base_hash=proposal.base_hash,
            proposed_fields=materialize_typed_values(proposal.values),
            status=proposal.status,
        )

    @staticmethod
    def _validate_target(payload: CanonicalCorrectionProposalCreate) -> None:
        target = canonical_correction_target(payload.kind, payload.proposed_fields)
        if target is None:
            raise ApiHTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="invalid_canonical_correction_target",
                detail=(
                    "proposed_fields must contain only canonical fields from one "
                    "kind/scope/entity target"
                ),
            )
        expected_scope, expected_entity_type = target
        if payload.scope != expected_scope:
            raise ApiHTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="canonical_correction_scope_mismatch",
                detail=(
                    f"scope '{payload.scope}' does not match canonical field scope "
                    f"'{expected_scope}'"
                ),
            )
        if payload.entity_type != expected_entity_type:
            raise ApiHTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="canonical_correction_entity_type_mismatch",
                detail=(
                    f"entity_type '{payload.entity_type}' does not match canonical "
                    f"field entity type '{expected_entity_type}'"
                ),
            )
