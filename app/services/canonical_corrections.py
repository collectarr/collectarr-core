from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalog.metadata_fields import canonical_correction_target
from app.core.errors import ApiHTTPException
from app.models import (
    AdminAuditLog,
    AdminAuditLogDetail,
    CanonicalCorrectionProposal,
    CanonicalCorrectionProposalValue,
)
from app.models.user import User
from app.schemas.canonical_corrections import (
    CanonicalCorrectionApprovalResponse,
    CanonicalCorrectionProposalCreate,
    CanonicalCorrectionProposalResponse,
)
from app.services.canonical_correction_targets import CanonicalCorrectionTargetService
from app.services.typed_values import flatten_typed_values, materialize_typed_values


class CanonicalCorrectionService:
    """Create, compare, and approve exact canonical correction proposals."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.targets = CanonicalCorrectionTargetService(db)

    async def create(self, payload: CanonicalCorrectionProposalCreate) -> CanonicalCorrectionProposalResponse:
        self._validate_target(payload)
        current, diff = await self.targets.current_and_diff(
            kind=payload.kind,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            scope=payload.scope,
            proposed_fields=payload.proposed_fields,
        )
        self._validate_baseline(payload.base_revision, payload.base_hash, current.revision, current.hash)

        changed_fields = {key: row["after"] for key, row in diff.items()}
        proposal = CanonicalCorrectionProposal(
            kind=payload.kind,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            scope=payload.scope,
            base_revision=current.revision,
            base_hash=current.hash,
            status="pending",
        )
        self.db.add(proposal)
        await self.db.flush()
        self.db.add_all(
            CanonicalCorrectionProposalValue(proposal_id=proposal.id, **row)
            for row in flatten_typed_values(changed_fields)
        )
        await self.db.commit()
        await self.db.refresh(proposal, attribute_names=["values"])
        return self._proposal_response(proposal, current.fields, diff, current.revision, current.hash)

    async def approve(self, proposal_id: UUID, *, actor: User) -> CanonicalCorrectionApprovalResponse:
        # Approval is an optimistic-concurrency transition. Lock the proposal
        # before reading its values so two admins cannot approve the same
        # pending proposal concurrently, and avoid an async lazy-load of the
        # typed value rows.
        proposal = (
            await self.db.execute(
                select(CanonicalCorrectionProposal)
                .options(selectinload(CanonicalCorrectionProposal.values))
                .where(CanonicalCorrectionProposal.id == proposal_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if proposal is None:
            raise ApiHTTPException(status_code=404, code="canonical_correction_not_found", detail=f"Correction proposal {proposal_id} was not found.")
        if proposal.status != "pending":
            raise ApiHTTPException(status_code=status.HTTP_409_CONFLICT, code="canonical_correction_not_pending", detail=f"Correction proposal is already {proposal.status}.")

        proposed = materialize_typed_values(proposal.values)
        if not isinstance(proposed, dict) or not proposed:
            raise ApiHTTPException(status_code=422, code="canonical_correction_empty", detail="Correction proposal has no canonical fields.")
        current, diff = await self.targets.current_and_diff(
            kind=proposal.kind,
            entity_type=proposal.entity_type,
            entity_id=proposal.entity_id,
            scope=proposal.scope,
            proposed_fields=proposed,
            lock=True,
        )
        self._validate_baseline(proposal.base_revision, proposal.base_hash, current.revision, current.hash)
        updated = await self.targets.apply(
            kind=proposal.kind,
            entity_type=proposal.entity_type,
            entity_id=proposal.entity_id,
            scope=proposal.scope,
            fields={key: row["after"] for key, row in diff.items()},
        )
        proposal.status = "approved"
        audit = AdminAuditLog(
            action="canonical_correction_approved",
            actor_user_id=actor.id,
            actor_email=actor.email,
            entity_type=proposal.entity_type,
            entity_id=proposal.entity_id,
        )
        audit.details = [
            AdminAuditLogDetail(**row)
            for row in flatten_typed_values(
                {
                    "proposal_id": str(proposal.id),
                    "scope": proposal.scope,
                    "base_hash": proposal.base_hash,
                    "approved_hash": updated.hash,
                    "diff": diff,
                }
            )
        ]
        self.db.add(audit)
        await self.db.commit()
        await self.db.refresh(proposal, attribute_names=["values"])
        response = self._proposal_response(proposal, updated.fields, diff, updated.revision, updated.hash)
        return CanonicalCorrectionApprovalResponse(
            **response.model_dump(),
            approved_by=actor.id,
        )

    @staticmethod
    def _proposal_response(
        proposal: CanonicalCorrectionProposal,
        current_fields: dict[str, Any],
        diff: dict[str, Any],
        current_revision: str,
        current_hash: str,
    ) -> CanonicalCorrectionProposalResponse:
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
            current_fields=current_fields,
            diff=diff,
            current_revision=current_revision,
            current_hash=current_hash,
        )

    @staticmethod
    def _validate_baseline(base_revision: str | None, base_hash: str | None, current_revision: str, current_hash: str) -> None:
        if base_revision is not None and base_revision != current_revision:
            raise ApiHTTPException(status_code=status.HTTP_409_CONFLICT, code="stale_canonical_correction", detail="The canonical target revision is stale.")
        if base_hash is not None and base_hash != current_hash:
            raise ApiHTTPException(status_code=status.HTTP_409_CONFLICT, code="stale_canonical_correction", detail="The canonical target hash is stale.")

    @staticmethod
    def _validate_target(payload: CanonicalCorrectionProposalCreate) -> None:
        target = canonical_correction_target(payload.kind, payload.proposed_fields)
        if target is None:
            raise ApiHTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="invalid_canonical_correction_target",
                detail="proposed_fields must contain only canonical fields from one kind/scope/entity target",
            )
        expected_scope, expected_entity_type = target
        if payload.scope != expected_scope:
            raise ApiHTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, code="canonical_correction_scope_mismatch", detail=f"scope '{payload.scope}' does not match canonical field scope '{expected_scope}'")
        if payload.entity_type != expected_entity_type:
            raise ApiHTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, code="canonical_correction_entity_type_mismatch", detail=f"entity_type '{payload.entity_type}' does not match canonical field entity type '{expected_entity_type}'")
