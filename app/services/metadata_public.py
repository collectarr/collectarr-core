from __future__ import annotations

from uuid import UUID

from fastapi import status
from sqlalchemy import func, or_, select

from app.core.errors import ApiHTTPException
from app.models import (
    Character,
    CharacterAppearance,
    EntityPerson,
    Person,
    StoryArc,
    StoryArcItem,
)
from app.models.base import Base, ExternalProvider, ItemKind
from app.proposal_payload import compact_metadata_payload
from app.providers.base import ProviderSearchResult
from app.schemas import (
    CharacterAppearanceResponse,
    CharacterFacetResponse,
    CharacterResponse,
    CreatorCreditResponse,
    CreatorFacetResponse,
    CreatorResponse,
    MetadataProposalCreate,
    MetadataProposalResponse,
    ProviderSearchResultResponse,
    SeasonResponse,
    StoryArcFacetResponse,
    StoryArcItemResponse,
    StoryArcResponse,
)
from app.schemas import EpisodeResponse as ProviderEpisodeResponse
from app.schemas.metadata_shared import public_item_kind
from app.storage.image_cache import ImageCache
from app.storage.images import ImageMirror

_UPSTREAM_HTTP_STATUS_RE = __import__("re").compile(r"\bHTTP\s+(?P<status>\d{3})\b")
_PROVIDER_INTERNAL_RETRY_NAMES = {ExternalProvider.bgg.value, ExternalProvider.comicvine.value}
ITEM_TABLE = Base.metadata.tables["items"]


async def barcode_provider_search(service, barcode: str, kind: ItemKind | None = None) -> list[ProviderSearchResult]:
    cache_key = service._provider_search_cache_key("barcode", barcode, kind)
    cached_results = await service._cached_provider_search_results(cache_key)
    if cached_results is not None:
        return await service._with_stable_provider_image_urls(cached_results)

    providers = service.providers.for_kind(kind) if kind is not None else service.providers.all()
    for provider in providers:
        if not provider.is_configured or not hasattr(provider, "search_by_barcode"):
            continue
        try:
            results = await provider.search_by_barcode(barcode, kind)
        except Exception:
            service.logger.warning(
                "barcode_provider_search_failed provider=%s barcode=%s",
                provider.name,
                barcode,
                exc_info=True,
            )
            continue
        if results:
            results = results[:3]
            await service._store_provider_search_results(cache_key, results)
            return await service._with_stable_provider_image_urls(results)

    await service._store_provider_search_results(cache_key, [])
    return []


async def search_provider(
    service,
    provider_name: ExternalProvider,
    query: str | None,
    kind: ItemKind | None = None,
    *,
    series: str | None = None,
    issue_number: str | None = None,
    year: int | None = None,
) -> list[ProviderSearchResultResponse]:
    provider = service.providers.maybe_get(provider_name)
    if provider is None:
        raise ApiHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="provider_not_configured",
            detail=f"Provider '{provider_name.value}' is not configured",
        )
    if not provider.capabilities.supports_search:
        raise ApiHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="provider_search_unsupported",
            detail=f"Provider '{provider_name.value}' does not support search",
        )
    if kind is not None and not provider.capabilities.supports_kind(kind):
        raise ApiHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="provider_kind_unsupported",
            detail=f"Provider '{provider_name.value}' does not support kind '{kind.value}'",
        )
    provider_query = service._provider_search_query(
        query,
        kind,
        series=series,
        issue_number=issue_number,
        year=year,
    )
    if not provider_query:
        raise ApiHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="provider_query_required",
            detail="Provider search requires a query, series title, barcode, or issue context.",
        )
    cache_key = service._provider_search_cache_key(provider_name, provider_query, kind)
    results = await service._cached_provider_search_results(cache_key)
    should_refresh_cache = False
    if results is None:
        try:
            results = await service._search_provider_live(provider_name, provider, provider_query, kind)
        except ApiHTTPException as exc:
            fallback_results = await service._search_provider_fallback(provider_name, provider_query, kind, exc)
            if fallback_results is None:
                raise
            results = fallback_results
        should_refresh_cache = True
    enriched_results = await service._with_provider_search_enrichment(provider_name, provider_query, kind, results)
    if enriched_results is not results:
        results = enriched_results
        should_refresh_cache = True
    preview_results = await service._with_provider_search_credit_previews(provider_name, results)
    if preview_results is not results:
        results = preview_results
        should_refresh_cache = True
    if should_refresh_cache:
        await service._store_provider_search_results(cache_key, results)
    results = await service._with_stable_provider_image_urls(results)
    return [
        ProviderSearchResultResponse(
            **{**result.__dict__, "kind": public_item_kind(getattr(result, "kind", None))}
        )
        for result in results
    ]


