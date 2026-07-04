from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm.attributes import NO_VALUE

from app.catalog.physical_formats import is_video_item_kind, physical_format_for_id
from app.models import (
    AnimeContribution,
    AnimeSeries,
    BoardGameWork,
    BookContribution,
    BookWork,
    ComicContribution,
    ComicWork,
    GameWork,
    MangaContribution,
    MangaWork,
    MovieWork,
    MovieWorkContribution,
    TVRelease,
    TVSeries,
)
from app.models.base import ItemKind


def item_search_document(item: Any) -> dict[str, Any]:
    barcode = None
    cover_url = None
    thumbnail_url = None
    publisher = _organization_name(item, "publisher")
    release_date = None
    release_region = None
    release_year = None
    barcodes: list[str] = []
    creators: list[str] = []
    characters: list[str] = []
    story_arcs: list[str] = []
    typed_metadata = _normalized_metadata(item)
    platforms: list[str] = (
        _string_list(typed_metadata.get("platforms"))
        if isinstance(typed_metadata.get("platforms"), list)
        else []
    )
    catalog_number = None
    release_status = None
    language = None
    imprint = _organization_name(item, "imprint")
    subtitle = None
    series_group = None
    age_rating = None
    runtime_minutes = getattr(item, "runtime_minutes", None)
    variant = None
    variant_names: list[str] = []
    series_title = None
    volume = getattr(item, "__dict__", {}).get("volume")
    if volume is not None:
        series_title = getattr(volume, "name", None) or getattr(volume, "title", None)
    volume_name = getattr(volume, "name", None) if volume is not None else None
    creator_links = sorted(
        _loaded_rows(item, "creator_links"),
        key=lambda link: (
            getattr(link, "created_at", None) is None,
            getattr(link, "created_at", None),
            str(getattr(link, "id", "") or ""),
        ),
    )
    if creator_links:
        creators.extend(
            [
                link.person.name
                for link in creator_links
                if getattr(link, "person", None) is not None and getattr(link.person, "name", None)
            ]
        )
    character_links = sorted(
        _loaded_rows(item, "character_appearances"),
        key=lambda appearance: (
            str(getattr(appearance, "role", "") or "").casefold(),
            str(getattr(getattr(appearance, "character", None), "name", "") or "").casefold(),
        ),
    )
    if character_links:
        characters.extend(
            [
                appearance.character.name
                for appearance in character_links
                if getattr(appearance, "character", None) is not None
                and getattr(appearance.character, "name", None)
            ]
        )
    story_arc_links = sorted(
        _loaded_rows(item, "story_arc_items"),
        key=lambda link: (
            getattr(link, "ordinal", None) is None,
            getattr(link, "ordinal", None) or 0,
            str(getattr(getattr(link, "story_arc", None), "name", "") or "").casefold(),
        ),
    )
    if story_arc_links:
        story_arcs.extend(
            [
                link.story_arc.name
                for link in story_arc_links
                if getattr(link, "story_arc", None) is not None
                and getattr(link.story_arc, "name", None)
            ]
        )

    for edition in item.editions:
        publisher = publisher or edition.publisher
        physical_format = _physical_format_label(
            edition.metadata_json,
            fallback_format=edition.format,
            kind=item.kind,
            preferred=getattr(edition, "physical_format", None),
        )
        if physical_format:
            _append_unique(variant_names, physical_format)
            variant = variant or physical_format
        if edition.release_date and release_year is None:
            release_date = edition.release_date.isoformat()
            release_year = edition.release_date.year
        if edition.upc:
            _append_unique(barcodes, _normalized_barcode(edition.upc))
            barcode = barcode or _normalized_barcode(edition.upc)
        if edition.isbn:
            _append_unique(barcodes, _normalized_barcode(edition.isbn))
            barcode = barcode or _normalized_barcode(edition.isbn)
        catalog_number = catalog_number or _optional_text(getattr(edition, "catalog_number", None))
        release_status = release_status or _optional_text(getattr(edition, "release_status", None))
        language = language or _optional_text(getattr(edition, "language", None))
        imprint = imprint or _optional_text(getattr(edition, "imprint", None))
        subtitle = subtitle or _optional_text(getattr(edition, "subtitle", None))
        series_group = series_group or _optional_text(getattr(edition, "series_group", None))
        age_rating = age_rating or _optional_text(getattr(edition, "age_rating", None))
        primary = next((row for row in edition.variants if row.is_primary), None)
        for variant_row in edition.variants:
            _append_unique(variant_names, variant_row.name)
            if variant_row.barcode:
                _append_unique(barcodes, _normalized_barcode(variant_row.barcode))
                barcode = barcode or _normalized_barcode(variant_row.barcode)
            if variant_row.isbn:
                _append_unique(barcodes, _normalized_barcode(variant_row.isbn))
                barcode = barcode or _normalized_barcode(variant_row.isbn)
        if primary:
            variant = physical_format or primary.name
            cover_url = cover_url or primary.cover_image_url
            thumbnail_url = thumbnail_url or primary.thumbnail_image_url
        release_region = release_region or edition.region

    return {
        "id": str(item.id),
        "kind": item.kind.value,
        "title": item.title,
        "item_number": item.item_number,
        "runtime_minutes": runtime_minutes,
        "cover_image_url": cover_url,
        "thumbnail_image_url": thumbnail_url,
        "publisher": publisher,
        "release_date": release_date,
        "region": release_region,
        "release_year": release_year,
        "barcode": barcode,
        "barcodes": barcodes,
        "variant": variant,
        "variant_names": variant_names,
        "series_title": series_title,
        "volume_name": volume_name,
        "catalog_number": catalog_number,
        "creators": _unique(creators),
        "characters": _unique(characters),
        "story_arcs": _unique(story_arcs),
        "platforms": _unique(platforms),
        "release_status": release_status,
        "language": language,
        "imprint": imprint,
        "subtitle": subtitle,
        "series_group": series_group,
        "age_rating": age_rating,
    }


