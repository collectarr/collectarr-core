from app.api.routes.metadata import search as metadata_search
from app.catalog.kind_documents.registry import DOCUMENTS
from app.catalog.kind_registry import (
    CATALOG_KIND_DEFINITIONS,
    CATALOG_KINDS_BY_ID,
    CATALOG_KINDS_BY_MODEL,
    CATALOG_KINDS_BY_ROUTE,
    catalog_kind_for,
)
from app.catalog.media_types import top_level_media_types
from app.catalog.metadata_field_spec import MetadataFieldSpec
from app.main import app
from app.models.base import ItemKind
from app.models.catalog_book_series import BookSeries
from app.schemas.catalog_boardgame_item import CatalogBoardGameItemResponse
from app.schemas.metadata_shared import CatalogSearchPage


def test_flat_kind_registry_has_one_catalog_root_for_every_kind():
    assert len(CATALOG_KIND_DEFINITIONS) == 9
    assert set(CATALOG_KINDS_BY_ID) == {definition.kind for definition in CATALOG_KIND_DEFINITIONS}
    assert set(DOCUMENTS) == set(CATALOG_KINDS_BY_ID)
    assert set(CATALOG_KINDS_BY_MODEL) == {
        definition.model for definition in CATALOG_KIND_DEFINITIONS
    }
    assert {media_type.kind for media_type in top_level_media_types} == set(CATALOG_KINDS_BY_ID)
    assert len(CATALOG_KINDS_BY_ROUTE) == sum(
        len(definition.route_segments) for definition in CATALOG_KIND_DEFINITIONS
    )
    assert CATALOG_KINDS_BY_ID[ItemKind.book].model.__tablename__ == "book_items"
    assert CATALOG_KINDS_BY_ID[ItemKind.music].model.__tablename__ == "music_items"
    assert all(
        definition.route_module and definition.entity_type
        for definition in CATALOG_KIND_DEFINITIONS
    )


def test_metadata_search_uses_a_paged_contract():
    assert CatalogSearchPage.model_fields.keys() == {"items", "next_offset", "has_more"}
    assert any(
        getattr(route, "path", "").endswith("/search") for route in metadata_search.router.routes
    )


def test_flat_catalog_contract_has_no_generic_grouping_model():
    schemas = app.openapi()["components"]["schemas"]
    assert "GroupingModel" not in schemas
    assert "grouping_model" not in MetadataFieldSpec.__dataclass_fields__
    assert not {"scope", "source_table", "write_target"}.intersection(
        MetadataFieldSpec.__dataclass_fields__
    )


def test_reusable_book_series_remains_a_book_specific_reference():
    assert BookSeries.__tablename__ == "book_series"


def test_music_credit_fields_are_not_part_of_other_kind_documents():
    music = catalog_kind_for(ItemKind.music).document
    artist_credit = music.children["artist_credits"]
    role_credit = music.children["credits"]
    assert {"id", "name", "sequence", "artist_id", "join_phrase"}.issubset(artist_credit.fields)
    assert {
        "id",
        "name",
        "sequence",
        "contributor_id",
        "role",
        "instruments",
    }.issubset(role_credit.fields)
    assert not artist_credit.allow_string_value

    for kind in (ItemKind.book, ItemKind.movie, ItemKind.tv):
        person = catalog_kind_for(kind).document.children["creators"]
        assert not {"artist_id", "join_phrase", "instrument"}.intersection(person.fields)

    comic_creator = catalog_kind_for(ItemKind.comic).document.children["creators"]
    assert "join_phrase" in comic_creator.fields
    assert not {"artist_id", "instrument"}.intersection(comic_creator.fields)

    comic_creator_fields = app.openapi()["components"]["schemas"]["CatalogComicCreatorResponse"][
        "properties"
    ]
    assert "join_phrase" in comic_creator_fields
    assert not {"artist_id", "instrument"}.intersection(comic_creator_fields)


def test_kind_child_shapes_and_responses_are_composed_once():
    book_children = catalog_kind_for(ItemKind.book).document.children
    assert "characters" in book_children
    assert book_children["characters"].fields == {
        "id": "string",
        "character_id": "string",
        "name": "string",
        "aliases": "string_list",
        "role": "string",
        "description": "string",
        "image_url": "string",
    }

    boardgame_children = catalog_kind_for(ItemKind.boardgame).document.children
    assert "characters" in boardgame_children
    assert "characters" in CatalogBoardGameItemResponse.model_fields
