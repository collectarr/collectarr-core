"""Submission and moderation persistence for Catalog Item proposals."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.catalog_item_schema import validate_catalog_item_payload
from app.core.errors import ApiHTTPException
from app.models import AdminAuditLog, CatalogItemProposal
from app.models.base import ItemKind
from app.schemas.catalog_item_proposals import (
    CatalogItemProposalCreate,
    CatalogItemProposalResponse,
    CatalogItemProposalUpdate,
)
from app.services.catalog_boardgame_items import CatalogBoardGameItemService
from app.services.catalog_book_items import CatalogBookItemService
from app.services.catalog_comic_items import CatalogComicItemService
from app.services.catalog_game_items import CatalogGameItemService
from app.services.catalog_manga_items import CatalogMangaItemService
from app.services.catalog_movie_items import CatalogMovieItemService
from app.services.catalog_music_items import CatalogMusicItemService


class CatalogItemProposalService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        actor_user_id: UUID | None = None,
        actor_email: str | None = None,
    ) -> None:
        self.db = db
        self.actor_user_id = actor_user_id
        self.actor_email = actor_email

    async def submit(
        self,
        payload: CatalogItemProposalCreate,
        submitted_by_user_id: UUID | None,
    ) -> CatalogItemProposalResponse:
        item = payload.catalog_item
        title = str(item["title"]).strip()
        proposal = CatalogItemProposal(
            kind=payload.kind,
            catalog_item=item,
            title=title,
            submitted_by_user_id=submitted_by_user_id,
            status="pending",
        )
        self.db.add(proposal)
        await self.db.commit()
        await self.db.refresh(proposal)
        return CatalogItemProposalResponse.model_validate(proposal)

    async def list(
        self,
        status_filter: str = "pending",
        limit: int = 100,
    ) -> list[CatalogItemProposalResponse]:
        result = await self.db.execute(
            select(CatalogItemProposal)
            .where(CatalogItemProposal.status == status_filter)
            .order_by(CatalogItemProposal.created_at.asc())
            .limit(limit)
        )
        return [CatalogItemProposalResponse.model_validate(row) for row in result.scalars()]

    async def pending_count(self) -> int:
        return int(
            await self.db.scalar(
                select(func.count(CatalogItemProposal.id)).where(
                    CatalogItemProposal.status == "pending"
                )
            )
            or 0
        )

    async def update(
        self,
        proposal_id: UUID,
        payload: CatalogItemProposalUpdate,
    ) -> CatalogItemProposalResponse:
        proposal = await self._pending(proposal_id)
        proposal.catalog_item = validate_catalog_item_payload(
            proposal.kind,
            payload.catalog_item,
        )
        proposal.title = str(payload.catalog_item["title"]).strip()
        proposal.review_note = payload.review_note
        self._record_review("metadata_proposal.update", proposal.id)
        await self.db.commit()
        await self.db.refresh(proposal)
        return CatalogItemProposalResponse.model_validate(proposal)

    async def approve(self, proposal_id: UUID) -> CatalogItemProposalResponse:
        proposal = await self._pending(proposal_id)
        if proposal.kind is ItemKind.movie:
            await CatalogMovieItemService(self.db).create_from_proposal(
                proposal.catalog_item
            )
        elif proposal.kind is ItemKind.book:
            await CatalogBookItemService(self.db).create_from_proposal(
                proposal.catalog_item
            )
        elif proposal.kind is ItemKind.boardgame:
            await CatalogBoardGameItemService(self.db).create_from_proposal(
                proposal.catalog_item
            )
        elif proposal.kind is ItemKind.game:
            await CatalogGameItemService(self.db).create_from_proposal(
                proposal.catalog_item
            )
        elif proposal.kind is ItemKind.manga:
            await CatalogMangaItemService(self.db).create_from_proposal(
                proposal.catalog_item
            )
        elif proposal.kind is ItemKind.comic:
            await CatalogComicItemService(self.db).create_from_proposal(
                proposal.catalog_item
            )
        elif proposal.kind is ItemKind.music:
            await CatalogMusicItemService(self.db).create_from_proposal(
                proposal.catalog_item
            )
        else:
            # Keep the proposal pending until its kind has a flattened root
            # writer. Marking it approved without publishing a catalog item
            # would silently lose the user's contribution.
            raise ApiHTTPException(
                status_code=409,
                code="catalog_item_kind_not_ready_for_approval",
                detail=(
                    f"Catalog Item approval is not available for {proposal.kind.value} yet. "
                    "The proposal remains pending."
                ),
            )

        proposal.status = "approved"
        self._record_review("metadata_proposal.approve", proposal.id)
        await self.db.commit()
        await self.db.refresh(proposal)
        return CatalogItemProposalResponse.model_validate(proposal)

    async def reject(self, proposal_id: UUID) -> CatalogItemProposalResponse:
        proposal = await self._pending(proposal_id)
        proposal.status = "rejected"
        self._record_review("metadata_proposal.reject", proposal.id)
        await self.db.commit()
        await self.db.refresh(proposal)
        return CatalogItemProposalResponse.model_validate(proposal)

    async def summary(self) -> dict[str, int]:
        result = await self.db.execute(
            select(CatalogItemProposal.status, func.count(CatalogItemProposal.id)).group_by(
                CatalogItemProposal.status
            )
        )
        counts = {str(status): int(count) for status, count in result.all()}
        return {
            "pending": counts.get("pending", 0),
            "approved": counts.get("approved", 0),
            "rejected": counts.get("rejected", 0),
            "total": sum(counts.values()),
        }

    async def _pending(self, proposal_id: UUID) -> CatalogItemProposal:
        proposal = await self.db.get(CatalogItemProposal, proposal_id)
        if proposal is None:
            raise ApiHTTPException(
                status_code=404,
                code="catalog_item_proposal_not_found",
                detail="Catalog Item proposal not found",
            )
        if proposal.status != "pending":
            raise ApiHTTPException(
                status_code=400,
                code="catalog_item_proposal_not_pending",
                detail="Only pending proposals can be reviewed",
            )
        return proposal

    def _record_review(self, action: str, proposal_id: UUID) -> None:
        self.db.add(
            AdminAuditLog(
                action=action,
                actor_user_id=self.actor_user_id,
                actor_email=self.actor_email,
                entity_type="metadata_proposal",
                entity_id=proposal_id,
            )
        )