def book_work_search_document(work: BookWork) -> dict[str, Any]:
    editions = sorted(
        getattr(work, "__dict__", {}).get("editions") or [],
        key=lambda row: (
            getattr(row, "publication_date", None) is None,
            getattr(row, "publication_date", None),
            str(getattr(row, "id", "")),
        ),
    )
    primary_edition = editions[0] if editions else None
    series_memberships = sorted(
        getattr(work, "__dict__", {}).get("series_memberships") or [],
        key=lambda row: (
            getattr(row, "sequence", None) is None,
            getattr(row, "sequence", None) or 0,
            str(getattr(row, "series_id", "")),
        ),
    )
    primary_series = series_memberships[0] if series_memberships else None
    creators: list[str] = []
    barcodes: list[str] = []
    variant_names: list[str] = []
    for edition in editions:
        variant = _optional_text(getattr(edition, "binding", None)) or _optional_text(getattr(edition, "format", None))
        if variant:
            _append_unique(variant_names, variant)
        for contribution in sorted(
            getattr(edition, "contributions", []) or [],
            key=lambda row: (
                getattr(row, "sequence", None) is None,
                getattr(row, "sequence", None) or 0,
                str(getattr(row, "id", "")),
            ),
        ):
            if not isinstance(contribution, BookContribution):
                continue
            person = getattr(contribution, "person", None)
            person_name = _optional_text(getattr(person, "name", None))
            if person_name:
                _append_unique(creators, person_name)
        for identifier in list(getattr(edition, "identifiers", []) or []):
            value = _optional_text(getattr(identifier, "value", None))
            if not value:
                continue
            _append_unique(barcodes, _normalized_barcode(value))
    barcode = barcodes[0] if barcodes else None
    release_date = (
        primary_edition.publication_date.isoformat()
        if primary_edition is not None and primary_edition.publication_date is not None
        else None
    )
    release_year = (
        primary_edition.publication_date.year
        if primary_edition is not None and primary_edition.publication_date is not None
        else None
    )
    return {
        "id": str(work.id),
        "kind": ItemKind.book.value,
        "title": work.title,
        "item_number": None,
        "runtime_minutes": (
            primary_edition.audio_length_minutes if primary_edition is not None else None
        ),
        "cover_image_url": primary_edition.cover_image_url if primary_edition is not None else None,
        "thumbnail_image_url": None,
        "publisher": primary_edition.publisher if primary_edition is not None else None,
        "release_date": release_date,
        "region": primary_edition.region if primary_edition is not None else None,
        "release_year": release_year,
        "barcode": barcode,
        "barcodes": barcodes,
        "variant": variant_names[0] if variant_names else None,
        "variant_names": variant_names,
        "series_title": (
            getattr(getattr(primary_series, "__dict__", {}).get("series"), "title", None)
            if primary_series is not None
            else None
        ),
        "volume_name": None,
        "catalog_number": None,
        "creators": creators,
        "characters": [],
        "story_arcs": [],
        "platforms": [],
        "release_status": primary_edition.release_status if primary_edition is not None else None,
        "language": primary_edition.language if primary_edition is not None else None,
        "imprint": primary_edition.imprint if primary_edition is not None else None,
        "subtitle": work.subtitle,
        "series_group": None,
        "age_rating": primary_edition.age_rating if primary_edition is not None else None,
    }


