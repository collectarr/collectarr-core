from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import and_, case, or_, select

from app.core.errors import ApiHTTPException
from app.models.base import ExternalProvider, ItemKind
from app.models import AdminReleaseMediaMappingRule, MetadataProposal
from app.schemas.admin import (
    AdminProviderPrefillResolveRequest,
    AdminProviderPrefillResolveResponse,
    AdminReleaseMediaMappingRuleCreateRequest,
    AdminReleaseMediaMappingRuleResponse,
    AdminReleaseMediaMappingRuleUpdateRequest,
    ProviderIngestHistoryEntry,
)


class AdminRulesService:
    def __init__(
        self,
        *,
        db: Any,
        ingest_history_reader: Callable[[], list[ProviderIngestHistoryEntry]],
    ) -> None:
        self.db = db
        self._ingest_history_reader = ingest_history_reader

    async def list_release_media_mapping_rules(
        self,
        provider_filter: ExternalProvider | None = None,
        active_filter: bool | None = None,
    ) -> list[AdminReleaseMediaMappingRuleResponse]:
        stmt = select(AdminReleaseMediaMappingRule)
        if provider_filter is not None:
            stmt = stmt.where(
                or_(
                    AdminReleaseMediaMappingRule.provider == provider_filter,
                    AdminReleaseMediaMappingRule.provider.is_(None),
                )
            )
        if active_filter is not None:
            stmt = stmt.where(AdminReleaseMediaMappingRule.is_active == active_filter)
        provider_priority = case(
            (AdminReleaseMediaMappingRule.provider.is_(None), 1),
            else_=0,
        )
        stmt = stmt.order_by(
            provider_priority.asc(),
            AdminReleaseMediaMappingRule.priority.asc(),
            AdminReleaseMediaMappingRule.created_at.asc(),
        )
        result = await self.db.execute(stmt)
        return [
            AdminReleaseMediaMappingRuleResponse.model_validate(row)
            for row in result.scalars().all()
        ]

    async def create_release_media_mapping_rule(
        self,
        payload: AdminReleaseMediaMappingRuleCreateRequest,
    ) -> AdminReleaseMediaMappingRuleResponse:
        release_type = _normalized_release_type(payload.release_type)
        existing = await self._matching_exact_rule(
            provider=payload.provider,
            release_type=release_type,
            target_kind=payload.target_kind,
        )
        if existing is not None:
            raise ApiHTTPException(
                status_code=status.HTTP_409_CONFLICT,
                code="admin_release_mapping_rule_exists",
                detail="Release mapping rule already exists",
            )
        rule = AdminReleaseMediaMappingRule(
            provider=payload.provider,
            release_type=release_type,
            target_kind=payload.target_kind,
            priority=payload.priority,
            is_active=payload.is_active,
            notes=_normalized_optional_text(payload.notes),
        )
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        return AdminReleaseMediaMappingRuleResponse.model_validate(rule)

    async def update_release_media_mapping_rule(
        self,
        rule_id: UUID,
        payload: AdminReleaseMediaMappingRuleUpdateRequest,
    ) -> AdminReleaseMediaMappingRuleResponse:
        rule = await self.db.get(AdminReleaseMediaMappingRule, rule_id)
        if rule is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="admin_release_mapping_rule_not_found",
                detail="Release mapping rule not found",
            )
        fields_set = payload.model_fields_set
        updated_provider = payload.provider if "provider" in fields_set else rule.provider
        updated_release_type = (
            _normalized_release_type(payload.release_type)
            if "release_type" in fields_set and payload.release_type is not None
            else rule.release_type
        )
        updated_target_kind = (
            payload.target_kind if "target_kind" in fields_set and payload.target_kind is not None else rule.target_kind
        )
        existing = await self._matching_exact_rule(
            provider=updated_provider,
            release_type=updated_release_type,
            target_kind=updated_target_kind,
            exclude_rule_id=rule.id,
        )
        if existing is not None:
            raise ApiHTTPException(
                status_code=status.HTTP_409_CONFLICT,
                code="admin_release_mapping_rule_exists",
                detail="Release mapping rule already exists",
            )
        if "provider" in fields_set:
            rule.provider = payload.provider
        if "release_type" in fields_set and payload.release_type is not None:
            rule.release_type = updated_release_type
        if "target_kind" in fields_set and payload.target_kind is not None:
            rule.target_kind = payload.target_kind
        if payload.priority is not None:
            rule.priority = payload.priority
        if payload.is_active is not None:
            rule.is_active = payload.is_active
        if "notes" in fields_set:
            rule.notes = _normalized_optional_text(payload.notes)
        await self.db.commit()
        await self.db.refresh(rule)
        return AdminReleaseMediaMappingRuleResponse.model_validate(rule)

    async def delete_release_media_mapping_rule(self, rule_id: UUID) -> bool:
        rule = await self.db.get(AdminReleaseMediaMappingRule, rule_id)
        if rule is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="admin_release_mapping_rule_not_found",
                detail="Release mapping rule not found",
            )
        await self.db.delete(rule)
        await self.db.commit()
        return True

    async def resolve_provider_prefill(
        self,
        payload: AdminProviderPrefillResolveRequest,
    ) -> AdminProviderPrefillResolveResponse:
        provider = payload.provider
        kind = payload.kind
        query = _normalized_query(payload.query)
        provider_item_id = _normalized_optional_text(payload.provider_item_id)
        release_type = (
            _normalized_release_type(payload.release_type)
            if payload.release_type is not None
            else None
        )
        notes: list[str] = []

        if payload.source == "proposal" and payload.proposal_id is not None:
            proposal = await self.db.get(MetadataProposal, payload.proposal_id)
            if proposal is None:
                raise ApiHTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="metadata_proposal_not_found",
                    detail="Proposal not found",
                )
            if provider is None:
                provider = proposal.provider
                notes.append("Provider prefilled from proposal")
            if query is None:
                query = _normalized_query(proposal.query)
                if query is not None:
                    notes.append("Query prefilled from proposal")
            if provider_item_id is None and proposal.provider_item_id:
                provider_item_id = proposal.provider_item_id
                notes.append("Provider item id prefilled from proposal")
            proposal_kind = _proposal_kind(proposal.metadata_payload)
            if kind is None and proposal_kind is not None:
                kind = proposal_kind
                notes.append("Kind prefilled from proposal payload")
            proposal_release_type = _proposal_release_type(proposal.metadata_payload)
            if release_type is None and proposal_release_type is not None:
                release_type = proposal_release_type
                notes.append("Release type inferred from proposal payload")

        if payload.source == "ingest_history" and payload.ingest_history_id is not None:
            entry = next(
                (
                    item
                    for item in self._ingest_history_reader()
                    if item.id == payload.ingest_history_id
                ),
                None,
            )
            if entry is None:
                raise ApiHTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="provider_ingest_history_not_found",
                    detail="Provider ingest history entry not found",
                )
            if provider is None:
                provider = entry.provider
                notes.append("Provider prefilled from ingest history")
            if provider_item_id is None:
                provider_item_id = entry.provider_item_id
                notes.append("Provider item id prefilled from ingest history")

        matched_rule = None
        if kind is None and release_type is not None:
            matched_rule = await self._best_rule(provider=provider, release_type=release_type)
            if matched_rule is not None:
                kind = matched_rule.target_kind
                notes.append("Kind inferred from release mapping rule")

        return AdminProviderPrefillResolveResponse(
            source=payload.source,
            provider=provider,
            kind=kind,
            query=query,
            provider_item_id=provider_item_id,
            release_type=release_type,
            matched_rule=(
                AdminReleaseMediaMappingRuleResponse.model_validate(matched_rule)
                if matched_rule is not None
                else None
            ),
            notes=notes,
        )

    async def _matching_exact_rule(
        self,
        *,
        provider: ExternalProvider | None,
        release_type: str,
        target_kind: ItemKind,
        exclude_rule_id: UUID | None = None,
    ) -> AdminReleaseMediaMappingRule | None:
        provider_clause = (
            AdminReleaseMediaMappingRule.provider.is_(None)
            if provider is None
            else AdminReleaseMediaMappingRule.provider == provider
        )
        stmt = select(AdminReleaseMediaMappingRule).where(
            and_(
                provider_clause,
                AdminReleaseMediaMappingRule.release_type == release_type,
                AdminReleaseMediaMappingRule.target_kind == target_kind,
            )
        )
        if exclude_rule_id is not None:
            stmt = stmt.where(AdminReleaseMediaMappingRule.id != exclude_rule_id)
        return await self.db.scalar(stmt)

    async def _best_rule(
        self,
        *,
        provider: ExternalProvider | None,
        release_type: str,
    ) -> AdminReleaseMediaMappingRule | None:
        stmt = select(AdminReleaseMediaMappingRule).where(
            AdminReleaseMediaMappingRule.is_active.is_(True),
            AdminReleaseMediaMappingRule.release_type == release_type,
        )
        if provider is None:
            stmt = stmt.where(AdminReleaseMediaMappingRule.provider.is_(None))
        else:
            stmt = stmt.where(
                or_(
                    AdminReleaseMediaMappingRule.provider == provider,
                    AdminReleaseMediaMappingRule.provider.is_(None),
                )
            )
        provider_priority = case(
            (AdminReleaseMediaMappingRule.provider == provider, 0),
            else_=1,
        )
        stmt = stmt.order_by(
            provider_priority.asc(),
            AdminReleaseMediaMappingRule.priority.asc(),
            AdminReleaseMediaMappingRule.created_at.asc(),
        )
        return await self.db.scalar(stmt.limit(1))


