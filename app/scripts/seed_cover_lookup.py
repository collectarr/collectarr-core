from __future__ import annotations

import re

import httpx

from app.models.base import ItemKind

_WIKIPEDIA_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{page_title}"
_REQUEST_HEADERS = {
    "User-Agent": "CollectarrSeed/1.0 (https://github.com/collectarr/collectarr-core; dev seed resolver)",
    "Accept": "application/json; charset=utf-8",
}

_PAGE_TITLE_OVERRIDES: dict[str, tuple[str, ...]] = {
    "amazing-spider-man": ("The_Amazing_Spider-Man",),
    "ultimate-spider-man": ("Ultimate_Spider-Man",),
    "batman": ("Batman_(comic_book)",),
    "x-men": ("X-Men_(comic_book)",),
    "saga": ("Saga_(comics)",),
    "invincible": ("Invincible_(Image_Comics)",),
    "superman": ("Superman_(comic_book)",),
    "superman-vol-4": ("Superman_(comic_book)",),
    "hellboy-seed-of-destruction": ("Hellboy:_Seed_of_Destruction",),
    "one-piece": ("One_Piece",),
    "naruto": ("Naruto",),
    "attack-on-titan": ("Attack_on_Titan",),
    "my-hero-academia": ("My_Hero_Academia",),
    "demon-slayer": ("Demon_Slayer:_Kimetsu_no_Yaiba",),
    "chainsaw-man": ("Chainsaw_Man",),
    "fma-brotherhood": ("Fullmetal_Alchemist:_Brotherhood",),
    "death-note": ("Death_Note",),
    "cowboy-bebop": ("Cowboy_Bebop",),
    "evangelion": ("Neon_Genesis_Evangelion",),
    "steins-gate": ("Steins;Gate",),
    "mob-psycho": ("Mob_Psycho_100",),
    "lotr": ("The_Lord_of_the_Rings",),
    "dune": ("Dune_(novel)",),
    "discworld": ("The_Colour_of_Magic",),
    "hitchhikers": ("The_Hitchhiker's_Guide_to_the_Galaxy",),
    "foundation": ("Foundation_(Asimov_novel)",),
    "neuromancer": ("Neuromancer",),
    "dark-knight": ("Batman_Begins",),
    "dark-knight-trilogy": ("Batman_Begins",),
    "blade-runner": ("Blade_Runner",),
    "interstellar": ("Interstellar_(film)",),
    "mad-max": ("Mad_Max:_Fury_Road",),
    "alien": ("Alien_(film)",),
    "the-matrix": ("The_Matrix",),
    "star-wars-ot": ("Star_Wars_(film)",),
    "godfather": ("The_Godfather",),
    "bttf": ("Back_to_the_Future",),
    "breaking-bad": ("Breaking_Bad",),
    "better-call-saul": ("Better_Call_Saul",),
    "the-wire": ("The_Wire",),
    "chernobyl": ("Chernobyl_(miniseries)",),
    "sopranos": ("The_Sopranos",),
    "true-detective": ("True_Detective_(TV_series)",),
    "band-of-brothers": ("Band_of_Brothers_(miniseries)",),
    "dark-tv": ("Dark_(TV_series)",),
    "fargo": ("Fargo_(TV_series)",),
    "fleabag": ("Fleabag",),
    "pink-floyd": ("The_Dark_Side_of_the_Moon",),
    "radiohead": ("OK_Computer",),
    "daft-punk": ("Random_Access_Memories",),
    "tool": ("Lateralus",),
    "boards-of-canada": ("Music_Has_the_Right_to_Children",),
    "king-crimson": ("In_the_Court_of_the_Crimson_King",),
    "elder-scrolls": ("The_Elder_Scrolls_V:_Skyrim",),
    "dark-souls": ("Dark_Souls",),
    "metal-gear": ("Metal_Gear_Solid",),
    "zelda": ("The_Legend_of_Zelda:_Breath_of_the_Wild",),
    "final-fantasy": ("Final_Fantasy_VII",),
    "resident-evil": ("Resident_Evil_2_(2019_video_game)",),
    "catan": ("Catan",),
    "pandemic": ("Pandemic_(board_game)",),
    "twilight-imperium": ("Twilight_Imperium",),
    "gloomhaven": ("Gloomhaven",),
    "terraforming-mars": ("Terraforming_Mars",),
    "wingspan": ("Wingspan_(board_game)",),
}

_SUMMARY_CACHE: dict[str, tuple[str | None, str | None]] = {}
_RESOLUTION_CACHE: dict[str, tuple[str, str]] = {}


async def resolve_seed_cover_urls(
    *,
    kind: ItemKind,
    slug: str,
    title: str,
    series: str,
    fallback_key: str,
) -> tuple[str, str]:
    cache_key = f"{kind.value}|{slug}|{title}|{series}|{fallback_key}"
    cached = _RESOLUTION_CACHE.get(cache_key)
    if cached is not None:
        return cached

    for page_title in _candidate_page_titles(kind=kind, slug=slug, title=title, series=series):
        cover_url, thumbnail_url = await _fetch_wikipedia_image_urls(page_title)
        if cover_url is not None:
            resolved = (cover_url, thumbnail_url or cover_url)
            _RESOLUTION_CACHE[cache_key] = resolved
            return resolved

    fallback = _fallback_cover_urls(fallback_key)
    _RESOLUTION_CACHE[cache_key] = fallback
    return fallback


def _candidate_page_titles(
    *,
    kind: ItemKind,
    slug: str,
    title: str,
    series: str,
) -> list[str]:
    kind_title = kind.value.replace("_", " ")
    candidates = [
        *_PAGE_TITLE_OVERRIDES.get(slug, ()),
        title,
        series,
        f"{title} ({kind_title})",
        f"{series} ({kind_title})",
        slug.replace("-", " "),
    ]
    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = _normalize_page_title(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


async def _fetch_wikipedia_image_urls(page_title: str) -> tuple[str | None, str | None]:
    cached = _SUMMARY_CACHE.get(page_title)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(
            headers=_REQUEST_HEADERS,
            follow_redirects=True,
            timeout=10.0,
        ) as client:
            response = await client.get(
                _WIKIPEDIA_SUMMARY_URL.format(page_title=page_title),
            )
            response.raise_for_status()
    except httpx.HTTPError:
        result = (None, None)
        _SUMMARY_CACHE[page_title] = result
        return result

    payload = response.json()
    original = _nested_text(payload, "originalimage", "source")
    thumbnail = _nested_text(payload, "thumbnail", "source")
    result = (original, thumbnail or original)
    _SUMMARY_CACHE[page_title] = result
    return result


def _nested_text(payload: dict, *path: str) -> str | None:
    current: object = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    if not isinstance(current, str):
        return None
    text = current.strip()
    return text or None


def _fallback_cover_urls(fallback_key: str) -> tuple[str, str]:
    seed = _slugify_seed_part(fallback_key)
    return (
        f"https://picsum.photos/seed/{seed}/600/900",
        f"https://picsum.photos/seed/{seed}/240/360",
    )


def _normalize_page_title(value: str) -> str:
    normalized = value.strip().replace(" ", "_")
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_")


def _slugify_seed_part(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "collectarr-seed"