def game_work_search_document(work: GameWork) -> dict[str, Any]:
    releases = sorted(
        getattr(work, "releases", []) or [],
        key=lambda row: (
            getattr(row, "release_date", None) is None,
            getattr(row, "release_date", None),
            str(getattr(row, "id", "")),
        ),
    )
    primary_release = releases[0] if releases else None
    barcode = _optional_text(getattr(primary_release, "barcode", None))
    release_date = (
        primary_release.release_date.isoformat()
        if primary_release is not None and primary_release.release_date is not None
        else work.release_date.isoformat() if work.release_date is not None else None
    )
    release_year = (
        primary_release.release_date.year
        if primary_release is not None and primary_release.release_date is not None
        else work.release_date.year if work.release_date is not None else None
    )
    return {
        "id": str(work.id),
        "kind": ItemKind.game.value,
        "title": work.title,
        "item_number": None,
        "runtime_minutes": None,
        "cover_image_url": primary_release.cover_image_url if primary_release is not None else None,
        "thumbnail_image_url": None,
        "publisher": primary_release.publisher if primary_release is not None else None,
        "release_date": release_date,
        "region": primary_release.region_code if primary_release is not None else None,
        "release_year": release_year,
        "barcode": barcode,
        "barcodes": [barcode] if barcode else [],
        "variant": primary_release.platform if primary_release is not None else None,
        "variant_names": work.platforms,
        "bundle_titles": [],
        "bundle_release_ids": [],
        "series_title": None,
        "volume_name": None,
        "catalog_number": primary_release.catalog_number if primary_release is not None else None,
        "creators": [],
        "characters": [],
        "story_arcs": [],
        "platforms": work.platforms,
        "identifiers": work.identifiers,
        "company_roles": work.company_roles,
        "age_ratings": work.age_ratings,
        "release_status": primary_release.release_status if primary_release is not None else None,
        "language": primary_release.language if primary_release is not None else work.original_language,
        "imprint": None,
        "subtitle": work.subtitle,
        "series_group": None,
        "age_rating": work.age_rating,
    }


