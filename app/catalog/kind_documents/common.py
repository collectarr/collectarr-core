"""Shared contained-value shapes explicitly composed by kind schemas."""

from app.catalog.document_shape import (
    CHARACTER,
    IDENTIFIER,
    LINK,
    PERSON,
    STORY_ARC,
    ChildObjectShape,
)

_COMMON_CHILD_SHAPES = {
    "creators": PERSON,
    "contributors": PERSON,
    "identifiers": IDENTIFIER,
    "external_links": LINK,
    "trailer_urls": LINK,
    "characters": CHARACTER,
    "character_details": ChildObjectShape(
        fields=CHARACTER.fields,
        nullable=CHARACTER.nullable,
    ),
    "story_arcs": STORY_ARC,
}

def common_root_children(*names: str) -> dict[str, ChildObjectShape]:
    """Compose only child shapes explicitly supported by a kind document."""

    try:
        return {name: _COMMON_CHILD_SHAPES[name] for name in names}
    except KeyError as error:
        raise ValueError(
            f"Unknown shared Catalog Item child shape: {error.args[0]}"
        ) from error


__all__ = ["common_root_children"]