async def search_default_provider(
    service,
    query: str | None,
    kind: ItemKind,
    *,
    series: str | None = None,
    issue_number: str | None = None,
    year: int | None = None,
) -> list[ProviderSearchResultResponse]:
    provider = service.providers.default_for_kind(kind)
    if provider is None:
        raise ApiHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="provider_not_configured",
            detail=f"No metadata provider is configured for kind '{kind.value}'",
        )
    return await search_provider(
        service,
        ExternalProvider(provider.name),
        query,
        kind,
        series=series,
        issue_number=issue_number,
        year=year,
    )


async def mirror_provider_image_url(
    service,
    source_url: str | None,
    *,
    provider_name: str | ExternalProvider,
    provider_item_id: str | None,
    cache_only: bool = False,
) -> str | None:
    if not service._can_mirror_provider_image(provider_name, source_url):
        return None
    provider_value = service._provider_value(provider_name)
    provider_item_id = provider_item_id or "unknown"
    cache = ImageCache(service.db)
    try:
        cached = await cache.cached_provider_cover(provider=provider_value, source_url=source_url or "")
        if cached is not None:
            await service.db.commit()
            return cached.public_url
        if cache_only:
            return None
        mirrored = await ImageMirror().mirror_cover_best_effort(source_url, provider_value, provider_item_id)
        if mirrored is None:
            return None
        await cache.record_mirrored_cover(mirrored)
        await service.db.commit()
        return mirrored.url
    except Exception:
        await service.db.rollback()
        service.logger.warning(
            "provider_image_mirror_failed provider=%s provider_item_id=%s source=%s",
            provider_value,
            provider_item_id,
            source_url,
            exc_info=True,
        )
        return None


async def mirror_provider_image_bytes(
    service,
    image_bytes: bytes | None,
    *,
    source_url: str | None,
    provider_name: str | ExternalProvider,
    provider_item_id: str | None,
) -> str | None:
    if not image_bytes or not service._can_mirror_provider_image(provider_name, source_url):
        return None
    provider_value = service._provider_value(provider_name)
    provider_item_id = provider_item_id or "unknown"
    cache = ImageCache(service.db)
    try:
        cached = await cache.cached_provider_cover(provider=provider_value, source_url=source_url or "")
        if cached is not None:
            await service.db.commit()
            return cached.public_url
        mirrored = await ImageMirror().mirror_cover_bytes_best_effort(
            image_bytes,
            source_url=source_url,
            provider=provider_value,
            provider_item_id=provider_item_id,
        )
        if mirrored is None:
            return None
        await cache.record_mirrored_cover(mirrored)
        await service.db.commit()
        return mirrored.url
    except Exception:
        await service.db.rollback()
        service.logger.warning(
            "provider_image_mirror_failed provider=%s provider_item_id=%s source=%s",
            provider_value,
            provider_item_id,
            source_url,
            exc_info=True,
        )
        return None


async def create_proposal(service, payload: MetadataProposalCreate) -> MetadataProposalResponse:
    from app.models import MetadataProposal

    proposal = MetadataProposal(
        provider=payload.provider,
        provider_item_id=payload.provider_item_id,
        query=payload.query,
        title=payload.title,
        summary=payload.summary,
        image_url=payload.image_url,
        metadata_payload=compact_metadata_payload(payload.metadata_payload),
    )
    service.db.add(proposal)
    await service.db.commit()
    await service.db.refresh(proposal)
    return MetadataProposalResponse.model_validate(proposal)


