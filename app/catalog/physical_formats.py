from dataclasses import dataclass

from app.models.base import ItemKind


@dataclass(frozen=True)
class PhysicalFormatConfig:
    id: str
    label: str
    media_family: str
    variant_type: str
    aliases: tuple[str, ...] = ()


video_physical_formats: tuple[PhysicalFormatConfig, ...] = (
    PhysicalFormatConfig(
        id="dvd",
        label="DVD",
        media_family="video",
        variant_type="physical",
    ),
    PhysicalFormatConfig(
        id="blu-ray",
        label="Blu-ray",
        media_family="video",
        variant_type="physical",
        aliases=("bluray", "blu ray"),
    ),
    PhysicalFormatConfig(
        id="4k-uhd",
        label="4K UHD",
        media_family="video",
        variant_type="physical",
        aliases=("4k", "uhd", "4k blu-ray", "4k bluray", "ultra hd"),
    ),
    PhysicalFormatConfig(
        id="vhs",
        label="VHS",
        media_family="video",
        variant_type="physical",
    ),
    PhysicalFormatConfig(
        id="laserdisc",
        label="LaserDisc",
        media_family="video",
        variant_type="physical",
    ),
    PhysicalFormatConfig(
        id="digital",
        label="Digital",
        media_family="video",
        variant_type="digital",
    ),
)

_PHYSICAL_FORMATS_BY_ID = {
    key: config
    for config in video_physical_formats
    for key in (config.id, *config.aliases)
}

video_item_kinds = frozenset({
    ItemKind.anime,
    ItemKind.movie,
    ItemKind.tv,
})


def physical_format_for_id(format_id: str) -> PhysicalFormatConfig | None:
    return _PHYSICAL_FORMATS_BY_ID.get(format_id.strip().lower())


def is_video_item_kind(kind: ItemKind | str | None) -> bool:
    if kind is None:
        return False
    if isinstance(kind, ItemKind):
        return kind in video_item_kinds
    try:
        return ItemKind(kind) in video_item_kinds
    except ValueError:
        return False