def boardgame_search_document(work: BoardGameWork) -> dict[str, Any]:
    editions = sorted(
        getattr(work, "editions", []) or [],
        key=lambda row: (
            getattr(row, "release_date", None) is None,
            getattr(row, "release_date", None),
            str(getattr(row, "id", "")),
        ),
    )
    primary_edition = editions[0] if editions else None
    release_date = (
        primary_edition.release_date.isoformat()
        if primary_edition is not None and primary_edition.release_date is not None
        else work.release_date.isoformat() if work.release_date is not None else None
    )
    release_year = (
        primary_edition.release_date.year
        if primary_edition is not None and primary_edition.release_date is not None
        else work.release_date.year if work.release_date is not None else None
    )
    return {
        "id": str(work.id),
        "kind": ItemKind.boardgame.value,
        "title": work.title,
        "item_number": None,
        "runtime_minutes": None,
        "cover_image_url": primary_edition.cover_image_url if primary_edition is not None else None,
        "thumbnail_image_url": None,
        "publisher": primary_edition.publisher if primary_edition is not None else None,
        "release_date": release_date,
        "region": primary_edition.country if primary_edition is not None else None,
        "release_year": release_year,
        "barcode": _optional_text(getattr(primary_edition, "barcode", None)),
        "barcodes": [primary_edition.barcode] if primary_edition is not None and primary_edition.barcode else [],
        "variant": primary_edition.format if primary_edition is not None else None,
        "variant_names": _unique(
            work.platforms
            + ([primary_edition.format] if primary_edition is not None and primary_edition.format else [])
        ),
        "bundle_titles": [],
        "bundle_release_ids": [],
        "series_title": None,
        "volume_name": None,
        "catalog_number": primary_edition.catalog_number if primary_edition is not None else None,
        "creators": [],
        "characters": [],
        "story_arcs": [],
        "platforms": work.platforms,
        "identifiers": work.identifiers,
        "contributors": work.contributors,
        "mechanics": work.mechanics,
        "categories": work.categories,
        "families": work.families,
        "expansions": work.expansions,
        "rankings": work.rankings,
        "release_status": primary_edition.release_status if primary_edition is not None else None,
        "language": primary_edition.language if primary_edition is not None else None,
        "imprint": None,
        "subtitle": work.subtitle,
        "series_group": None,
        "age_rating": primary_edition.age_rating if primary_edition is not None else work.age_rating,
    }


def comic_work_search_document(work: ComicWork) -> dict[str, Any]:
    issues = sorted(
        getattr(work, "issues", []) or [],
        key=lambda row: (
            getattr(row, "publication_date", None) is None,
            getattr(row, "publication_date", None),
            getattr(row, "issue_number", None) is None,
            getattr(row, "issue_number", None) or "",
            str(getattr(row, "id", "")),
        ),
    )
    primary_issue = issues[0] if issues else None
    creators: list[str] = []
    characters: list[str] = []
    story_arcs: list[str] = []
    barcodes: list[str] = []
    variant_names: list[str] = []
    for issue in issues:
        if getattr(issue, "display_title", None):
            _append_unique(variant_names, _optional_text(getattr(issue, "display_title", None)))
        for contribution in sorted(
            getattr(issue, "contributions", []) or [],
            key=lambda row: (
                getattr(row, "sequence", None) is None,
                getattr(row, "sequence", None) or 0,
                str(getattr(row, "id", "")),
            ),
        ):
            if not isinstance(contribution, ComicContribution):
                continue
            person = getattr(contribution, "person", None)
            person_name = _optional_text(getattr(person, "name", None))
            if person_name:
                _append_unique(creators, person_name)
        for identifier in getattr(issue, "identifiers", []) or []:
            value = _optional_text(getattr(identifier, "value", None))
            if value:
                _append_unique(barcodes, _normalized_barcode(value))
        for row in getattr(issue, "character_appearances", []) or []:
            character_name = _optional_text(getattr(getattr(row, "character", None), "name", None))
            if character_name:
                _append_unique(characters, character_name)
        for row in getattr(issue, "story_arc_memberships", []) or []:
            arc_name = _optional_text(getattr(getattr(row, "story_arc", None), "name", None))
            if arc_name:
                _append_unique(story_arcs, arc_name)
    barcode = barcodes[0] if barcodes else None
    release_date = (
        primary_issue.release_date.isoformat()
        if primary_issue is not None and primary_issue.release_date is not None
        else None
    )
    release_year = (
        primary_issue.release_date.year
        if primary_issue is not None and primary_issue.release_date is not None
        else None
    )
    return {
        "id": str(work.id),
        "kind": ItemKind.comic.value,
        "title": work.title,
        "item_number": primary_issue.issue_number if primary_issue is not None else None,
        "runtime_minutes": None,
        "cover_image_url": primary_issue.cover_image_url if primary_issue is not None else None,
        "thumbnail_image_url": None,
        "publisher": primary_issue.publisher if primary_issue is not None else None,
        "release_date": release_date,
        "region": primary_issue.region if primary_issue is not None else None,
        "release_year": release_year,
        "barcode": barcode,
        "barcodes": barcodes,
        "variant": variant_names[0] if variant_names else None,
        "variant_names": variant_names,
        "bundle_titles": [],
        "bundle_release_ids": [],
        "series_title": work.title,
        "volume_name": work.title,
        "catalog_number": None,
        "creators": creators,
        "characters": characters,
        "story_arcs": story_arcs,
        "platforms": [],
        "release_status": primary_issue.release_status if primary_issue is not None else None,
        "language": primary_issue.language if primary_issue is not None else None,
        "imprint": primary_issue.imprint if primary_issue is not None else None,
        "subtitle": work.subtitle,
        "series_group": None,
        "age_rating": None,
    }