async def get_provider_seasons(service, provider_name: ExternalProvider, provider_item_id: str) -> list[SeasonResponse]:
    from app.providers.base import NormalizedSeason

    provider = service.providers.maybe_get(provider_name)
    if provider is None:
        raise ApiHTTPException(status_code=status.HTTP_400_BAD_REQUEST, code="provider_not_configured", detail=f"Provider '{provider_name.value}' is not configured")
    if not hasattr(provider, "get_seasons"):
        raise ApiHTTPException(status_code=status.HTTP_400_BAD_REQUEST, code="provider_seasons_unsupported", detail=f"Provider '{provider_name.value}' does not support seasons")
    seasons: list[NormalizedSeason] = await provider.get_seasons(provider_item_id)
    return [
        SeasonResponse(
            season_number=s.season_number,
            title=s.title,
            provider_item_id=s.provider_item_id,
            overview=s.overview,
            air_date=s.air_date,
            episode_count=s.episode_count,
            poster_url=s.poster_url,
            episodes=[
                ProviderEpisodeResponse(
                    episode_number=ep.episode_number,
                    title=ep.title,
                    provider_item_id=ep.provider_item_id,
                    overview=ep.overview,
                    air_date=ep.air_date,
                    runtime_minutes=ep.runtime_minutes,
                    page_count=ep.page_count,
                )
                for ep in s.episodes
            ],
        )
        for s in seasons
    ]


async def get_provider_volumes(service, provider_name: ExternalProvider, provider_item_id: str) -> list[SeasonResponse]:
    from app.providers.base import NormalizedSeason

    provider = service.providers.maybe_get(provider_name)
    if provider is None:
        raise ApiHTTPException(status_code=status.HTTP_400_BAD_REQUEST, code="provider_not_configured", detail=f"Provider '{provider_name.value}' is not configured")
    if not hasattr(provider, "get_volumes"):
        raise ApiHTTPException(status_code=status.HTTP_400_BAD_REQUEST, code="provider_volumes_unsupported", detail=f"Provider '{provider_name.value}' does not support volumes")
    volumes: list[NormalizedSeason] = await provider.get_volumes(provider_item_id)
    return [
        SeasonResponse(
            season_number=v.season_number,
            title=v.title,
            provider_item_id=v.provider_item_id,
            overview=v.overview,
            air_date=v.air_date,
            episode_count=v.episode_count,
            poster_url=v.poster_url,
            episodes=[
                ProviderEpisodeResponse(
                    episode_number=ep.episode_number,
                    title=ep.title,
                    provider_item_id=ep.provider_item_id,
                    overview=ep.overview,
                    air_date=ep.air_date,
                    runtime_minutes=ep.runtime_minutes,
                    page_count=ep.page_count,
                )
                for ep in v.episodes
            ],
        )
        for v in volumes
    ]


async def search_story_arcs(service, *, q: str | None = None, limit: int = 25) -> list[StoryArcResponse]:
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
        stmt = stmt.where(or_(StoryArc.name.ilike(pattern), StoryArc.description.ilike(pattern), StoryArc.publisher.ilike(pattern)))
    rows = (await service.db.execute(stmt)).all()
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


async def search_creators(service, *, q: str | None = None, limit: int = 25) -> list[CreatorResponse]:
    count_expr = func.count(EntityPerson.id)
    stmt = (
        select(Person, count_expr.label("item_count"))
        .join(EntityPerson, EntityPerson.person_id == Person.id)
        .where(EntityPerson.entity_type == "item")
        .group_by(Person.id)
        .order_by(count_expr.desc(), Person.name.asc())
        .limit(limit)
    )
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(Person.name.ilike(pattern))
    rows = (await service.db.execute(stmt)).all()
    return [
        CreatorResponse(
            id=person.id,
            name=person.name,
            description=service._model_text_or_metadata(person, "description"),
            image_url=service._model_text_or_metadata(person, "image_url"),
            api_detail_url=service._model_text_or_metadata(person, "api_detail_url"),
            site_detail_url=service._model_text_or_metadata(person, "site_detail_url"),
            item_count=int(item_count or 0),
        )
        for person, item_count in rows
    ]


