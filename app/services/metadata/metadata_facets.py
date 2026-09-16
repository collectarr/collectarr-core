from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import (
    Character,
    CharacterAppearance,
    EntityPerson,
    EntityTag,
    Person,
    StoryArc,
    StoryArcItem,
    Tag,
)
from app.schemas import MetadataCredit
from app.services.metadata.metadata_helpers import model_text


async def enrich_item_metadata_facets(
    service,
    response: dict[str, Any],
    entity_type: str,
    entity_id: UUID,
    series_id: UUID | None = None,
) -> None:
    creator_rows = (
        await service.db.execute(
            select(EntityPerson, Person)
            .join(Person, Person.id == EntityPerson.person_id)
            .where(
                EntityPerson.entity_type == entity_type,
                EntityPerson.entity_id == entity_id,
            )
            .order_by(EntityPerson.role.asc(), Person.name.asc())
        )
    ).all()
    if creator_rows:
        response["creators"] = [
            MetadataCredit(
                name=person.name,
                role=link.role,
                api_detail_url=model_text(person, "api_detail_url"),
                site_detail_url=model_text(person, "site_detail_url"),
                image_url=model_text(person, "image_url"),
            )
            for link, person in creator_rows
        ]

    character_rows = (
        await service.db.execute(
            select(CharacterAppearance, Character)
            .join(Character, Character.id == CharacterAppearance.character_id)
            .where(
                CharacterAppearance.entity_type == entity_type,
                CharacterAppearance.entity_id == entity_id,
            )
            .options(selectinload(Character.alias_entries))
            .order_by(CharacterAppearance.role.asc(), Character.name.asc())
        )
    ).all()
    if character_rows:
        response["characters"] = [
            MetadataCredit(
                name=character.name,
                role=appearance.role,
                aliases=[alias.alias for alias in character.alias_entries if alias.alias.strip()],
                description=character.description,
                image_url=character.image_url,
                first_appearance_entity_type=character.first_appearance_entity_type,
                first_appearance_entity_id=character.first_appearance_entity_id,
            )
            for appearance, character in character_rows
        ]

    arc_rows = (
        await service.db.execute(
            select(StoryArcItem, StoryArc)
            .join(StoryArc, StoryArc.id == StoryArcItem.story_arc_id)
            .where(
                StoryArcItem.entity_type == entity_type,
                StoryArcItem.entity_id == entity_id,
            )
            .order_by(StoryArcItem.ordinal.asc().nullslast(), StoryArc.name.asc())
        )
    ).all()
    if arc_rows:
        response["story_arcs"] = [
            MetadataCredit(
                name=arc.name,
                description=arc.description,
                ordinal=link.ordinal,
                publisher=arc.publisher,
            )
            for link, arc in arc_rows
        ]
    if series_id is not None:
        response["tags"] = await entity_tags(service, "series", series_id)


async def entity_tags(service, entity_type: str, entity_id: UUID) -> list[str]:
    rows = await service.db.scalars(
        select(Tag.name)
        .join(EntityTag, EntityTag.tag_id == Tag.id)
        .where(
            EntityTag.entity_type == entity_type,
            EntityTag.entity_id == entity_id,
        )
        .order_by(Tag.name.asc())
    )
    return [name for name in rows if isinstance(name, str) and name.strip()]