def manga_work_search_document(work: MangaWork) -> dict[str, Any]:
    chapters = sorted(
        getattr(work, "chapters", []) or [],
        key=lambda row: (
            getattr(row, "publication_date", None) is None,
            getattr(row, "publication_date", None),
            getattr(row, "chapter_number", None) is None,
            getattr(row, "chapter_number", None) or 0,
            str(getattr(row, "id", "")),
        ),
    )
    primary_chapter = chapters[0] if chapters else None
    creators: list[str] = []
    characters: list[str] = []

    for contribution in sorted(
        getattr(work, "contributions", []) or [],
        key=lambda row: (
            getattr(row, "sequence", None) is None,
            getattr(row, "sequence", None) or 0,
            str(getattr(row, "id", "")),
        ),
    ):
        if not isinstance(contribution, MangaContribution):
            continue
        person = getattr(contribution, "person", None)
        person_name = _optional_text(getattr(person, "name", None))
        if person_name:
            _append_unique(creators, person_name)

    for char_app in sorted(
        getattr(work, "character_appearances", []) or [],
        key=lambda row: (
            str(getattr(getattr(row, "character", None), "name", "") or "").casefold(),
        ),
    ):
        character = getattr(char_app, "character", None)
        character_name = _optional_text(getattr(character, "name", None))
        if character_name:
            _append_unique(characters, character_name)

    release_date = (
        primary_chapter.publication_date.isoformat()
        if primary_chapter is not None and primary_chapter.publication_date is not None
        else None
    )
    release_year = (
        primary_chapter.publication_date.year
        if primary_chapter is not None and primary_chapter.publication_date is not None
        else None
    )

    return {
        "id": str(work.id),
        "kind": ItemKind.manga.value,
        "title": work.title,
        "item_number": None,
        "runtime_minutes": None,
        "cover_image_url": primary_chapter.cover_image_url if primary_chapter is not None else None,
        "thumbnail_image_url": None,
        "publisher": None,
        "release_date": release_date,
        "region": None,
        "release_year": release_year,
        "barcode": None,
        "barcodes": [],
        "variant": None,
        "variant_names": [],
        "bundle_titles": [],
        "bundle_release_ids": [],
        "series_title": None,
        "volume_name": None,
        "catalog_number": None,
        "creators": creators,
        "characters": characters,
        "story_arcs": [],
        "platforms": [],
        "release_status": None,
        "language": work.original_language,
        "imprint": None,
        "subtitle": work.subtitle,
        "series_group": None,
        "age_rating": None,
    }