async def get_creator_credits(service, creator_id: UUID) -> list[CreatorCreditResponse]:
    creator = await service.db.get(Person, creator_id)
    if creator is None:
        raise ApiHTTPException(status_code=status.HTTP_404_NOT_FOUND, code="creator_not_found", detail="Creator not found")
    links = list(
        (
            await service.db.execute(
                select(EntityPerson)
                .where(EntityPerson.person_id == creator_id, EntityPerson.entity_type == "item")
                .order_by(EntityPerson.role.asc(), EntityPerson.created_at.asc())
            )
        ).scalars()
    )
    if not links:
        return []
    item_ids = [link.entity_id for link in links]
    items = {
        row.id: row
        for row in (
            await service.db.execute(
                select(
                    ITEM_TABLE.c.id,
                    ITEM_TABLE.c.kind,
                    ITEM_TABLE.c.title,
                    ITEM_TABLE.c.item_number,
                    ITEM_TABLE.c.metadata_json,
                ).where(ITEM_TABLE.c.id.in_(item_ids))
            )
        ).all()
    }
    results: list[CreatorCreditResponse] = []
    for link in links:
        item = items.get(link.entity_id)
        if item is None:
            continue
        results.append(
            CreatorCreditResponse(
                creator_id=creator_id,
                item_id=item.id,
                role=link.role,
                kind=public_item_kind(item.kind),
                title=item.title,
                item_number=item.item_number,
                series_title=item.metadata_json.get("series_title") if isinstance(item.metadata_json, dict) else None,
                volume_name=item.metadata_json.get("volume_name") if isinstance(item.metadata_json, dict) else None,
                cover_image_url=item.metadata_json.get("cover_image_url") if isinstance(item.metadata_json, dict) else None,
            )
        )
    return results


async def get_story_arc_items(service, story_arc_id: UUID) -> list[StoryArcItemResponse]:
    arc = await service.db.get(StoryArc, story_arc_id)
    if arc is None:
        raise ApiHTTPException(status_code=status.HTTP_404_NOT_FOUND, code="story_arc_not_found", detail="Story arc not found")
    links = list(
        (
            await service.db.execute(
                select(StoryArcItem)
                .where(StoryArcItem.story_arc_id == story_arc_id)
                .order_by(StoryArcItem.ordinal.asc().nullslast(), StoryArcItem.created_at.asc())
            )
        ).scalars()
    )
    item_ids = [link.item_id for link in links]
    items = {
    row.id: row
    for row in (
        await service.db.execute(
            select(
                ITEM_TABLE.c.id,
                ITEM_TABLE.c.kind,
                ITEM_TABLE.c.title,
                ITEM_TABLE.c.item_number,
                ITEM_TABLE.c.metadata_json,
            ).where(ITEM_TABLE.c.id.in_(item_ids))
        )
    ).all()
    }
    return [
    StoryArcItemResponse(
        story_arc_id=story_arc_id,
        item_id=link.item_id,
        ordinal=link.ordinal,
        kind=public_item_kind(items[link.item_id].kind),
        title=items[link.item_id].title,
        item_number=items[link.item_id].item_number,
        series_title=items[link.item_id].metadata_json.get("series_title") if isinstance(items[link.item_id].metadata_json, dict) else None,
        volume_name=items[link.item_id].metadata_json.get("volume_name") if isinstance(items[link.item_id].metadata_json, dict) else None,
        cover_image_url=items[link.item_id].metadata_json.get("cover_image_url") if isinstance(items[link.item_id].metadata_json, dict) else None,
    )
    for link in links
    if link.item_id in items
    ]


