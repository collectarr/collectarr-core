"""Administrative workflow for reviewing normalized metadata proposals."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from fastapi import status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ApiHTTPException
from app.models import MetadataProposal, MetadataProposalValue
from app.models.base import ExternalProvider
from app.providers.envelope import (
    NormalizedProviderEnvelopeV1,
    ProviderAttribution,
    ProviderProvenance,
)
from app.schemas.admin import (
    CanonicalCatalogWriteResponse,
    MetadataProposalAdminResponse,
    MetadataProposalAdminUpdateRequest,
    MetadataProposalSummaryResponse,
)
from app.services.canonical_catalog_writer import CanonicalCatalogWriter
from app.services.typed_values import flatten_typed_values, materialize_typed_values
from app.types import JsonObject


class AdminProposalService:
    """Owns proposal review; provider adapters stay outside Core."""

    def __init__(
        self,
        *,
        db: AsyncSession,
        audit_recorder: Callable[..., None],
    ) -> None:
        self.db = db
        self._audit_recorder = audit_recorder

    async def summary(self) -> MetadataProposalSummaryResponse:
        result = await self.db.execute(
            select(MetadataProposal.status, func.count(MetadataProposal.id)).group_by(
                MetadataProposal.status
            )
        )
        counts = {str(status): int(count) for status, count in result.all()}
        pending = counts.get("pending", 0)
        approved = counts.get("approved", 0)
        rejected = counts.get("rejected", 0)
        return MetadataProposalSummaryResponse(
            pending=pending,
            approved=approved,
            rejected=rejected,
            total=pending + approved + rejected,
        )

    async def list(
        self,
        status_filter: str = "pending",
        provider_filter: ExternalProvider | None = None,
    ) -> list[MetadataProposalAdminResponse]:
        stmt = (
            select(MetadataProposal)
            .options(selectinload(MetadataProposal.values))
            .where(MetadataProposal.status == status_filter)
            .order_by(MetadataProposal.created_at.asc())
        )
        if provider_filter:
            stmt = stmt.where(MetadataProposal.provider == provider_filter)
        result = await self.db.execute(stmt)
        return [self._response(proposal) for proposal in result.scalars()]

    async def update(
        self,
        proposal_id: UUID,
        payload: MetadataProposalAdminUpdateRequest,
    ) -> MetadataProposalAdminResponse:
        proposal = await self._get_pending(proposal_id)
        changed_fields: list[str] = []

        def trimmed(value: str | None) -> str | None:
            if value is None:
                return None
            normalized = value.strip()
            return normalized or None

        for field_name in ("query", "title", "summary", "image_url"):
            value = getattr(payload, field_name)
            if value is None:
                continue
            normalized = trimmed(value)
            if normalized != getattr(proposal, field_name):
                setattr(proposal, field_name, normalized)
                changed_fields.append(field_name)

        if payload.provider_item_id is not None:
            provider_item_id = trimmed(payload.provider_item_id)
            if provider_item_id != proposal.provider_item_id:
                proposal.provider_item_id = provider_item_id
                changed_fields.append("provider_item_id")

        if payload.metadata_payload is not None:
            from app.proposal_payload import validate_metadata_payload

            validate_metadata_payload(payload.metadata_payload)
            await self.db.execute(
                delete(MetadataProposalValue).where(
                    MetadataProposalValue.proposal_id == proposal.id
                )
            )
            self.db.add_all(
                MetadataProposalValue(proposal_id=proposal.id, **row)
                for row in flatten_typed_values(payload.metadata_payload)
            )
            changed_fields.append("metadata_payload")

        if changed_fields:
            self._audit_recorder(
                action="metadata_proposal.update",
                entity_type="metadata_proposal",
                entity_id=proposal.id,
                details={"changed_fields": changed_fields},
            )
            await self.db.commit()

        await self.db.refresh(proposal, attribute_names=["values"])
        return self._response(proposal)

    async def approve(self, proposal_id: UUID) -> CanonicalCatalogWriteResponse:
        proposal = await self._get_pending(proposal_id)
        await self.db.refresh(proposal, attribute_names=["values"])
        payload = materialize_typed_values(proposal.values)
        if not isinstance(payload, dict):
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="metadata_proposal_payload_invalid",
                detail="Proposal payload must be an object",
            )

        envelope = self._envelope_for_proposal(proposal, cast(JsonObject, payload))
        result = await CanonicalCatalogWriter(self.db).write_envelope(envelope)
        proposal.status = "approved"
        self._audit_recorder(
            action="metadata_proposal.approve",
            entity_type="metadata_proposal",
            entity_id=proposal.id,
            details={
                "provider": proposal.provider,
                "provider_item_id": proposal.provider_item_id,
                "item_id": result.item_id,
                "created": result.created,
            },
        )
        await self.db.commit()
        return CanonicalCatalogWriteResponse(
            item_id=result.item_id,
            kind=result.kind,
            created=result.created,
            item=result.item,
        )

    async def reject(self, proposal_id: UUID) -> MetadataProposalAdminResponse:
        proposal = await self._get_pending(proposal_id)
        proposal.status = "rejected"
        self._audit_recorder(
            action="metadata_proposal.reject",
            entity_type="metadata_proposal",
            entity_id=proposal.id,
            details={"provider": proposal.provider, "query": proposal.query},
        )
        await self.db.commit()
        await self.db.refresh(proposal, attribute_names=["values"])
        return self._response(proposal)

    async def _get_pending(self, proposal_id: UUID) -> MetadataProposal:
        proposal = await self.db.get(MetadataProposal, proposal_id)
        if proposal is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="metadata_proposal_not_found",
                detail="Proposal not found",
            )
        if proposal.status != "pending":
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="metadata_proposal_not_pending",
                detail="Only pending proposals can be reviewed",
            )
        return proposal

    def _response(self, proposal: MetadataProposal) -> MetadataProposalAdminResponse:
        response = MetadataProposalAdminResponse.model_validate(proposal)
        return response.model_copy(
            update={"metadata_payload": materialize_typed_values(proposal.values)}
        )

    def _envelope_for_proposal(
        self,
        proposal: MetadataProposal,
        payload: JsonObject,
    ) -> NormalizedProviderEnvelopeV1:
        if payload.get("schema_version") == "v1" and isinstance(payload.get("normalized"), dict):
            return NormalizedProviderEnvelopeV1.from_dict(payload)

        kind = payload.get("kind")
        normalized = payload.get("normalized")
        if not isinstance(kind, str) or not isinstance(normalized, dict):
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="metadata_proposal_missing_envelope",
                detail="Proposal must contain a v1 normalized provider envelope",
            )
        return NormalizedProviderEnvelopeV1(
            schema_version="v1",
            provider=proposal.provider.value,
            provider_item_id=proposal.provider_item_id or str(proposal.id),
            kind=kind,
            normalized=normalized,
            provenance=ProviderProvenance(
                fetched_at=datetime.now(UTC).isoformat().replace("+00:00", "Z")
            ),
            images=[],
            attribution=ProviderAttribution(required=False),
        )
