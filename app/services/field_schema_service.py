from __future__ import annotations

from uuid import UUID

from fastapi import status
from sqlalchemy import func, or_, select

from app.core.errors import ApiHTTPException
from app.models import Character, CharacterAppearance, EntityPerson, Person, StoryArc, StoryArcItem
from app.schemas import (
    CharacterAppearanceResponse,
    CharacterFacetResponse,
    CharacterResponse,
    CreatorCreditResponse,
    CreatorFacetResponse,
    CreatorResponse,
    StoryArcFacetResponse,
    StoryArcItemResponse,
    StoryArcResponse,
)
from app.schemas.metadata_shared import public_item_kind
from app.services.entity_resolution import load_entity_summaries
from app.services.metadata_helpers import _model_text_or_metadata


class FieldSchemaService:
    async def search_story_arcs(
        self,
        *,
        q: str | None = None,
        limit: int = 25,
    ) -> list[StoryArcResponse]:
        count_expr = func.count(StoryArcItem.id)
        stmt = (
            select(StoryArc, count_expr.label("item_count"))
            .outerjoin(StoryArcItem, StoryArcItem.story_arc_id == StoryArc.id)
            .group_by(StoryArc.id)
            .order_by(count_expr.desc(), StoryArc.name.asc())
            .limit(limit)
        )
        if q:
            pattern = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(
                    StoryArc.name.ilike(pattern),
                    StoryArc.description.ilike(pattern),
                    StoryArc.publisher.ilike(pattern),
                )
            )
        rows = (await self.db.execute(stmt)).all()
        return [
            StoryArcResponse(
                id=arc.id,
                name=arc.name,
                description=arc.description,
                publisher=arc.publisher,
                start_date=arc.start_date,
                end_date=arc.end_date,
                item_count=int(item_count or 0),
            )
            for arc, item_count in rows
        ]

    async def search_creators(
        self,
        *,
        q: str | None = None,
        limit: int = 25,
    ) -> list[CreatorResponse]:
        count_expr = func.count(EntityPerson.id)
        stmt = (
            select(Person, count_expr.label("item_count"))
            .join(EntityPerson, EntityPerson.person_id == Person.id)
            .group_by(Person.id)
            .order_by(count_expr.desc(), Person.name.asc())
            .limit(limit)
        )
        if q:
            pattern = f"%{q.strip()}%"
            stmt = stmt.where(Person.name.ilike(pattern))
        rows = (await self.db.execute(stmt)).all()
        return [
            CreatorResponse(
                id=person.id,
                name=person.name,
                description=_model_text_or_metadata(person, "description"),
                image_url=_model_text_or_metadata(person, "image_url"),
                api_detail_url=_model_text_or_metadata(person, "api_detail_url"),
                site_detail_url=_model_text_or_metadata(person, "site_detail_url"),
                item_count=int(item_count or 0),
            )
            for person, item_count in rows
        ]

    async def get_creator_credits(self, creator_id: UUID) -> list[CreatorCreditResponse]:
        creator = await self.db.get(Person, creator_id)
        if creator is None:
            raise ApiHTTPException(status_code=status.HTTP_404_NOT_FOUND, code="creator_not_found", detail="Creator not found")
        links = list((await self.db.execute(select(EntityPerson).where(EntityPerson.person_id == creator_id).order_by(EntityPerson.role.asc(), EntityPerson.created_at.asc()))).scalars())
        if not links:
            return []
        summaries = await load_entity_summaries(self.db, [(link.entity_type, link.entity_id) for link in links])
        results: list[CreatorCreditResponse] = []
        for link in links:
            summary = summaries.get((link.entity_type, link.entity_id))
            if summary is None or summary.kind is None:
                continue
            results.append(CreatorCreditResponse(creator_id=creator_id, item_id=summary.entity_id, role=link.role, kind=public_item_kind(summary.kind), title=summary.title, item_number=summary.item_number, series_title=summary.series_title, volume_name=summary.volume_name, cover_image_url=summary.cover_image_url))
        return results

    async def get_story_arc_items(self, story_arc_id: UUID) -> list[StoryArcItemResponse]:
        arc = await self.db.get(StoryArc, story_arc_id)
        if arc is None:
            raise ApiHTTPException(status_code=status.HTTP_404_NOT_FOUND, code="story_arc_not_found", detail="Story arc not found")
        links = list((await self.db.execute(select(StoryArcItem).where(StoryArcItem.story_arc_id == story_arc_id).order_by(StoryArcItem.ordinal.asc().nullslast(), StoryArcItem.created_at.asc()))).scalars())
        summaries = await load_entity_summaries(self.db, [(link.entity_type, link.entity_id) for link in links])
        results: list[StoryArcItemResponse] = []
        for link in links:
            summary = summaries.get((link.entity_type, link.entity_id))
            if summary is None or summary.kind is None:
                continue
            results.append(StoryArcItemResponse(story_arc_id=story_arc_id, entity_type=link.entity_type, entity_id=link.entity_id, ordinal=link.ordinal, kind=public_item_kind(summary.kind), title=summary.title, item_number=summary.item_number, series_title=summary.series_title, volume_name=summary.volume_name, cover_image_url=summary.cover_image_url))
        return results

    async def get_story_arc_facets(self, entity_ids: list[UUID]) -> list[StoryArcFacetResponse]:
        ordered_entity_ids = list(dict.fromkeys(entity_ids))
        if not ordered_entity_ids:
            return []
        entity_order = {entity_id: index for index, entity_id in enumerate(ordered_entity_ids)}
        rows = (await self.db.execute(select(StoryArc, StoryArcItem.entity_id).join(StoryArcItem, StoryArcItem.story_arc_id == StoryArc.id).where(StoryArcItem.entity_id.in_(ordered_entity_ids)))).all()
        grouped: dict[UUID, dict[str, object]] = {}
        for arc, item_id in rows:
            bucket = grouped.setdefault(arc.id, {"arc": arc, "entity_ids": set()})
            cast_entity_ids = bucket["entity_ids"]
            if isinstance(cast_entity_ids, set):
                cast_entity_ids.add(item_id)
        facets: list[StoryArcFacetResponse] = []
        for bucket in grouped.values():
            arc = bucket["arc"]
            if not isinstance(arc, StoryArc):
                continue
            raw_entity_ids = bucket["entity_ids"]
            if not isinstance(raw_entity_ids, set):
                continue
            facet_entity_ids = sorted(raw_entity_ids, key=lambda entity_id: entity_order.get(entity_id, len(entity_order)))
            facets.append(StoryArcFacetResponse(id=arc.id, name=arc.name, description=arc.description, publisher=arc.publisher, start_date=arc.start_date, end_date=arc.end_date, item_count=len(facet_entity_ids), entity_ids=facet_entity_ids))
        facets.sort(key=lambda facet: (-facet.item_count, facet.name.casefold()))
        return facets

    async def get_creator_facets(self, entity_ids: list[UUID]) -> list[CreatorFacetResponse]:
        ordered_entity_ids = list(dict.fromkeys(entity_ids))
        if not ordered_entity_ids:
            return []
        entity_order = {entity_id: index for index, entity_id in enumerate(ordered_entity_ids)}
        rows = (await self.db.execute(select(Person, EntityPerson.entity_id, EntityPerson.role).join(EntityPerson, EntityPerson.person_id == Person.id).where(EntityPerson.entity_id.in_(ordered_entity_ids)))).all()
        grouped: dict[UUID, dict[str, object]] = {}
        for person, item_id, role in rows:
            bucket = grouped.setdefault(person.id, {"person": person, "entity_ids": set(), "role_counts": {}})
            cast_entity_ids = bucket["entity_ids"]
            if isinstance(cast_entity_ids, set):
                cast_entity_ids.add(item_id)
            cast_role_counts = bucket["role_counts"]
            if isinstance(cast_role_counts, dict):
                cast_role_counts[role] = int(cast_role_counts.get(role, 0)) + 1
        facets: list[CreatorFacetResponse] = []
        for bucket in grouped.values():
            person = bucket["person"]
            if not isinstance(person, Person):
                continue
            raw_entity_ids = bucket["entity_ids"]
            if not isinstance(raw_entity_ids, set):
                continue
            facet_entity_ids = sorted(raw_entity_ids, key=lambda entity_id: entity_order.get(entity_id, len(entity_order)))
            role_counts = bucket["role_counts"]
            facets.append(CreatorFacetResponse(id=person.id, name=person.name, description=_model_text_or_metadata(person, "description"), image_url=_model_text_or_metadata(person, "image_url"), item_count=len(facet_entity_ids), entity_ids=facet_entity_ids, role_counts=role_counts if isinstance(role_counts, dict) else {}))
        facets.sort(key=lambda facet: (-facet.item_count, facet.name.casefold()))
        return facets

    async def search_characters(self, *, q: str | None = None, limit: int = 25) -> list[CharacterResponse]:
        count_expr = func.count(CharacterAppearance.id)
        stmt = (
            select(Character, count_expr.label("appearance_count"))
            .outerjoin(CharacterAppearance, CharacterAppearance.character_id == Character.id)
            .group_by(Character.id)
            .order_by(count_expr.desc(), Character.name.asc())
            .limit(limit)
        )
        if q:
            pattern = f"%{q.strip()}%"
            stmt = stmt.where(or_(Character.name.ilike(pattern), Character.description.ilike(pattern)))
        rows = (await self.db.execute(stmt)).all()
        return [
            CharacterResponse(
                id=character.id,
                name=character.name,
                aliases=[str(alias) for alias in (character.aliases or []) if str(alias).strip()],
                description=character.description,
                image_url=character.image_url,
                first_appearance_entity_type=character.first_appearance_entity_type,
                first_appearance_entity_id=character.first_appearance_entity_id,
                appearance_count=int(appearance_count or 0),
            )
            for character, appearance_count in rows
        ]

    async def get_character_appearances(self, character_id: UUID) -> list[CharacterAppearanceResponse]:
        character = await self.db.get(Character, character_id)
        if character is None:
            raise ApiHTTPException(status_code=status.HTTP_404_NOT_FOUND, code="character_not_found", detail="Character not found")
        links = list((await self.db.execute(select(CharacterAppearance).where(CharacterAppearance.character_id == character_id).order_by(CharacterAppearance.role.asc(), CharacterAppearance.created_at.asc()))).scalars())
        summaries = await load_entity_summaries(self.db, [(link.entity_type, link.entity_id) for link in links])
        results: list[CharacterAppearanceResponse] = []
        for link in links:
            summary = summaries.get((link.entity_type, link.entity_id))
            if summary is None or summary.kind is None:
                continue
            results.append(CharacterAppearanceResponse(character_id=character_id, entity_type=link.entity_type, entity_id=link.entity_id, role=link.role, kind=public_item_kind(summary.kind), title=summary.title, item_number=summary.item_number, series_title=summary.series_title, volume_name=summary.volume_name, cover_image_url=summary.cover_image_url))
        return results

    async def get_character_facets(self, entity_ids: list[UUID]) -> list[CharacterFacetResponse]:
        ordered_entity_ids = list(dict.fromkeys(entity_ids))
        if not ordered_entity_ids:
            return []
        entity_order = {entity_id: index for index, entity_id in enumerate(ordered_entity_ids)}
        rows = (await self.db.execute(select(Character, CharacterAppearance.entity_id, CharacterAppearance.role).join(CharacterAppearance, CharacterAppearance.character_id == Character.id).where(CharacterAppearance.entity_id.in_(ordered_entity_ids)))).all()
        grouped: dict[UUID, dict[str, object]] = {}
        for character, item_id, role in rows:
            bucket = grouped.setdefault(character.id, {"character": character, "entity_ids": set(), "role_counts": {}})
            cast_entity_ids = bucket["entity_ids"]
            if isinstance(cast_entity_ids, set):
                cast_entity_ids.add(item_id)
            cast_role_counts = bucket["role_counts"]
            if isinstance(cast_role_counts, dict):
                role_key = str(role or "main")
                cast_role_counts[role_key] = int(cast_role_counts.get(role_key, 0)) + 1
        facets: list[CharacterFacetResponse] = []
        for bucket in grouped.values():
            character = bucket["character"]
            if not isinstance(character, Character):
                continue
            raw_entity_ids = bucket["entity_ids"]
            raw_role_counts = bucket["role_counts"]
            if not isinstance(raw_entity_ids, set) or not isinstance(raw_role_counts, dict):
                continue
            facet_entity_ids = sorted(raw_entity_ids, key=lambda entity_id: entity_order.get(entity_id, len(entity_order)))
            facets.append(CharacterFacetResponse(id=character.id, name=character.name, aliases=[str(alias) for alias in (character.aliases or []) if str(alias).strip()], image_url=character.image_url, item_count=len(facet_entity_ids), entity_ids=facet_entity_ids, role_counts={str(role): int(count) for role, count in raw_role_counts.items()}))
        facets.sort(key=lambda facet: (-facet.item_count, facet.name.casefold()))
        return facets