async def get_story_arc_facets(service, item_ids: list[UUID]) -> list[StoryArcFacetResponse]:
    ordered_item_ids = list(dict.fromkeys(item_ids))
    if not ordered_item_ids:
        return []
    item_order = {item_id: index for index, item_id in enumerate(ordered_item_ids)}
    rows = (await service.db.execute(select(StoryArc, StoryArcItem.item_id).join(StoryArcItem, StoryArcItem.story_arc_id == StoryArc.id).where(StoryArcItem.item_id.in_(ordered_item_ids)))).all()
    grouped: dict[UUID, dict[str, object]] = {}
    for arc, item_id in rows:
        bucket = grouped.setdefault(arc.id, {"arc": arc, "item_ids": set()})
        cast_item_ids = bucket["item_ids"]
        if isinstance(cast_item_ids, set):
            cast_item_ids.add(item_id)
    facets: list[StoryArcFacetResponse] = []
    for bucket in grouped.values():
        arc = bucket["arc"]
        if not isinstance(arc, StoryArc):
            continue
        raw_item_ids = bucket["item_ids"]
        if not isinstance(raw_item_ids, set):
            continue
        facet_item_ids = sorted(raw_item_ids, key=lambda item_id: item_order.get(item_id, len(item_order)))
        facets.append(
            StoryArcFacetResponse(
                id=arc.id,
                name=arc.name,
                description=arc.description,
                publisher=arc.publisher,
                start_date=arc.start_date,
                end_date=arc.end_date,
                item_count=len(facet_item_ids),
                item_ids=facet_item_ids,
            )
        )
    facets.sort(key=lambda facet: (-facet.item_count, facet.name.casefold()))
    return facets


async def get_creator_facets(service, item_ids: list[UUID]) -> list[CreatorFacetResponse]:
    ordered_item_ids = list(dict.fromkeys(item_ids))
    if not ordered_item_ids:
        return []
    item_order = {item_id: index for index, item_id in enumerate(ordered_item_ids)}
    rows = (await service.db.execute(select(Person, EntityPerson.entity_id, EntityPerson.role).join(EntityPerson, EntityPerson.person_id == Person.id).where(EntityPerson.entity_type == "item", EntityPerson.entity_id.in_(ordered_item_ids)))).all()
    grouped: dict[UUID, dict[str, object]] = {}
    for person, item_id, role in rows:
        bucket = grouped.setdefault(person.id, {"person": person, "item_ids": set(), "role_counts": {}})
        cast_item_ids = bucket["item_ids"]
        if isinstance(cast_item_ids, set):
            cast_item_ids.add(item_id)
        cast_role_counts = bucket["role_counts"]
        if isinstance(cast_role_counts, dict):
            cast_role_counts[role] = int(cast_role_counts.get(role, 0)) + 1
    facets: list[CreatorFacetResponse] = []
    for bucket in grouped.values():
        person = bucket["person"]
        if not isinstance(person, Person):
            continue
        raw_item_ids = bucket["item_ids"]
        if not isinstance(raw_item_ids, set):
            continue
        facet_item_ids = sorted(raw_item_ids, key=lambda item_id: item_order.get(item_id, len(item_order)))
        role_counts = bucket["role_counts"]
        facets.append(
            CreatorFacetResponse(
                id=person.id,
                name=person.name,
                description=service._model_text_or_metadata(person, "description"),
                image_url=service._model_text_or_metadata(person, "image_url"),
                item_count=len(facet_item_ids),
                item_ids=facet_item_ids,
                role_counts=role_counts if isinstance(role_counts, dict) else {},
            )
        )
    facets.sort(key=lambda facet: (-facet.item_count, facet.name.casefold()))
    return facets


async def search_characters(service, *, q: str | None = None, limit: int = 25) -> list[CharacterResponse]:
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
    rows = (await service.db.execute(stmt)).all()
    return [
        CharacterResponse(
            id=character.id,
            name=character.name,
            aliases=[str(alias) for alias in (character.aliases or []) if str(alias).strip()],
            description=character.description,
            image_url=character.image_url,
            first_appearance_item_id=character.first_appearance_item_id,
            appearance_count=int(appearance_count or 0),
        )
        for character, appearance_count in rows
    ]