def anime_series_search_document(series: AnimeSeries) -> dict[str, Any]:
    episodes = sorted(
        getattr(series, "episodes", []) or [],
        key=lambda row: (
            getattr(row, "air_date", None) is None,
            getattr(row, "air_date", None),
            getattr(row, "episode_number", None) is None,
            getattr(row, "episode_number", None) or 0,
            str(getattr(row, "id", "")),
        ),
    )
    primary_episode = episodes[0] if episodes else None
    creators: list[str] = []
    characters: list[str] = []

    for contribution in sorted(
        getattr(series, "contributions", []) or [],
        key=lambda row: (
            getattr(row, "sequence", None) is None,
            getattr(row, "sequence", None) or 0,
            str(getattr(row, "id", "")),
        ),
    ):
        if not isinstance(contribution, AnimeContribution):
            continue
        person = getattr(contribution, "person", None)
        person_name = _optional_text(getattr(person, "name", None))
        if person_name:
            _append_unique(creators, person_name)

    for char_app in sorted(
        getattr(series, "character_appearances", []) or [],
        key=lambda row: (
            str(getattr(getattr(row, "character", None), "name", "") or "").casefold(),
        ),
    ):
        character = getattr(char_app, "character", None)
        character_name = _optional_text(getattr(character, "name", None))
        if character_name:
            _append_unique(characters, character_name)

    release_date = (
        primary_episode.air_date.isoformat()
        if primary_episode is not None and primary_episode.air_date is not None
        else None
    )
    release_year = (
        primary_episode.air_date.year
        if primary_episode is not None and primary_episode.air_date is not None
        else None
    )

    return {
        "id": str(series.id),
        "kind": ItemKind.anime.value,
        "title": series.title,
        "item_number": None,
        "runtime_minutes": primary_episode.runtime_minutes if primary_episode is not None else None,
        "cover_image_url": primary_episode.cover_image_url if primary_episode is not None else None,
        "thumbnail_image_url": None,
        "publisher": None,
        "release_date": release_date,
        "region": None,
        "release_year": release_year,
        "barcode": None,
        "barcodes": [],
        "variant": None,
        "variant_names": [],
        "bundle_titles": [],
        "bundle_release_ids": [],
        "series_title": series.title,
        "volume_name": None,
        "catalog_number": None,
        "creators": creators,
        "characters": characters,
        "story_arcs": [],
        "platforms": [],
        "release_status": series.status,
        "language": series.original_language,
        "imprint": None,
        "subtitle": None,
        "series_group": None,
        "age_rating": None,
    }


def movie_work_search_document(work: MovieWork) -> dict[str, Any]:
    releases = sorted(
        getattr(work, "releases", []) or [],
        key=lambda row: (
            getattr(row, "release_date", None) is None,
            getattr(row, "release_date", None),
            str(getattr(row, "id", "")),
        ),
    )
    primary_release = releases[0] if releases else None
    creators: list[str] = []
    characters: list[str] = []

    for contribution in sorted(
        getattr(work, "contributions", []) or [],
        key=lambda row: (
            getattr(row, "sequence", None) is None,
            getattr(row, "sequence", None) or 0,
            str(getattr(row, "id", "")),
        ),
    ):
        if not isinstance(contribution, MovieWorkContribution):
            continue
        person = getattr(contribution, "person", None)
        person_name = _optional_text(getattr(person, "name", None))
        if person_name:
            _append_unique(creators, person_name)

    for char_app in sorted(
        getattr(work, "character_appearances", []) or [],
        key=lambda row: (
            str(getattr(getattr(row, "character", None), "name", "") or "").casefold(),
        ),
    ):
        character = getattr(char_app, "character", None)
        character_name = _optional_text(getattr(character, "name", None))
        if character_name:
            _append_unique(characters, character_name)

    release_date = (
        primary_release.release_date.isoformat()
        if primary_release is not None and primary_release.release_date is not None
        else work.original_release_date.isoformat() if work.original_release_date is not None else None
    )
    release_year = (
        primary_release.release_date.year
        if primary_release is not None and primary_release.release_date is not None
        else work.original_release_date.year if work.original_release_date is not None else None
    )

    return {
        "id": str(work.id),
        "kind": ItemKind.movie.value,
        "title": work.title,
        "item_number": None,
        "runtime_minutes": work.runtime_minutes,
        "cover_image_url": primary_release.cover_image_url if primary_release is not None else None,
        "thumbnail_image_url": None,
        "publisher": None,
        "release_date": release_date,
        "region": primary_release.region_code if primary_release is not None else None,
        "release_year": release_year,
        "barcode": None,
        "barcodes": [],
        "variant": primary_release.format if primary_release is not None else None,
        "variant_names": [],
        "bundle_titles": [],
        "bundle_release_ids": [],
        "series_title": None,
        "volume_name": None,
        "catalog_number": None,
        "creators": creators,
        "characters": characters,
        "story_arcs": [],
        "platforms": [],
        "release_status": None,
        "language": work.original_language,
        "imprint": None,
        "subtitle": None,
        "series_group": None,
        "age_rating": None,
    }


