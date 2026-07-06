from __future__ import annotations

from app.schemas import MetadataProposalCreate, MetadataProposalResponse


class ProposalsService:
    async def create_proposal(self, payload: MetadataProposalCreate) -> MetadataProposalResponse:
        from app.services.metadata.metadata_public import create_proposal as _create_proposal

        return await _create_proposal(self, payload)