async def get_character_appearances(service, character_id: UUID) -> list[CharacterAppearanceResponse]:
    character = await service.db.get(Character, character_id)
    if character is None:
        raise ApiHTTPException(status_code=status.HTTP_404_NOT_FOUND, code="character_not_found", detail="Character not found")
    links = list(
        (
            await service.db.execute(
                select(CharacterAppearance)
                .where(CharacterAppearance.character_id == character_id)
                .order_by(CharacterAppearance.role.asc(), CharacterAppearance.created_at.asc())
            )
        ).scalars()
    )
    item_ids = [link.item_id for link in links]
    items = {
    row.id: row
    for row in (
        await service.db.execute(
            select(
                ITEM_TABLE.c.id,
                ITEM_TABLE.c.kind,
                ITEM_TABLE.c.title,
                ITEM_TABLE.c.item_number,
                ITEM_TABLE.c.metadata_json,
            ).where(ITEM_TABLE.c.id.in_(item_ids))
        )
    ).all()
    }
    return [
    CharacterAppearanceResponse(
        character_id=character_id,
        item_id=link.item_id,
        role=link.role,
        kind=public_item_kind(items[link.item_id].kind),
        title=items[link.item_id].title,
        item_number=items[link.item_id].item_number,
        series_title=items[link.item_id].metadata_json.get("series_title") if isinstance(items[link.item_id].metadata_json, dict) else None,
        volume_name=items[link.item_id].metadata_json.get("volume_name") if isinstance(items[link.item_id].metadata_json, dict) else None,
        cover_image_url=items[link.item_id].metadata_json.get("cover_image_url") if isinstance(items[link.item_id].metadata_json, dict) else None,
    )
    for link in links
    if link.item_id in items
    ]


async def get_character_facets(service, item_ids: list[UUID]) -> list[CharacterFacetResponse]:
    ordered_item_ids = list(dict.fromkeys(item_ids))
    if not ordered_item_ids:
        return []
    item_order = {item_id: index for index, item_id in enumerate(ordered_item_ids)}
    rows = (await service.db.execute(select(Character, CharacterAppearance.item_id, CharacterAppearance.role).join(CharacterAppearance, CharacterAppearance.character_id == Character.id).where(CharacterAppearance.item_id.in_(ordered_item_ids)))).all()
    grouped: dict[UUID, dict[str, object]] = {}
    for character, item_id, role in rows:
        bucket = grouped.setdefault(character.id, {"character": character, "item_ids": set(), "role_counts": {}})
        cast_item_ids = bucket["item_ids"]
        if isinstance(cast_item_ids, set):
            cast_item_ids.add(item_id)
        cast_role_counts = bucket["role_counts"]
        if isinstance(cast_role_counts, dict):
            role_key = str(role or "main")
            cast_role_counts[role_key] = int(cast_role_counts.get(role_key, 0)) + 1
    facets: list[CharacterFacetResponse] = []
    for bucket in grouped.values():
        character = bucket["character"]
        if not isinstance(character, Character):
            continue
        raw_item_ids = bucket["item_ids"]
        raw_role_counts = bucket["role_counts"]
        if not isinstance(raw_item_ids, set) or not isinstance(raw_role_counts, dict):
            continue
        facet_item_ids = sorted(raw_item_ids, key=lambda item_id: item_order.get(item_id, len(item_order)))
        facets.append(
            CharacterFacetResponse(
                id=character.id,
                name=character.name,
                aliases=[str(alias) for alias in (character.aliases or []) if str(alias).strip()],
                image_url=character.image_url,
                item_count=len(facet_item_ids),
                item_ids=facet_item_ids,
                role_counts={str(role): int(count) for role, count in raw_role_counts.items()},
            )
        )
    facets.sort(key=lambda facet: (-facet.item_count, facet.name.casefold()))
    return facets