def tv_release_search_document(entity: TVSeries | TVRelease) -> dict[str, Any]:
    series = entity if isinstance(entity, TVSeries) else getattr(entity, "series", None) or entity
    release = entity if isinstance(entity, TVRelease) else None
    title = _optional_text(getattr(series, "title", None)) or _optional_text(getattr(release, "title", None))
    poster_url = _optional_text(getattr(series, "poster_url", None)) or _optional_text(
        getattr(release, "cover_image_url", None)
    )
    network = _optional_text(getattr(series, "network", None)) or _optional_text(getattr(release, "publisher", None))
    runtime_minutes = getattr(series, "runtime_minutes", None)
    if runtime_minutes is None:
        runtime_minutes = getattr(release, "runtime_minutes", None)
    country = _optional_text(getattr(series, "country", None)) or _optional_text(getattr(release, "region_code", None))
    original_language = _optional_text(getattr(series, "original_language", None))
    if original_language is None and release is not None and getattr(release, "language_audio", None):
        original_language = _string_list(release.language_audio)[0]
    release_status = _optional_text(getattr(series, "status", None)) or _optional_text(
        getattr(release, "content_rating", None)
    )
    season_count = getattr(series, "season_count", None)
    if season_count is None:
        season_count = getattr(release, "season_count", None)
    episode_count = getattr(series, "episode_count", None)
    if episode_count is None:
        episode_count = getattr(release, "episode_count", None)
    releases = sorted(
        getattr(series, "releases", []) or [],
        key=lambda row: (
            getattr(row, "release_date", None) is None,
            getattr(row, "release_date", None),
            str(getattr(row, "id", "")),
        ),
    )
    primary_release = releases[0] if releases else None
    creators: list[str] = []
    for contribution in sorted(
        [contribution for release in releases for contribution in (getattr(release, "contributions", []) or [])],
        key=lambda row: (
            getattr(row, "sequence", None) is None,
            getattr(row, "sequence", None) or 0,
            str(getattr(row, "id", "")),
        ),
    ):
        person = getattr(contribution, "person", None)
        person_name = _optional_text(getattr(person, "name", None))
        if person_name:
            _append_unique(creators, person_name)
    release_date_value = primary_release.release_date if primary_release is not None else getattr(release, "release_date", None)
    release_date = release_date_value.isoformat() if release_date_value is not None else None
    return {
        "id": str(series.id),
        "kind": ItemKind.tv.value,
        "title": title or str(series.id),
        "item_number": None,
        "runtime_minutes": runtime_minutes if runtime_minutes is not None else (
            primary_release.runtime_minutes if primary_release is not None else None
        ),
        "cover_image_url": poster_url if poster_url is not None else (
            primary_release.cover_image_url if primary_release is not None else None
        ),
        "thumbnail_image_url": None,
        "publisher": network if network is not None else (primary_release.publisher if primary_release is not None else None),
        "release_date": release_date,
        "region": primary_release.region_code if primary_release is not None else country,
        "release_year": release_date_value.year if release_date_value is not None else None,
        "barcode": _optional_text(getattr(primary_release, "sku", None)) if primary_release is not None else None,
        "barcodes": [primary_release.sku] if primary_release and primary_release.sku else [],
        "variant": primary_release.format if primary_release is not None else None,
        "variant_names": [primary_release.format] if primary_release and primary_release.format else [],
        "bundle_titles": [],
        "bundle_release_ids": [],
        "series_title": title or str(series.id),
        "volume_name": None,
        "catalog_number": primary_release.sku if primary_release is not None else None,
        "creators": creators,
        "characters": [],
        "story_arcs": [],
        "platforms": [],
        "release_status": release_status,
        "language": original_language,
        "imprint": None,
        "subtitle": None,
        "series_group": None,
        "age_rating": release_status,
    }


