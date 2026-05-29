"""Comprehensive seed: 30 items × 9 library kinds, each with 10 editions,
bundles, characters, persons, organizations, tags, story arcs, and images.

All fields populated for full integration testing.

Usage:
    python -m app.scripts.seed_full          # seed everything
    python -m app.scripts.seed_full --wipe   # drop existing seed data first
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal, engine
from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import (
    Base,
    BundleRelease,
    BundleReleaseItem,
    Character,
    CharacterAppearance,
    Edition,
    EntityOrganization,
    EntityPerson,
    EntityTag,
    ExternalProviderId,
    ItemProviderLink,
    Franchise,
    ImageAsset,
    Item,
    Organization,
    Person,
    Series,
    StoryArc,
    StoryArcItem,
    Tag,
    Variant,
    Volume,
)
from app.models.user import User  # noqa: F401 – register User table on Base.metadata
from app.scripts.seed_cover_lookup import resolve_seed_cover_urls

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ITEMS_PER_KIND = 30
EDITIONS_PER_ITEM = 10

SEED_MARKER = "seed-full"  # prefix for provider IDs to identify seed data

KINDS = [
    ItemKind.comic,
    ItemKind.manga,
    ItemKind.anime,
    ItemKind.book,
    ItemKind.movie,
    ItemKind.tv,
    ItemKind.music,
    ItemKind.game,
    ItemKind.boardgame,
]

PROVIDER_FOR_KIND: dict[ItemKind, ExternalProvider] = {
    ItemKind.comic: ExternalProvider.comicvine,
    ItemKind.manga: ExternalProvider.mangadex,
    ItemKind.anime: ExternalProvider.anilist,
    ItemKind.book: ExternalProvider.openlibrary,
    ItemKind.movie: ExternalProvider.tmdb,
    ItemKind.tv: ExternalProvider.tmdb,
    ItemKind.music: ExternalProvider.musicbrainz,
    ItemKind.game: ExternalProvider.igdb,
    ItemKind.boardgame: ExternalProvider.bgg,
}

# ---------------------------------------------------------------------------
# Rich seed data per kind
# ---------------------------------------------------------------------------
_KIND_DATA: dict[ItemKind, dict[str, Any]] = {
    ItemKind.comic: {
        "franchises": ["Marvel Universe", "DC Universe", "Image Comics"],
        "series": [
            ("The Amazing Spider-Man", "amazing-spiderman", "Marvel Comics", 1963),
            ("Batman", "batman", "DC Comics", 1940),
            ("X-Men", "x-men", "Marvel Comics", 1963),
            ("Saga", "saga", "Image Comics", 2012),
            ("Invincible", "invincible", "Image Comics", 2003),
            ("Superman", "superman", "DC Comics", 1939),
        ],
        "characters": [
            "Spider-Man", "Batman", "Wolverine", "The Will", "Invincible",
            "Superman", "Venom", "Joker", "Magneto", "Lying Cat",
        ],
        "creators": [
            ("Stan Lee", "writer"), ("Todd McFarlane", "artist"), ("Jim Lee", "penciller"),
            ("Brian K. Vaughan", "writer"), ("Fiona Staples", "artist"),
            ("Frank Miller", "writer"), ("Jack Kirby", "artist"),
            ("Robert Kirkman", "writer"), ("Ryan Ottley", "artist"),
            ("Bob Kane", "creator"),
        ],
        "publishers": ["Marvel Comics", "DC Comics", "Image Comics"],
        "story_arcs": ["Clone Saga", "Death of Superman", "Dark Phoenix Saga", "The War of the Realms"],
        "tags": ["superhero", "action", "sci-fi", "drama", "horror"],
        "formats": ["Single Issue", "Trade Paperback", "Hardcover", "Omnibus", "Digital"],
        "page_count_range": (22, 48),
        "price_range": (399, 999),
    },
    ItemKind.manga: {
        "franchises": ["Shonen Jump", "Kodansha", "Viz Media"],
        "series": [
            ("One Piece", "one-piece", "Shueisha", 1997),
            ("Naruto", "naruto", "Shueisha", 1999),
            ("Attack on Titan", "attack-on-titan", "Kodansha", 2009),
            ("My Hero Academia", "my-hero-academia", "Shueisha", 2014),
            ("Demon Slayer", "demon-slayer", "Shueisha", 2016),
            ("Chainsaw Man", "chainsaw-man", "Shueisha", 2018),
        ],
        "characters": [
            "Monkey D. Luffy", "Naruto Uzumaki", "Eren Yeager", "Izuku Midoriya",
            "Tanjiro Kamado", "Denji", "Zoro", "Sasuke", "Mikasa", "All Might",
        ],
        "creators": [
            ("Eiichiro Oda", "mangaka"), ("Masashi Kishimoto", "mangaka"),
            ("Hajime Isayama", "mangaka"), ("Kohei Horikoshi", "mangaka"),
            ("Koyoharu Gotouge", "mangaka"), ("Tatsuki Fujimoto", "mangaka"),
        ],
        "publishers": ["Shueisha", "Kodansha", "Viz Media"],
        "story_arcs": ["Water 7", "Pain's Assault", "Marley Arc", "Final War"],
        "tags": ["shonen", "action", "fantasy", "drama", "dark fantasy"],
        "formats": ["Tankobon", "Digital", "Omnibus", "Box Set", "Collectors"],
        "page_count_range": (180, 220),
        "price_range": (999, 1499),
    },
    ItemKind.anime: {
        "franchises": ["Studio Ghibli", "Bones Studio", "Madhouse"],
        "series": [
            ("Fullmetal Alchemist: Brotherhood", "fma-brotherhood", "Bones", 2009),
            ("Death Note", "death-note", "Madhouse", 2006),
            ("Cowboy Bebop", "cowboy-bebop", "Sunrise", 1998),
            ("Neon Genesis Evangelion", "evangelion", "Gainax", 1995),
            ("Steins;Gate", "steins-gate", "White Fox", 2011),
            ("Mob Psycho 100", "mob-psycho", "Bones", 2016),
        ],
        "characters": [
            "Edward Elric", "Light Yagami", "Spike Spiegel", "Shinji Ikari",
            "Okabe Rintaro", "Mob", "Alphonse Elric", "L", "Faye Valentine", "Asuka",
        ],
        "creators": [
            ("Hiromu Arakawa", "mangaka"), ("Tsugumi Ohba", "writer"),
            ("Shinichiro Watanabe", "director"), ("Hideaki Anno", "director"),
            ("Jiro Taniguchi", "creator"), ("ONE", "writer"),
        ],
        "publishers": ["Funimation", "Aniplex", "Bandai Visual"],
        "story_arcs": ["Ishval Civil War", "Kira Investigation", "Bebop Bounty", "Third Impact"],
        "tags": ["action", "sci-fi", "psychological", "mecha", "comedy"],
        "formats": ["Blu-ray", "DVD", "Blu-ray Box Set", "Steelbook", "Limited Edition"],
        "runtime_range": (24, 150),
        "price_range": (2999, 7999),
    },
    ItemKind.book: {
        "franchises": ["Tolkien Legendarium", "Dune Universe", "Discworld"],
        "series": [
            ("The Lord of the Rings", "lotr", "Allen & Unwin", 1954),
            ("Dune", "dune", "Chilton Books", 1965),
            ("Discworld", "discworld", "Corgi Books", 1983),
            ("The Hitchhiker's Guide", "hitchhikers", "Pan Books", 1979),
            ("Foundation", "foundation", "Gnome Press", 1951),
            ("Neuromancer", "neuromancer", "Ace Books", 1984),
        ],
        "characters": [
            "Frodo Baggins", "Paul Atreides", "Rincewind", "Arthur Dent",
            "Hari Seldon", "Case", "Gandalf", "Stilgar", "Sam Vimes", "Ford Prefect",
        ],
        "creators": [
            ("J.R.R. Tolkien", "author"), ("Frank Herbert", "author"),
            ("Terry Pratchett", "author"), ("Douglas Adams", "author"),
            ("Isaac Asimov", "author"), ("William Gibson", "author"),
        ],
        "publishers": ["Allen & Unwin", "Ace Books", "Corgi", "HarperCollins", "Gollancz"],
        "story_arcs": ["War of the Ring", "Butlerian Jihad", "Ankh-Morpork City Watch", "Seldon Plan"],
        "tags": ["fantasy", "sci-fi", "humor", "dystopia", "classic"],
        "formats": ["Hardcover", "Paperback", "Mass Market", "Kindle", "Audiobook", "Illustrated Edition"],
        "page_count_range": (200, 800),
        "price_range": (999, 3499),
    },
    ItemKind.movie: {
        "franchises": ["The Dark Knight Trilogy", "Blade Runner", "Alien", "Star Wars", "MCU"],
        "series": [
            ("The Dark Knight Trilogy", "dark-knight", "Warner Bros.", 2005),
            ("Blade Runner", "blade-runner", "Warner Bros.", 1982),
            ("Alien", "alien", "20th Century Fox", 1979),
            ("Star Wars Original Trilogy", "star-wars-ot", "Lucasfilm", 1977),
            ("The Godfather", "godfather", "Paramount", 1972),
            ("Back to the Future", "bttf", "Universal", 1985),
        ],
        "characters": [
            "Batman", "Rick Deckard", "Ellen Ripley", "Luke Skywalker",
            "Michael Corleone", "Marty McFly", "Joker", "Roy Batty", "Xenomorph", "Han Solo",
        ],
        "creators": [
            ("Christopher Nolan", "director"), ("Ridley Scott", "director"),
            ("George Lucas", "director"), ("Francis Ford Coppola", "director"),
            ("Robert Zemeckis", "director"), ("Denis Villeneuve", "director"),
            ("Hans Zimmer", "composer"), ("John Williams", "composer"),
        ],
        "publishers": ["Warner Bros.", "Paramount", "Universal", "20th Century Fox", "Lucasfilm"],
        "story_arcs": ["Gotham's Reckoning", "Replicant Hunt", "Galactic Civil War", "Corleone Empire"],
        "tags": ["action", "sci-fi", "thriller", "noir", "adventure"],
        "formats": ["DVD", "Blu-ray", "4K UHD", "Steelbook", "Digital", "VHS", "Laserdisc",
                     "Director's Cut", "IMAX", "Criterion"],
        "runtime_range": (90, 200),
        "price_range": (999, 4999),
    },
    ItemKind.tv: {
        "franchises": ["Breaking Bad Universe", "Star Trek", "The Wire Universe"],
        "series": [
            ("Breaking Bad", "breaking-bad", "AMC", 2008),
            ("The Wire", "the-wire", "HBO", 2002),
            ("The Sopranos", "sopranos", "HBO", 1999),
            ("Chernobyl", "chernobyl", "HBO", 2019),
            ("Band of Brothers", "band-of-brothers", "HBO", 2001),
            ("Fargo", "fargo", "FX", 2014),
        ],
        "characters": [
            "Walter White", "Omar Little", "Tony Soprano", "Valery Legasov",
            "Richard Winters", "Lorne Malvo", "Jesse Pinkman", "Jimmy McNulty",
            "Carmela Soprano", "Lester Nygaard",
        ],
        "creators": [
            ("Vince Gilligan", "creator"), ("David Simon", "creator"),
            ("David Chase", "creator"), ("Craig Mazin", "writer"),
            ("Tom Hanks", "producer"), ("Noah Hawley", "creator"),
        ],
        "publishers": ["AMC", "HBO", "FX", "Netflix", "Apple TV+"],
        "story_arcs": ["Heisenberg's Rise", "The Barksdale Investigation", "North Jersey Mafia", "Reactor 4"],
        "tags": ["drama", "crime", "thriller", "historical", "dark comedy"],
        "formats": ["DVD Box Set", "Blu-ray Box Set", "4K Box Set", "Steelbook Set",
                     "Digital Season", "Complete Series"],
        "runtime_range": (42, 62),
        "price_range": (1999, 8999),
    },
    ItemKind.music: {
        "franchises": ["Classic Rock", "Progressive Rock", "Electronic"],
        "series": [
            ("Pink Floyd Discography", "pink-floyd", "Harvest Records", 1967),
            ("Radiohead Discography", "radiohead", "Parlophone", 1993),
            ("Daft Punk Discography", "daft-punk", "Virgin Records", 1997),
            ("Tool Discography", "tool", "Volcano Records", 1993),
            ("Boards of Canada", "boards-of-canada", "Warp Records", 1998),
            ("King Crimson", "king-crimson", "Island Records", 1969),
        ],
        "characters": [],
        "creators": [
            ("Roger Waters", "musician"), ("David Gilmour", "musician"),
            ("Thom Yorke", "musician"), ("Thomas Bangalter", "musician"),
            ("Maynard James Keenan", "musician"), ("Robert Fripp", "musician"),
            ("Nigel Godrich", "producer"), ("Bob Ezrin", "producer"),
        ],
        "publishers": ["Harvest Records", "Parlophone", "Virgin Records", "Warp Records",
                        "Volcano Records", "Island Records"],
        "story_arcs": [],
        "tags": ["rock", "electronic", "progressive", "experimental", "ambient"],
        "formats": ["Vinyl LP", "CD", "Cassette", "SACD", "180g Vinyl", "Picture Disc",
                     "Box Set", "Deluxe Edition", "Remaster", "Digital"],
        "runtime_range": (35, 80),
        "price_range": (1299, 4999),
    },
    ItemKind.game: {
        "franchises": ["The Elder Scrolls", "Dark Souls", "Metal Gear"],
        "series": [
            ("The Elder Scrolls", "elder-scrolls", "Bethesda", 1994),
            ("Dark Souls", "dark-souls", "FromSoftware", 2011),
            ("Metal Gear Solid", "metal-gear", "Konami", 1998),
            ("The Legend of Zelda", "zelda", "Nintendo", 1986),
            ("Final Fantasy", "final-fantasy", "Square Enix", 1987),
            ("Resident Evil", "resident-evil", "Capcom", 1996),
        ],
        "characters": [
            "Dragonborn", "Chosen Undead", "Solid Snake", "Link",
            "Cloud Strife", "Leon S. Kennedy", "Alduin", "Solaire",
            "Revolver Ocelot", "Zelda",
        ],
        "creators": [
            ("Todd Howard", "director"), ("Hidetaka Miyazaki", "director"),
            ("Hideo Kojima", "director"), ("Shigeru Miyamoto", "designer"),
            ("Hironobu Sakaguchi", "creator"), ("Shinji Mikami", "director"),
        ],
        "publishers": ["Bethesda", "FromSoftware", "Konami", "Nintendo", "Square Enix", "Capcom"],
        "story_arcs": ["Dragon Crisis", "Age of Fire", "Foxhound", "Ganon's Return"],
        "tags": ["rpg", "action", "adventure", "survival horror", "open world"],
        "formats": ["PS5", "PS4", "Xbox Series X", "Xbox One", "Nintendo Switch", "PC",
                     "Collector's Edition", "Steelbook", "Digital", "GOTY Edition"],
        "runtime_range": None,
        "price_range": (5999, 6999),
    },
    ItemKind.boardgame: {
        "franchises": ["Eurogame Classics", "Ameritrash Classics", "Cooperative Games"],
        "series": [
            ("Catan", "catan", "Kosmos", 1995),
            ("Pandemic", "pandemic", "Z-Man Games", 2008),
            ("Twilight Imperium", "twilight-imperium", "Fantasy Flight", 2005),
            ("Gloomhaven", "gloomhaven", "Cephalofair", 2017),
            ("Terraforming Mars", "terraforming-mars", "FryxGames", 2016),
            ("Wingspan", "wingspan", "Stonemaier Games", 2019),
        ],
        "characters": [],
        "creators": [
            ("Klaus Teuber", "designer"), ("Matt Leacock", "designer"),
            ("Isaac Childres", "designer"), ("Elizabeth Hargrave", "designer"),
            ("Jacob Fryxelius", "designer"), ("Dane Beltrami", "designer"),
        ],
        "publishers": ["Kosmos", "Z-Man Games", "Fantasy Flight", "Cephalofair",
                        "FryxGames", "Stonemaier Games"],
        "story_arcs": [],
        "tags": ["strategy", "cooperative", "competitive", "engine building", "area control"],
        "formats": ["Standard Box", "Big Box", "Deluxe Edition", "Kickstarter Edition",
                     "Travel Edition", "Anniversary Edition", "Expansion",
                     "Collector's Tin", "Sleeve Pack", "Wooden Insert"],
        "runtime_range": None,
        "price_range": (2999, 12999),
    },
}

# ---------------------------------------------------------------------------
# Deterministic titles per kind
# ---------------------------------------------------------------------------
_TITLE_TEMPLATES: dict[ItemKind, list[str]] = {
    ItemKind.comic: [
        "The Incredible #{n}", "Dawn of #{n}", "Crisis on Issue #{n}",
        "Dark Reckoning #{n}", "Heroes Reborn #{n}", "Civil War #{n}",
        "Infinite Crisis #{n}", "Secret Invasion #{n}", "Age of Ultron #{n}",
        "House of M #{n}",
    ],
    ItemKind.manga: [
        "Chapter {n}: New Beginning", "Chapter {n}: The Storm", "Chapter {n}: Resolve",
        "Chapter {n}: Awakening", "Chapter {n}: War Cry", "Chapter {n}: Rebirth",
        "Chapter {n}: Final Stand", "Chapter {n}: Shadow Falls", "Chapter {n}: Crimson Dawn",
        "Chapter {n}: Eternal Bond",
    ],
    ItemKind.anime: [
        "Episode {n}: Departure", "Episode {n}: Encounter", "Episode {n}: Turning Point",
        "Episode {n}: The Truth", "Episode {n}: Battle Begins", "Episode {n}: Sacrifice",
        "Episode {n}: Reunion", "Episode {n}: Final Battle", "Episode {n}: New World",
        "Episode {n}: Aftermath",
    ],
    ItemKind.book: [
        "Volume {n}: The Beginning", "Volume {n}: Rising Tide", "Volume {n}: Into the Storm",
        "Volume {n}: Shadows Fall", "Volume {n}: The Reckoning", "Volume {n}: New Dawn",
        "Volume {n}: Beyond the Horizon", "Volume {n}: The Return",
        "Volume {n}: Convergence", "Volume {n}: Endgame",
    ],
    ItemKind.movie: [
        "Part {n}", "Part {n}: Reloaded", "Part {n}: Revolutions",
        "Part {n}: Rising", "Part {n}: Awakening", "Part {n}: Unleashed",
        "Part {n}: Reckoning", "Part {n}: Genesis", "Part {n}: Infinity",
        "Part {n}: Endgame",
    ],
    ItemKind.tv: [
        "Season {n}", "Season {n}: The Return", "Season {n}: Descent",
        "Season {n}: Reckoning", "Season {n}: The Final Season",
        "Season {n}: New Blood", "Season {n}: Aftermath", "Season {n}: Origins",
        "Season {n}: Redemption", "Season {n}: Legacy",
    ],
    ItemKind.music: [
        "Album {n}: First Light", "Album {n}: Echoes", "Album {n}: Horizons",
        "Album {n}: Nocturne", "Album {n}: Pulse", "Album {n}: Frequencies",
        "Album {n}: Circuits", "Album {n}: Resonance", "Album {n}: Waves",
        "Album {n}: Static",
    ],
    ItemKind.game: [
        "Chapter {n}: The Quest Begins", "Chapter {n}: Dark Territory",
        "Chapter {n}: Final Frontier", "Chapter {n}: Legacy",
        "Chapter {n}: Rebirth", "Chapter {n}: Tactical Advance",
        "Chapter {n}: Survival", "Chapter {n}: New Game+",
        "Chapter {n}: Endgame", "Chapter {n}: DLC Pack",
    ],
    ItemKind.boardgame: [
        "Edition {n}", "Edition {n}: Revised", "Edition {n}: Deluxe",
        "Edition {n}: Expansion", "Edition {n}: Anniversary",
        "Edition {n}: Big Box", "Edition {n}: Collector's",
        "Edition {n}: Travel", "Edition {n}: Legacy", "Edition {n}: Ultimate",
    ],
}

_SYNOPSES: list[str] = [
    "A thrilling journey into the unknown that challenges everything we thought we knew.",
    "When darkness descends, unlikely heroes must rise to protect what matters most.",
    "An epic tale of ambition, betrayal, and redemption set against a sprawling world.",
    "The boundaries between reality and fiction blur in this gripping narrative.",
    "A masterwork that explores the depths of human nature and the cost of power.",
    "In the aftermath of catastrophe, survivors forge a new path forward.",
    "A cerebral puzzle that rewards close attention and multiple revisits.",
    "Heart-pounding action meets deep philosophical questions in this landmark entry.",
    "The stakes have never been higher as allies become enemies and secrets surface.",
    "A love letter to the genre that redefines what's possible.",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _deterministic_uuid(namespace: str, *parts: str) -> uuid.UUID:
    """Generate a deterministic UUID from a namespace + parts so re-runs are idempotent."""
    raw = f"{SEED_MARKER}:{namespace}:{':'.join(parts)}"
    return uuid.UUID(hashlib.md5(raw.encode()).hexdigest())  # noqa: S324


def _fake_barcode(kind: ItemKind, series_idx: int, item_idx: int, ed_idx: int) -> str:
    return f"9{kind.value[:2]}{series_idx:02d}{item_idx:03d}{ed_idx:02d}00001"


def _fake_isbn(series_idx: int, item_idx: int, ed_idx: int) -> str:
    return f"978-0-{series_idx:02d}{item_idx:02d}-{ed_idx:04d}-0"


def _fake_upc(series_idx: int, item_idx: int) -> str:
    return f"7596060{series_idx:02d}{item_idx:03d}00111"


def _item_title(kind: ItemKind, n: int) -> str:
    templates = _TITLE_TEMPLATES[kind]
    return templates[n % len(templates)].format(n=n + 1)


def _release_date(start_year: int, item_idx: int) -> date:
    base = date(start_year, 1, 15)
    return base + timedelta(days=item_idx * 30)


# ---------------------------------------------------------------------------
# Core seed logic
# ---------------------------------------------------------------------------
async def _seed_kind(db, kind: ItemKind) -> int:  # noqa: C901
    data = _KIND_DATA[kind]
    provider = PROVIDER_FOR_KIND[kind]

    created_items: list[Item] = []
    created_persons: dict[str, Person] = {}
    created_orgs: dict[str, Organization] = {}
    created_chars: dict[str, Character] = {}
    created_tags: dict[str, Tag] = {}
    created_arcs: dict[str, StoryArc] = {}

    # --- Pre-create shared entities ---

    # Persons (creators)
    for name, role in data["creators"]:
        key = name.lower()
        if key in created_persons:
            continue
        result = await db.execute(select(Person).where(Person.name == name))
        person = result.scalar_one_or_none()
        if person is None:
            person = Person(name=name, metadata_json={"seed": True, "primary_role": role})
            db.add(person)
            await db.flush()
        created_persons[key] = person

    # Organizations (publishers)
    for pub in data["publishers"]:
        key = pub.lower()
        if key in created_orgs:
            continue
        result = await db.execute(select(Organization).where(Organization.name == pub))
        org = result.scalar_one_or_none()
        if org is None:
            org = Organization(name=pub, type="publisher", metadata_json={"seed": True})
            db.add(org)
            await db.flush()
        created_orgs[key] = org

    # Characters
    for char_name in data["characters"]:
        key = char_name.lower()
        if key in created_chars:
            continue
        result = await db.execute(select(Character).where(Character.name == char_name))
        char = result.scalar_one_or_none()
        if char is None:
            char = Character(
                name=char_name,
                aliases=[f"{char_name} (alt)"],
                description=f"Seed character: {char_name}",
                metadata_json={"seed": True},
            )
            db.add(char)
            await db.flush()
        created_chars[key] = char

    # Tags
    for tag_name in data["tags"]:
        key = f"{kind.value}:{tag_name}"
        if key in created_tags:
            continue
        result = await db.execute(
            select(Tag).where(Tag.kind == kind.value, Tag.name == tag_name)
        )
        tag = result.scalar_one_or_none()
        if tag is None:
            tag = Tag(kind=kind.value, name=tag_name)
            db.add(tag)
            await db.flush()
        created_tags[key] = tag

    # Story arcs
    for arc_name in data.get("story_arcs", []):
        key = arc_name.lower()
        if key in created_arcs:
            continue
        pub = data["publishers"][0] if data["publishers"] else None
        result = await db.execute(select(StoryArc).where(StoryArc.name == arc_name))
        arc = result.scalar_one_or_none()
        if arc is None:
            arc = StoryArc(
                name=arc_name,
                description=f"Seed story arc: {arc_name}",
                publisher=pub,
                metadata_json={"seed": True},
            )
            db.add(arc)
            await db.flush()
        created_arcs[key] = arc

    # --- Create items ---
    series_list = data["series"]
    formats = data["formats"]
    arc_names = list(created_arcs.keys())
    char_names = list(created_chars.keys())
    tag_keys = list(created_tags.keys())
    creator_entries = data["creators"]

    items_for_bundles: list[tuple[Item, int, int]] = []  # (item, series_idx, item_idx)

    for item_global_idx in range(ITEMS_PER_KIND):
        series_idx = item_global_idx % len(series_list)
        item_in_series = item_global_idx // len(series_list) + 1

        series_title, series_slug, publisher, start_year = series_list[series_idx]
        franchise_name = data["franchises"][series_idx % len(data["franchises"])]

        # Franchise
        result = await db.execute(select(Franchise).where(Franchise.name == franchise_name))
        franchise = result.scalar_one_or_none()
        if franchise is None:
            franchise = Franchise(name=franchise_name, description=f"Seed franchise: {franchise_name}")
            db.add(franchise)
            await db.flush()

        # Series
        result = await db.execute(select(Series).where(Series.slug == series_slug, Series.kind == kind))
        series = result.scalar_one_or_none()
        if series is None:
            series = Series(
                franchise=franchise,
                kind=kind,
                title=series_title,
                slug=series_slug,
                original_title=f"{series_title} (Original)",
                description=f"Seed series: {series_title}",
                start_date=date(start_year, 1, 1),
                status="ongoing",
                language="en",
                country="US",
                metadata_json={"seed": True, "publisher": publisher},
            )
            db.add(series)
            await db.flush()

        # Volume
        vol_name = f"{series_title} Vol. {item_in_series}"
        result = await db.execute(
            select(Volume).where(Volume.series_id == series.id, Volume.name == vol_name)
        )
        volume = result.scalar_one_or_none()
        if volume is None:
            volume = Volume(
                series=series,
                name=vol_name,
                volume_number=item_in_series,
                start_year=start_year + item_in_series - 1,
                start_date=date(start_year + item_in_series - 1, 1, 1),
                description=f"Volume {item_in_series} of {series_title}",
                metadata_json={"seed": True},
            )
            db.add(volume)
            await db.flush()

        # Item
        item_number = str(item_global_idx + 1)
        title = _item_title(kind, item_global_idx)
        rel_date = _release_date(start_year, item_global_idx)
        synopsis = _SYNOPSES[item_global_idx % len(_SYNOPSES)]
        sort_key = f"{series_slug}-{int(item_number):04d}"

        runtime = None
        page_count = None
        season_num = None
        episode_num = None

        if data.get("runtime_range"):
            lo, hi = data["runtime_range"]
            runtime = lo + (item_global_idx * 7) % (hi - lo + 1)
        if data.get("page_count_range"):
            lo, hi = data["page_count_range"]
            page_count = lo + (item_global_idx * 3) % (hi - lo + 1)
        if kind == ItemKind.tv:
            season_num = (item_global_idx // 6) + 1
            episode_num = (item_global_idx % 6) + 1
        if kind == ItemKind.anime:
            season_num = (item_global_idx // 6) + 1
            episode_num = (item_global_idx % 6) + 1

        cover_url, thumbnail_url = await resolve_seed_cover_urls(
            kind=kind,
            slug=series_slug,
            title=title,
            series=series_title,
            fallback_key=f"{SEED_MARKER}-{kind.value}-{series_slug}-{item_number}",
        )

        result = await db.execute(
            select(Item).where(
                Item.volume_id == volume.id,
                Item.item_number == item_number,
                Item.kind == kind,
            )
        )
        item = result.scalar_one_or_none()
        if item is None:
            item = Item(
                volume=volume,
                kind=kind,
                title=title,
                item_number=item_number,
                sort_key=sort_key,
                synopsis=synopsis,
                release_type="standard",
                runtime_minutes=runtime,
                page_count=page_count,
                season_number=season_num,
                episode_number=episode_num,
                metadata_json={
                    "seed": True,
                    "publisher": publisher,
                    "cover_image_url": cover_url,
                },
            )
            db.add(item)
            await db.flush()
        else:
            metadata_json = dict(item.metadata_json) if isinstance(item.metadata_json, dict) else {}
            metadata_json.update({
                "seed": True,
                "publisher": publisher,
                "cover_image_url": cover_url,
            })
            item.metadata_json = metadata_json

        created_items.append(item)
        items_for_bundles.append((item, series_idx, item_global_idx))

        # --- 10 Editions + Variants per item ---
        for ed_idx in range(EDITIONS_PER_ITEM):
            fmt = formats[ed_idx % len(formats)]
            ed_title = f"{fmt} Edition" if ed_idx < len(formats) else f"{fmt} (Reissue {ed_idx})"
            ed_pub = data["publishers"][ed_idx % len(data["publishers"])]
            region = ["US", "UK", "EU", "JP", "AU"][ed_idx % 5]
            language = ["en", "en", "en", "ja", "en"][ed_idx % 5]

            result = await db.execute(
                select(Edition).where(
                    Edition.item_id == item.id,
                    Edition.title == ed_title,
                )
            )
            edition = result.scalar_one_or_none()
            if edition is None:
                edition = Edition(
                    item=item,
                    title=ed_title,
                    format=fmt,
                    publisher=ed_pub,
                    isbn=_fake_isbn(series_idx, item_global_idx, ed_idx) if kind in (ItemKind.book, ItemKind.comic, ItemKind.manga) else None,
                    upc=_fake_upc(series_idx, item_global_idx) if ed_idx == 0 else None,
                    language=language,
                    region=region,
                    release_date=rel_date + timedelta(days=ed_idx * 60),
                    metadata_json={"seed": True, "edition_index": ed_idx},
                )
                db.add(edition)
                await db.flush()

            # 1-3 variants per edition
            variant_count = 1 + (ed_idx % 3)
            for v_idx in range(variant_count):
                var_name = f"{fmt} Variant {chr(65 + v_idx)}" if v_idx > 0 else fmt
                var_type = ["standard", "limited", "exclusive"][v_idx % 3]
                lo, hi = data["price_range"]
                price = lo + ((item_global_idx + ed_idx + v_idx) * 100) % (hi - lo + 1)
                platform = None
                if kind == ItemKind.game:
                    platforms = ["PS5", "Xbox Series X", "PC", "Nintendo Switch"]
                    platform = platforms[(ed_idx + v_idx) % len(platforms)]

                result = await db.execute(
                    select(Variant).where(
                        Variant.edition_id == edition.id,
                        Variant.name == var_name,
                    )
                )
                variant = result.scalar_one_or_none()
                if variant is None:
                    variant = Variant(
                        edition=edition,
                        name=var_name,
                        variant_type=var_type,
                        barcode=_fake_barcode(kind, series_idx, item_global_idx, ed_idx * 3 + v_idx),
                        isbn=edition.isbn,
                        region=region,
                        platform=platform,
                        cover_price_cents=price,
                        currency=["USD", "GBP", "EUR", "JPY", "AUD"][ed_idx % 5],
                        cover_image_url=cover_url,
                        thumbnail_image_url=thumbnail_url,
                        is_primary=(v_idx == 0 and ed_idx == 0),
                        description=f"Seed variant {var_name} for {title}",
                        metadata_json={"seed": True},
                    )
                    db.add(variant)
                else:
                    variant.variant_type = var_type
                    variant.barcode = _fake_barcode(kind, series_idx, item_global_idx, ed_idx * 3 + v_idx)
                    variant.isbn = edition.isbn
                    variant.region = region
                    variant.platform = platform
                    variant.cover_price_cents = price
                    variant.currency = ["USD", "GBP", "EUR", "JPY", "AUD"][ed_idx % 5]
                    variant.cover_image_url = cover_url
                    variant.thumbnail_image_url = thumbnail_url
                    variant.is_primary = v_idx == 0 and ed_idx == 0
                    variant.description = f"Seed variant {var_name} for {title}"
                    variant.metadata_json = {"seed": True}

        # --- Provider ID ---
        pid = f"{SEED_MARKER}-{series_slug}-{item_number}"
        result = await db.execute(
            select(ItemProviderLink).where(
                ItemProviderLink.provider == provider,
                ItemProviderLink.provider_item_id == pid,
            )
        )
        if result.scalar_one_or_none() is None:
            db.add(ItemProviderLink(
                provider=provider,
                provider_item_id=pid,
                item_id=item.id,
                site_url=f"https://example.com/{kind.value}/{series_slug}/{item_number}",
                api_url=f"https://api.example.com/{kind.value}/{series_slug}/{item_number}",
            ))

        # --- Credits (EntityPerson) — 3-5 per item ---
        for cr_idx in range(min(3 + (item_global_idx % 3), len(creator_entries))):
            c_name, c_role = creator_entries[(item_global_idx + cr_idx) % len(creator_entries)]
            person = created_persons[c_name.lower()]
            result = await db.execute(
                select(EntityPerson).where(
                    EntityPerson.entity_type == "item",
                    EntityPerson.entity_id == item.id,
                    EntityPerson.person_id == person.id,
                    EntityPerson.role == c_role,
                )
            )
            if result.scalar_one_or_none() is None:
                db.add(EntityPerson(
                    entity_type="item",
                    entity_id=item.id,
                    person_id=person.id,
                    role=c_role,
                ))

        # --- Publisher (EntityOrganization) ---
        pub_key = publisher.lower()
        if pub_key in created_orgs:
            org = created_orgs[pub_key]
            result = await db.execute(
                select(EntityOrganization).where(
                    EntityOrganization.entity_type == "item",
                    EntityOrganization.entity_id == item.id,
                    EntityOrganization.organization_id == org.id,
                )
            )
            if result.scalar_one_or_none() is None:
                db.add(EntityOrganization(
                    entity_type="item",
                    entity_id=item.id,
                    organization_id=org.id,
                    role="publisher",
                ))

        # --- Characters (2-4 per item, if available) ---
        if char_names:
            for ch_idx in range(min(2 + (item_global_idx % 3), len(char_names))):
                ch_key = char_names[(item_global_idx + ch_idx) % len(char_names)]
                char = created_chars[ch_key]
                role = "main" if ch_idx < 2 else "supporting"
                result = await db.execute(
                    select(CharacterAppearance).where(
                        CharacterAppearance.character_id == char.id,
                        CharacterAppearance.item_id == item.id,
                    )
                )
                if result.scalar_one_or_none() is None:
                    db.add(CharacterAppearance(
                        character_id=char.id,
                        item_id=item.id,
                        role=role,
                    ))
                    # Set first appearance
                    if char.first_appearance_item_id is None:
                        char.first_appearance_item_id = item.id

        # --- Tags (2-3 per item) ---
        for t_idx in range(min(2 + (item_global_idx % 2), len(tag_keys))):
            t_key = tag_keys[(item_global_idx + t_idx) % len(tag_keys)]
            tag = created_tags[t_key]
            result = await db.execute(
                select(EntityTag).where(
                    EntityTag.entity_type == "item",
                    EntityTag.entity_id == item.id,
                    EntityTag.tag_id == tag.id,
                )
            )
            if result.scalar_one_or_none() is None:
                db.add(EntityTag(
                    entity_type="item",
                    entity_id=item.id,
                    tag_id=tag.id,
                ))

        # --- Story arcs (every 3rd item) ---
        if arc_names and item_global_idx % 3 == 0:
            arc_key = arc_names[item_global_idx % len(arc_names)]
            arc = created_arcs[arc_key]
            result = await db.execute(
                select(StoryArcItem).where(
                    StoryArcItem.story_arc_id == arc.id,
                    StoryArcItem.item_id == item.id,
                )
            )
            if result.scalar_one_or_none() is None:
                db.add(StoryArcItem(
                    story_arc_id=arc.id,
                    item_id=item.id,
                    ordinal=item_global_idx // 3 + 1,
                ))

        # --- Image assets (2 per item: cover + back) ---
        for img_type, is_primary in [("cover", True), ("back_cover", False)]:
            result = await db.execute(
                select(ImageAsset).where(
                    ImageAsset.entity_type == "item",
                    ImageAsset.entity_id == item.id,
                    ImageAsset.image_type == img_type,
                )
            )
            if result.scalar_one_or_none() is None:
                db.add(ImageAsset(
                    entity_type="item",
                    entity_id=item.id,
                    image_type=img_type,
                    storage_key=f"seed/{kind.value}/{series_slug}/{item_number}/{img_type}.jpg",
                    thumbnail_storage_key=f"seed/{kind.value}/{series_slug}/{item_number}/{img_type}_thumb.jpg",
                    source_url=cover_url,
                    provider=provider.value,
                    width=900 if img_type == "cover" else 600,
                    height=1350 if img_type == "cover" else 900,
                    phash=hashlib.md5(f"{SEED_MARKER}:{kind.value}:{series_slug}:{item_number}:{img_type}".encode()).hexdigest()[:16],  # noqa: S324
                    is_primary=is_primary,
                ))

    await db.flush()

    # --- Bundle releases (1 per 5 items, grouping consecutive items) ---
    bundle_count = 0
    for bundle_idx in range(0, len(items_for_bundles), 5):
        chunk = items_for_bundles[bundle_idx : bundle_idx + 5]
        if len(chunk) < 2:
            continue

        first_item, s_idx, _ = chunk[0]
        series_title, series_slug, publisher, start_year = series_list[s_idx % len(series_list)]
        bundle_title = f"{series_title} Collection Vol. {bundle_idx // 5 + 1}"
        cover_url, thumbnail_url = await resolve_seed_cover_urls(
            kind=kind,
            slug=series_slug,
            title=bundle_title,
            series=series_title,
            fallback_key=f"{SEED_MARKER}-{kind.value}-{series_slug}-bundle-{bundle_idx // 5 + 1}",
        )
        result = await db.execute(
            select(BundleRelease).where(BundleRelease.title == bundle_title, BundleRelease.kind == kind)
        )
        bundle = result.scalar_one_or_none()
        if bundle is None:
            # Get series for this bundle
            result = await db.execute(select(Series).where(Series.slug == series_slug, Series.kind == kind))
            series = result.scalar_one_or_none()

            bundle = BundleRelease(
                kind=kind,
                title=bundle_title,
                bundle_type="collection",
                series_id=series.id if series else None,
                primary_item_id=first_item.id,
                format="Box Set" if kind in (ItemKind.tv, ItemKind.music) else "Trade Paperback",
                variant_type="standard",
                packaging_type="slipcase",
                region="US",
                language="en",
                publisher=publisher,
                sku=f"SEED-{kind.value[:3].upper()}-BUN-{bundle_idx // 5 + 1:03d}",
                barcode=f"978{s_idx:02d}{bundle_idx:04d}0001",
                release_date=_release_date(start_year, bundle_idx) + timedelta(days=365),
                cover_image_url=cover_url,
                thumbnail_image_url=thumbnail_url,
                metadata_json={"seed": True, "items_count": len(chunk)},
            )
            db.add(bundle)
            await db.flush()

            for seq, (itm, _, _) in enumerate(chunk):
                db.add(BundleReleaseItem(
                    bundle_release_id=bundle.id,
                    item_id=itm.id,
                    role="included",
                    sequence_number=seq + 1,
                    disc_number=1 if kind in (ItemKind.tv, ItemKind.music, ItemKind.movie) else None,
                    disc_label=f"Disc {seq + 1}" if kind in (ItemKind.tv, ItemKind.music, ItemKind.movie) else None,
                    quantity=1,
                    is_primary=(seq == 0),
                    metadata_json={"seed": True},
                ))
        else:
            bundle.cover_image_url = cover_url
            bundle.thumbnail_image_url = thumbnail_url
            bundle.metadata_json = {"seed": True, "items_count": len(chunk)}

        bundle_count += 1

    await db.flush()
    return len(created_items)


# ---------------------------------------------------------------------------
# Wipe seed data
# ---------------------------------------------------------------------------
async def wipe_seed_data() -> None:
    """Remove all data created by seed_full (identified by provider IDs with SEED_MARKER prefix)."""
    async with AsyncSessionLocal() as db:
        # Find all seed item IDs
        result = await db.execute(
            select(ItemProviderLink.item_id).where(
                ItemProviderLink.provider_item_id.startswith(SEED_MARKER)
            )
        )
        item_ids = [row[0] for row in result.all()]
        if not item_ids:
            print("No seed data to wipe.")
            return

        # Delete in dependency order
        for model in [
            CharacterAppearance, StoryArcItem, EntityTag, EntityPerson,
            EntityOrganization, ImageAsset, BundleReleaseItem,
        ]:
            if hasattr(model, "item_id"):
                await db.execute(delete(model).where(model.item_id.in_(item_ids)))
            elif hasattr(model, "entity_id"):
                await db.execute(
                    delete(model).where(
                        model.entity_type == "item", model.entity_id.in_(item_ids)
                    )
                )

        # Bundle releases where primary_item is a seed item
        await db.execute(
            delete(BundleRelease).where(BundleRelease.primary_item_id.in_(item_ids))
        )

        # Variants → Editions → Items
        edition_ids_q = select(Edition.id).where(Edition.item_id.in_(item_ids))
        await db.execute(delete(Variant).where(Variant.edition_id.in_(edition_ids_q)))
        await db.execute(delete(Edition).where(Edition.item_id.in_(item_ids)))
        await db.execute(
            delete(ItemProviderLink).where(
                ItemProviderLink.provider_item_id.startswith(SEED_MARKER)
            )
        )
        await db.execute(delete(Item).where(Item.id.in_(item_ids)))

        await db.commit()
        print(f"Wiped {len(item_ids)} seed items and all related data.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def seed() -> None:
    wipe = "--wipe" in sys.argv

    # Ensure all tables exist (idempotent)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if wipe:
        await wipe_seed_data()

    async with AsyncSessionLocal() as db:
        total = 0
        for kind in KINDS:
            count = await _seed_kind(db, kind)
            print(f"  {kind.value}: {count} items seeded")
            total += count
        await db.commit()

    print(f"\nSeeded {total} items across {len(KINDS)} library types.")
    print(f"  Items: {total}")
    print(f"  Editions: ~{total * EDITIONS_PER_ITEM}")
    print(f"  Variants: ~{total * EDITIONS_PER_ITEM * 2}")
    print(f"  Bundles: ~{total // 5}")
    print("  + characters, credits, tags, story arcs, images per item")


if __name__ == "__main__":
    asyncio.run(seed())