def _normalized_release_type(value: str) -> str:
    normalized = " ".join(value.split()).strip().lower()
    if not normalized:
        raise ApiHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="admin_release_mapping_invalid_release_type",
            detail="Release type cannot be empty",
        )
    return normalized


def _normalized_query(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def _normalized_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def _proposal_kind(metadata_payload: dict | None) -> ItemKind | None:
    if not isinstance(metadata_payload, dict):
        return None
    raw_kind = metadata_payload.get("kind")
    if isinstance(raw_kind, str):
        try:
            return ItemKind(raw_kind)
        except ValueError:
            return None
    normalized = metadata_payload.get("normalized")
    if isinstance(normalized, dict):
        nested_kind = normalized.get("kind")
        if isinstance(nested_kind, str):
            try:
                return ItemKind(nested_kind)
            except ValueError:
                return None
    return None


def _proposal_release_type(metadata_payload: dict | None) -> str | None:
    if not isinstance(metadata_payload, dict):
        return None
    for key in ("release_type", "candidate_type"):
        raw = metadata_payload.get(key)
        if isinstance(raw, str):
            normalized = _normalized_query(raw)
            if normalized is not None:
                return normalized.lower()
    normalized = metadata_payload.get("normalized")
    if isinstance(normalized, dict):
        raw = normalized.get("release_type") or normalized.get("candidate_type")
        if isinstance(raw, str):
            normalized_value = _normalized_query(raw)
            if normalized_value is not None:
                return normalized_value.lower()
    return None