def catalog_search_document(entity: Any) -> dict[str, Any]:
    if isinstance(entity, BookWork):
        return book_work_search_document(entity)
    if isinstance(entity, ComicWork):
        return comic_work_search_document(entity)
    if isinstance(entity, MangaWork):
        return manga_work_search_document(entity)
    if isinstance(entity, AnimeSeries):
        return anime_series_search_document(entity)
    if isinstance(entity, MovieWork):
        return movie_work_search_document(entity)
    if isinstance(entity, (TVSeries, TVRelease)):
        return tv_release_search_document(entity)
    if isinstance(entity, GameWork):
        return game_work_search_document(entity)
    if isinstance(entity, BoardGameWork):
        return boardgame_search_document(entity)
    raise TypeError(f"Unsupported catalog entity type: {type(entity)!r}")


def _source_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    source = metadata.get("source")
    return source if isinstance(source, dict) else {}


def _normalized_metadata(item: Any) -> dict[str, Any]:
    metadata = getattr(item, "metadata_json", None)
    return dict(metadata.get("normalized") or {}) if isinstance(metadata, dict) else {}


def _physical_format_label(
    metadata: dict[str, Any] | None,
    *,
    fallback_format: str | None,
    kind: Any,
    preferred: str | None = None,
) -> str | None:
    config = physical_format_for_id(preferred) if preferred else None
    if isinstance(metadata, dict):
        normalized = metadata.get("normalized")
        if isinstance(normalized, dict) and normalized.get("physical_format"):
            config = physical_format_for_id(str(normalized["physical_format"]))
    if config is None and fallback_format and is_video_item_kind(kind):
        config = physical_format_for_id(fallback_format)
    return config.label if config else None


def _organization_name(item: Any, role: str) -> str | None:
    rows = sorted(
        _loaded_rows(item, "organization_links"),
        key=lambda link: (
            str(getattr(link, "role", "") or "").casefold(),
            str(getattr(getattr(link, "organization", None), "name", "") or "").casefold(),
        ),
    )
    for link in rows:
        if getattr(link, "role", None) != role:
            continue
        organization = getattr(link, "organization", None)
        name = getattr(organization, "name", None)
        if name:
            return str(name)
    return None


def _credit_names(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    names: list[str] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        name = value.get("name")
        if name:
            names.append(str(name))
    return names


def _string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    names: list[str] = []
    for value in values:
        text = str(value).strip() if value is not None else ""
        if text:
            names.append(text)
    return names


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _append_unique(values: list[str], value: str | None) -> None:
    if value and value not in values:
        values.append(value)


def _normalized_barcode(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().replace("-", "").replace(" ", "")
    return normalized or None


def _unique(values: list[str]) -> list[str]:
    unique_values: list[str] = []
    for value in values:
        _append_unique(unique_values, value)
    return unique_values


def _loaded_rows(item: Any, attr_name: str) -> list[Any]:
    attr = inspect(item).attrs[attr_name].loaded_value
    if attr is NO_VALUE or attr is None:
        return []
    return list(attr)
