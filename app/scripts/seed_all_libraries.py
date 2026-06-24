"""Seed data for ALL library types — 10 items each with varied editions/variants.

All fields populated: creators, characters, story arcs, tags, publishers,
edition details (imprint, series_group, age_rating, catalog_number,
release_status), fully-populated series and volumes.

Usage:
    python -m app.scripts.seed_all_libraries
"""

import asyncio
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import (
    BundleRelease,
    BundleReleaseItem,
    BundleReleaseProviderLink,
    Character,
    CharacterAppearance,
    Edition,
    EntityOrganization,
    EntityPerson,
    EntityTag,
    Franchise,
    Item,
    ItemProviderLink,
    Organization,
    Person,
    Series,
    StoryArc,
    StoryArcItem,
    Tag,
    Variant,
    Volume,
)
from app.scripts.seed_cover_lookup import resolve_seed_cover_urls

# ---------------------------------------------------------------------------
# Provider mapping per kind
# ---------------------------------------------------------------------------
_PROVIDER_FOR_KIND: dict[ItemKind, ExternalProvider] = {
    ItemKind.comic: ExternalProvider.comicvine,
    ItemKind.manga: ExternalProvider.hardcover,
    ItemKind.anime: ExternalProvider.anilist,
    ItemKind.book: ExternalProvider.openlibrary,
    ItemKind.game: ExternalProvider.igdb,
    ItemKind.boardgame: ExternalProvider.bgg,
    ItemKind.movie: ExternalProvider.tmdb,
    ItemKind.tv: ExternalProvider.tmdb,
    ItemKind.music: ExternalProvider.musicbrainz,
}


# ---------------------------------------------------------------------------
# Generic seed entry
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SeedCreator:
    name: str
    role: str  # writer, artist, director, musician, designer, author, etc.


@dataclass(frozen=True)
class SeedCharacter:
    name: str
    role: str = "main"  # main, supporting, cameo, antagonist


@dataclass(frozen=True)
class SeedEntry:
    kind: ItemKind
    franchise: str
    publisher: str
    series: str
    slug: str
    volume: str
    volume_number: int
    start_year: int
    item_number: str
    title: str
    synopsis: str
    release_date: date
    title_extension: str | None = None
    runtime_minutes: int | None = None
    page_count: int | None = None
    season_number: int | None = None
    episode_number: int | None = None
    metadata_json: dict | None = None
    editions: list["SeedEdition"] = field(default_factory=list)
    creators: list[SeedCreator] = field(default_factory=list)
    characters: list[SeedCharacter] = field(default_factory=list)
    story_arcs: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    # Series-level overrides
    series_original_title: str | None = None
    series_status: str = "ongoing"
    series_language: str = "en"
    series_country: str = "US"

    @property
    def sort_key(self) -> str:
        num = self.item_number.lower().replace(" ", "").replace("#", "")
        try:
            return f"{self.slug}-{int(num):04d}"
        except ValueError:
            return f"{self.slug}-{num}"

    @property
    def provider(self) -> ExternalProvider:
        return _PROVIDER_FOR_KIND[self.kind]

    @property
    def provider_id(self) -> str:
        return f"seed-{self.slug}-{self.item_number.lower().replace(' ', '-')}"


@dataclass(frozen=True)
class SeedEdition:
    title: str
    fmt: str  # format column
    publisher: str | None = None
    language: str = "en"
    region: str | None = None
    release_date: date | None = None
    upc: str | None = None
    isbn: str | None = None
    imprint: str | None = None
    subtitle: str | None = None
    series_group: str | None = None
    age_rating: str | None = None
    catalog_number: str | None = None
    release_status: str | None = None
    variants: list["SeedVariant"] = field(default_factory=list)


@dataclass(frozen=True)
class SeedVariant:
    name: str
    variant_type: str | None = None
    barcode: str | None = None
    isbn: str | None = None
    sku: str | None = None
    region: str | None = None
    is_primary: bool = True
    cover_price_cents: int | None = None
    currency: str | None = None
    platform: str | None = None
    description: str | None = None
    metadata_json: dict | None = None


# ---------------------------------------------------------------------------
# Helper – create default edition if none supplied
# ---------------------------------------------------------------------------
def _default_edition(entry: SeedEntry) -> SeedEdition:
    return SeedEdition(
        title="Standard Edition",
        fmt="Standard",
        publisher=entry.publisher,
        release_date=entry.release_date,
        variants=[SeedVariant(name="Standard", is_primary=True)],
    )


# ===================================================================
#  MOVIES (10)
# ===================================================================
SEED_MOVIES = [
    SeedEntry(
        kind=ItemKind.movie, franchise="The Dark Knight Trilogy", publisher="Warner Bros.",
        series="The Dark Knight Trilogy", slug="dark-knight-trilogy",
        volume="The Dark Knight Trilogy", volume_number=1, start_year=2005,
        item_number="1", title="Batman Begins", title_extension="Year One",
        synopsis="After witnessing his parents' murder, Bruce Wayne trains to become a symbol of justice.",
        release_date=date(2005, 6, 15), runtime_minutes=140,
        series_original_title="The Dark Knight Saga", series_status="completed", series_country="US",
        creators=[SeedCreator("Christopher Nolan", "director"), SeedCreator("Hans Zimmer", "composer"),
                  SeedCreator("David S. Goyer", "writer")],
        characters=[SeedCharacter("Bruce Wayne", "main"), SeedCharacter("Ra's al Ghul", "antagonist"),
                    SeedCharacter("Alfred Pennyworth", "supporting")],
        story_arcs=["Batman's Origin"],
        tags=["superhero", "action", "thriller", "origin story"],
        editions=[
            SeedEdition(title="DVD", fmt="DVD", publisher="Warner Bros.", release_date=date(2005, 10, 18),
                        region="US", age_rating="PG-13", release_status="released",
                        variants=[SeedVariant(name="DVD", variant_type="physical", cover_price_cents=1999, currency="USD",
                                             barcode="012569593763", region="US")]),
            SeedEdition(title="Blu-ray", fmt="Blu-ray", publisher="Warner Bros.", release_date=date(2008, 7, 8),
                        region="US", age_rating="PG-13",
                        variants=[SeedVariant(name="Blu-ray", variant_type="physical", cover_price_cents=2499, currency="USD")]),
            SeedEdition(title="4K UHD", fmt="4K UHD", publisher="Warner Bros.", release_date=date(2017, 12, 19),
                        region="US", imprint="DC Films", age_rating="PG-13",
                        variants=[SeedVariant(name="4K UHD", variant_type="physical", cover_price_cents=2999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.movie, franchise="The Dark Knight Trilogy", publisher="Warner Bros.",
        series="The Dark Knight Trilogy", slug="dark-knight-trilogy",
        volume="The Dark Knight Trilogy", volume_number=1, start_year=2005,
        item_number="2", title="The Dark Knight",
        synopsis="Batman faces the Joker, a criminal mastermind who seeks to plunge Gotham into anarchy.",
        release_date=date(2008, 7, 18), runtime_minutes=152,
        creators=[SeedCreator("Christopher Nolan", "director"), SeedCreator("Hans Zimmer", "composer"),
                  SeedCreator("Heath Ledger", "actor")],
        characters=[SeedCharacter("Bruce Wayne", "main"), SeedCharacter("The Joker", "antagonist"),
                    SeedCharacter("Harvey Dent", "supporting")],
        story_arcs=["Gotham's Reckoning"],
        tags=["superhero", "action", "crime", "thriller"],
        editions=[
            SeedEdition(title="Blu-ray", fmt="Blu-ray", publisher="Warner Bros.", release_date=date(2008, 12, 9),
                        region="US", age_rating="PG-13",
                        variants=[SeedVariant(name="Blu-ray", variant_type="physical", cover_price_cents=2499, currency="USD")]),
            SeedEdition(title="4K UHD Steelbook", fmt="4K UHD", publisher="Warner Bros.", release_date=date(2017, 12, 19),
                        region="US", imprint="DC Films", series_group="The Dark Knight Collection",
                        variants=[SeedVariant(name="Steelbook", variant_type="physical", cover_price_cents=3499, currency="USD",
                                             description="Limited steelbook edition with IMAX sequences")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.movie, franchise="The Dark Knight Trilogy", publisher="Warner Bros.",
        series="The Dark Knight Trilogy", slug="dark-knight-trilogy",
        volume="The Dark Knight Trilogy", volume_number=1, start_year=2005,
        item_number="3", title="The Dark Knight Rises",
        synopsis="Eight years after the Joker's reign, Bane forces Batman out of exile.",
        release_date=date(2012, 7, 20), runtime_minutes=165,
        creators=[SeedCreator("Christopher Nolan", "director"), SeedCreator("Tom Hardy", "actor")],
        characters=[SeedCharacter("Bruce Wayne", "main"), SeedCharacter("Bane", "antagonist"),
                    SeedCharacter("Selina Kyle", "supporting")],
        tags=["superhero", "action", "epic"],
    ),
    SeedEntry(
        kind=ItemKind.movie, franchise="Blade Runner", publisher="Warner Bros.",
        series="Blade Runner", slug="blade-runner",
        volume="Blade Runner", volume_number=1, start_year=1982,
        item_number="1", title="Blade Runner",
        synopsis="A blade runner must pursue and terminate four replicants who have returned to Earth.",
        release_date=date(1982, 6, 25), runtime_minutes=117,
        series_status="completed", series_country="US",
        creators=[SeedCreator("Ridley Scott", "director"), SeedCreator("Vangelis", "composer"),
                  SeedCreator("Hampton Fancher", "writer")],
        characters=[SeedCharacter("Rick Deckard", "main"), SeedCharacter("Roy Batty", "antagonist"),
                    SeedCharacter("Rachael", "supporting")],
        story_arcs=["Replicant Hunt"],
        tags=["sci-fi", "noir", "dystopia", "cyberpunk"],
        editions=[
            SeedEdition(title="The Final Cut", fmt="Blu-ray", publisher="Warner Bros.", release_date=date(2007, 12, 18),
                        region="US", release_status="released",
                        variants=[SeedVariant(name="The Final Cut Blu-ray", variant_type="physical")]),
            SeedEdition(title="Director's Cut", fmt="DVD", publisher="Warner Bros.", release_date=date(1997, 9, 9),
                        region="US",
                        variants=[SeedVariant(name="Director's Cut DVD", variant_type="physical")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.movie, franchise="Blade Runner", publisher="Columbia Pictures",
        series="Blade Runner", slug="blade-runner",
        volume="Blade Runner", volume_number=1, start_year=1982,
        item_number="2", title="Blade Runner 2049",
        synopsis="A young blade runner's discovery of a secret leads him to seek out the former blade runner.",
        release_date=date(2017, 10, 6), runtime_minutes=164,
        creators=[SeedCreator("Denis Villeneuve", "director"), SeedCreator("Roger Deakins", "cinematographer"),
                  SeedCreator("Benjamin Wallfisch", "composer")],
        characters=[SeedCharacter("Officer K", "main"), SeedCharacter("Rick Deckard", "supporting"),
                    SeedCharacter("Niander Wallace", "antagonist")],
        tags=["sci-fi", "noir", "cyberpunk"],
    ),
    SeedEntry(
        kind=ItemKind.movie, franchise="Interstellar", publisher="Paramount Pictures",
        series="Interstellar", slug="interstellar",
        volume="Interstellar", volume_number=1, start_year=2014,
        item_number="1", title="Interstellar",
        synopsis="A team of explorers travel through a wormhole in space to ensure humanity's survival.",
        release_date=date(2014, 11, 7), runtime_minutes=169,
        series_status="completed",
        creators=[SeedCreator("Christopher Nolan", "director"), SeedCreator("Hans Zimmer", "composer"),
                  SeedCreator("Kip Thorne", "consultant")],
        characters=[SeedCharacter("Cooper", "main"), SeedCharacter("Murph", "supporting"),
                    SeedCharacter("Dr. Brand", "supporting")],
        tags=["sci-fi", "drama", "space", "time travel"],
        editions=[
            SeedEdition(title="IMAX Blu-ray", fmt="Blu-ray", publisher="Paramount", release_date=date(2015, 3, 31),
                        region="US", subtitle="The IMAX Experience",
                        variants=[SeedVariant(name="IMAX Edition", variant_type="physical", cover_price_cents=2999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.movie, franchise="Mad Max", publisher="Warner Bros.",
        series="Mad Max", slug="mad-max",
        volume="Mad Max", volume_number=1, start_year=1979,
        item_number="4", title="Mad Max: Fury Road",
        synopsis="In a post-apocalyptic wasteland, Max teams up with Furiosa to escape a tyrannical warlord.",
        release_date=date(2015, 5, 15), runtime_minutes=120,
        creators=[SeedCreator("George Miller", "director"), SeedCreator("Tom Holkenborg", "composer")],
        characters=[SeedCharacter("Max Rockatansky", "main"), SeedCharacter("Furiosa", "main"),
                    SeedCharacter("Immortan Joe", "antagonist")],
        tags=["action", "post-apocalyptic", "chase"],
        editions=[
            SeedEdition(title="Black & Chrome Edition", fmt="Blu-ray", publisher="Warner Bros.", release_date=date(2016, 12, 6),
                        region="US", subtitle="Black & Chrome",
                        variants=[SeedVariant(name="B&W Blu-ray", variant_type="physical")]),
            SeedEdition(title="Standard Blu-ray", fmt="Blu-ray", publisher="Warner Bros.", release_date=date(2015, 9, 1),
                        variants=[SeedVariant(name="Blu-ray", variant_type="physical")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.movie, franchise="Alien", publisher="20th Century Fox",
        series="Alien", slug="alien",
        volume="Alien", volume_number=1, start_year=1979,
        item_number="1", title="Alien",
        synopsis="The crew of a commercial spacecraft encounters a deadly lifeform after investigating a distress signal.",
        release_date=date(1979, 5, 25), runtime_minutes=117,
        creators=[SeedCreator("Ridley Scott", "director"), SeedCreator("Jerry Goldsmith", "composer"),
                  SeedCreator("Dan O'Bannon", "writer")],
        characters=[SeedCharacter("Ellen Ripley", "main"), SeedCharacter("Xenomorph", "antagonist"),
                    SeedCharacter("Dallas", "supporting")],
        story_arcs=["Xenomorph Saga"],
        tags=["sci-fi", "horror", "survival"],
    ),
    SeedEntry(
        kind=ItemKind.movie, franchise="Alien", publisher="20th Century Fox",
        series="Alien", slug="alien",
        volume="Alien", volume_number=1, start_year=1979,
        item_number="2", title="Aliens",
        synopsis="Ripley returns to the planet where her crew encountered the hostile alien creature.",
        release_date=date(1986, 7, 18), runtime_minutes=137,
        creators=[SeedCreator("James Cameron", "director"), SeedCreator("James Horner", "composer")],
        characters=[SeedCharacter("Ellen Ripley", "main"), SeedCharacter("Newt", "supporting"),
                    SeedCharacter("Xenomorph Queen", "antagonist")],
        story_arcs=["Xenomorph Saga"],
        tags=["sci-fi", "action", "horror"],
    ),
    SeedEntry(
        kind=ItemKind.movie, franchise="The Matrix", publisher="Warner Bros.",
        series="The Matrix", slug="the-matrix",
        volume="The Matrix", volume_number=1, start_year=1999,
        item_number="1", title="The Matrix",
        synopsis="A computer hacker learns about the true nature of reality and his role in the war against its controllers.",
        release_date=date(1999, 3, 31), runtime_minutes=136,
        creators=[SeedCreator("The Wachowskis", "director"), SeedCreator("Don Davis", "composer"),
                  SeedCreator("Keanu Reeves", "actor")],
        characters=[SeedCharacter("Neo", "main"), SeedCharacter("Morpheus", "supporting"),
                    SeedCharacter("Agent Smith", "antagonist"), SeedCharacter("Trinity", "supporting")],
        tags=["sci-fi", "action", "cyberpunk", "philosophy"],
        editions=[
            SeedEdition(title="DVD", fmt="DVD", publisher="Warner Bros.", release_date=date(1999, 9, 21),
                        region="US", age_rating="R",
                        variants=[SeedVariant(name="DVD", variant_type="physical", cover_price_cents=1499, currency="USD")]),
            SeedEdition(title="4K UHD", fmt="4K UHD", publisher="Warner Bros.", release_date=date(2018, 5, 22),
                        region="US", age_rating="R", catalog_number="WB-MATRIX-4K",
                        variants=[SeedVariant(name="4K UHD", variant_type="physical", cover_price_cents=2999, currency="USD")]),
        ],
    ),
]

# ===================================================================
#  TV SHOWS (10)
# ===================================================================
SEED_TV = [
    SeedEntry(
        kind=ItemKind.tv, franchise="Breaking Bad", publisher="AMC",
        series="Breaking Bad", slug="breaking-bad",
        volume="Breaking Bad", volume_number=1, start_year=2008,
        item_number="1", title="Breaking Bad", title_extension="Season 1",
        synopsis="A high school chemistry teacher turned methamphetamine manufacturer partners with a former student.",
        release_date=date(2008, 1, 20), runtime_minutes=49, season_number=1,
        series_status="completed", series_country="US",
        creators=[SeedCreator("Vince Gilligan", "creator"), SeedCreator("Bryan Cranston", "actor"),
                  SeedCreator("Aaron Paul", "actor")],
        characters=[SeedCharacter("Walter White", "main"), SeedCharacter("Jesse Pinkman", "main"),
                    SeedCharacter("Hank Schrader", "supporting")],
        story_arcs=["Heisenberg's Rise"],
        tags=["drama", "crime", "thriller"],
        editions=[
            SeedEdition(title="Complete Series Blu-ray", fmt="Blu-ray", publisher="Sony", release_date=date(2014, 11, 25),
                        region="US", age_rating="TV-MA", series_group="Breaking Bad Universe",
                        variants=[SeedVariant(name="Barrel Set", variant_type="physical", cover_price_cents=7999, currency="USD",
                                             description="Special barrel-shaped collector packaging")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.tv, franchise="Breaking Bad", publisher="AMC",
        series="Better Call Saul", slug="better-call-saul",
        volume="Better Call Saul", volume_number=1, start_year=2015,
        item_number="1", title="Better Call Saul", title_extension="Season 1",
        synopsis="The transformation of Jimmy McGill into Saul Goodman, the morally challenged lawyer.",
        release_date=date(2015, 2, 8), runtime_minutes=53, season_number=1,
        series_status="completed", series_country="US",
        creators=[SeedCreator("Vince Gilligan", "creator"), SeedCreator("Peter Gould", "creator"),
                  SeedCreator("Bob Odenkirk", "actor")],
        characters=[SeedCharacter("Jimmy McGill", "main"), SeedCharacter("Kim Wexler", "main"),
                    SeedCharacter("Mike Ehrmantraut", "supporting")],
        story_arcs=["Heisenberg's Rise"],
        tags=["drama", "crime", "legal"],
    ),
    SeedEntry(
        kind=ItemKind.tv, franchise="The Wire", publisher="HBO",
        series="The Wire", slug="the-wire",
        volume="The Wire", volume_number=1, start_year=2002,
        item_number="1", title="The Wire", title_extension="Season 1",
        synopsis="Examines the Baltimore drug scene through the eyes of law enforcers and drug dealers.",
        release_date=date(2002, 6, 2), runtime_minutes=60, season_number=1,
        series_status="completed",
        creators=[SeedCreator("David Simon", "creator"), SeedCreator("Ed Burns", "creator"),
                  SeedCreator("Dominic West", "actor")],
        characters=[SeedCharacter("Jimmy McNulty", "main"), SeedCharacter("Omar Little", "supporting"),
                    SeedCharacter("Avon Barksdale", "antagonist")],
        tags=["drama", "crime", "social commentary"],
        editions=[
            SeedEdition(title="Complete Series DVD", fmt="DVD", publisher="HBO", release_date=date(2011, 6, 7),
                        region="US", age_rating="TV-MA",
                        variants=[SeedVariant(name="DVD Box Set", variant_type="physical")]),
            SeedEdition(title="Complete Series Blu-ray", fmt="Blu-ray", publisher="HBO", release_date=date(2015, 6, 2),
                        region="US", subtitle="Remastered in HD",
                        variants=[SeedVariant(name="Remastered Blu-ray", variant_type="physical", cover_price_cents=5999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.tv, franchise="Chernobyl", publisher="HBO",
        series="Chernobyl", slug="chernobyl",
        volume="Chernobyl", volume_number=1, start_year=2019,
        item_number="1", title="Chernobyl",
        synopsis="A dramatization of the 1986 nuclear accident and the unprecedented cleanup efforts that followed.",
        release_date=date(2019, 5, 6), runtime_minutes=65, season_number=1,
        series_status="completed", series_country="GB",
        creators=[SeedCreator("Craig Mazin", "creator"), SeedCreator("Jared Harris", "actor"),
                  SeedCreator("Stellan Skarsgård", "actor")],
        characters=[SeedCharacter("Valery Legasov", "main"), SeedCharacter("Boris Shcherbina", "main"),
                    SeedCharacter("Ulana Khomyuk", "supporting")],
        tags=["drama", "historical", "miniseries", "disaster"],
    ),
    SeedEntry(
        kind=ItemKind.tv, franchise="The Sopranos", publisher="HBO",
        series="The Sopranos", slug="the-sopranos",
        volume="The Sopranos", volume_number=1, start_year=1999,
        item_number="1", title="The Sopranos", title_extension="Season 1",
        synopsis="New Jersey mob boss Tony Soprano deals with personal and professional issues in his family.",
        release_date=date(1999, 1, 10), runtime_minutes=55, season_number=1,
        series_status="completed",
        creators=[SeedCreator("David Chase", "creator"), SeedCreator("James Gandolfini", "actor")],
        characters=[SeedCharacter("Tony Soprano", "main"), SeedCharacter("Carmela Soprano", "supporting"),
                    SeedCharacter("Christopher Moltisanti", "supporting")],
        tags=["drama", "crime", "mafia", "psychology"],
        editions=[
            SeedEdition(title="Complete Series Blu-ray", fmt="Blu-ray", publisher="HBO", release_date=date(2014, 11, 18),
                        region="US", age_rating="TV-MA", catalog_number="HBO-SOPRANOS-BLU",
                        variants=[SeedVariant(name="Complete Blu-ray", variant_type="physical", cover_price_cents=8999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.tv, franchise="True Detective", publisher="HBO",
        series="True Detective", slug="true-detective",
        volume="True Detective", volume_number=1, start_year=2014,
        item_number="1", title="True Detective", title_extension="Season 1",
        synopsis="Two detectives trace a Louisiana serial murder case across seventeen years.",
        release_date=date(2014, 1, 12), runtime_minutes=58, season_number=1,
        series_status="ongoing",
        creators=[SeedCreator("Nic Pizzolatto", "creator"), SeedCreator("Matthew McConaughey", "actor"),
                  SeedCreator("Woody Harrelson", "actor")],
        characters=[SeedCharacter("Rust Cohle", "main"), SeedCharacter("Marty Hart", "main")],
        tags=["drama", "crime", "mystery", "anthology"],
    ),
    SeedEntry(
        kind=ItemKind.tv, franchise="Band of Brothers", publisher="HBO",
        series="Band of Brothers", slug="band-of-brothers",
        volume="Band of Brothers", volume_number=1, start_year=2001,
        item_number="1", title="Band of Brothers",
        synopsis="The story of Easy Company during World War II from their training to V-J Day.",
        release_date=date(2001, 9, 9), runtime_minutes=70,
        series_status="completed",
        creators=[SeedCreator("Steven Spielberg", "executive producer"), SeedCreator("Tom Hanks", "executive producer")],
        characters=[SeedCharacter("Richard Winters", "main"), SeedCharacter("Lewis Nixon", "supporting"),
                    SeedCharacter("Ronald Speirs", "supporting")],
        story_arcs=["Easy Company's War"],
        tags=["war", "historical", "drama", "miniseries"],
        editions=[
            SeedEdition(title="Blu-ray", fmt="Blu-ray", publisher="HBO", release_date=date(2008, 11, 11),
                        region="US", age_rating="TV-MA",
                        variants=[SeedVariant(name="Blu-ray Box", variant_type="physical")]),
            SeedEdition(title="4K UHD", fmt="4K UHD", publisher="Warner Bros.", release_date=date(2023, 6, 6),
                        region="US", subtitle="Remastered in 4K",
                        variants=[SeedVariant(name="4K UHD", variant_type="physical", cover_price_cents=5999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.tv, franchise="Dark", publisher="Netflix",
        series="Dark", slug="dark-tv",
        volume="Dark", volume_number=1, start_year=2017,
        item_number="1", title="Dark", title_extension="Season 1",
        synopsis="A missing child triggers events that unravel the secrets of four interconnected families.",
        release_date=date(2017, 12, 1), runtime_minutes=52, season_number=1,
        series_original_title="Dark", series_status="completed", series_language="de", series_country="DE",
        creators=[SeedCreator("Baran bo Odar", "creator"), SeedCreator("Jantje Friese", "creator")],
        characters=[SeedCharacter("Jonas Kahnwald", "main"), SeedCharacter("Martha Nielsen", "main"),
                    SeedCharacter("Claudia Tiedemann", "supporting")],
        story_arcs=["Winden Time Loop"],
        tags=["sci-fi", "mystery", "time travel"],
    ),
    SeedEntry(
        kind=ItemKind.tv, franchise="Fargo", publisher="FX",
        series="Fargo", slug="fargo-tv",
        volume="Fargo", volume_number=1, start_year=2014,
        item_number="1", title="Fargo", title_extension="Season 1",
        synopsis="An anthology series exploring deception, crime, and intrigue across the American Midwest.",
        release_date=date(2014, 4, 15), runtime_minutes=53, season_number=1,
        series_status="ongoing",
        creators=[SeedCreator("Noah Hawley", "creator"), SeedCreator("Billy Bob Thornton", "actor"),
                  SeedCreator("Martin Freeman", "actor")],
        characters=[SeedCharacter("Lorne Malvo", "antagonist"), SeedCharacter("Lester Nygaard", "main"),
                    SeedCharacter("Molly Solverson", "main")],
        tags=["crime", "dark comedy", "anthology", "thriller"],
    ),
    SeedEntry(
        kind=ItemKind.tv, franchise="Fleabag", publisher="BBC / Amazon",
        series="Fleabag", slug="fleabag",
        volume="Fleabag", volume_number=1, start_year=2016,
        item_number="1", title="Fleabag", title_extension="Season 1",
        synopsis="A dry-witted woman navigates life in London while dealing with loss and complicated relationships.",
        release_date=date(2016, 7, 21), runtime_minutes=27, season_number=1,
        series_status="completed", series_country="GB",
        creators=[SeedCreator("Phoebe Waller-Bridge", "creator"), SeedCreator("Phoebe Waller-Bridge", "actor")],
        characters=[SeedCharacter("Fleabag", "main"), SeedCharacter("Claire", "supporting"),
                    SeedCharacter("The Priest", "supporting")],
        tags=["comedy", "drama", "fourth wall"],
    ),
]

# ANIME and MANGA seed data can be added explicitly when needed.

# ===================================================================
#  BOOKS (10)
# ===================================================================
SEED_BOOKS = [
    SeedEntry(
        kind=ItemKind.book, franchise="Dune", publisher="Chilton Books",
        series="Dune", slug="dune",
        volume="Dune", volume_number=1, start_year=1965,
        item_number="1", title="Dune",
        synopsis="A noble family becomes embroiled in a war for control of the most valuable substance in the universe.",
        release_date=date(1965, 8, 1), page_count=412,
        series_status="completed", series_country="US",
        creators=[SeedCreator("Frank Herbert", "author")],
        characters=[SeedCharacter("Paul Atreides", "main"), SeedCharacter("Duke Leto Atreides", "supporting"),
                    SeedCharacter("Baron Harkonnen", "antagonist"), SeedCharacter("Lady Jessica", "supporting")],
        story_arcs=["Arrakis Saga"],
        tags=["sci-fi", "politics", "ecology", "space opera"],
        editions=[
            SeedEdition(title="Mass Market Paperback", fmt="Paperback", publisher="Ace Books", release_date=date(1990, 9, 1),
                        isbn="9780441172719", age_rating="Adult", release_status="released", imprint="Ace",
                        variants=[SeedVariant(name="Paperback", variant_type="physical", cover_price_cents=999, currency="USD",
                                             isbn="9780441172719")]),
            SeedEdition(title="Hardcover", fmt="Hardcover", publisher="Chilton Books", release_date=date(1965, 8, 1),
                        release_status="released",
                        variants=[SeedVariant(name="Hardcover", variant_type="physical",
                                             description="Original 1965 first edition hardcover")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.book, franchise="Dune", publisher="Chilton Books",
        series="Dune", slug="dune",
        volume="Dune", volume_number=1, start_year=1965,
        item_number="2", title="Dune Messiah",
        synopsis="Paul Atreides faces a conspiracy to overthrow him twelve years after becoming Emperor.",
        release_date=date(1969, 10, 1), page_count=256,
        creators=[SeedCreator("Frank Herbert", "author")],
        characters=[SeedCharacter("Paul Atreides", "main"), SeedCharacter("Alia Atreides", "supporting"),
                    SeedCharacter("Chani", "supporting")],
        story_arcs=["Arrakis Saga"],
        tags=["sci-fi", "politics", "religion"],
    ),
    SeedEntry(
        kind=ItemKind.book, franchise="Foundation", publisher="Gnome Press",
        series="Foundation", slug="foundation",
        volume="Foundation", volume_number=1, start_year=1951,
        item_number="1", title="Foundation",
        synopsis="A mathematician predicts the fall of the Galactic Empire and creates a plan to preserve knowledge.",
        release_date=date(1951, 5, 1), page_count=244,
        series_status="completed",
        creators=[SeedCreator("Isaac Asimov", "author")],
        characters=[SeedCharacter("Hari Seldon", "main"), SeedCharacter("Salvor Hardin", "main")],
        tags=["sci-fi", "psychohistory", "galactic empire"],
        editions=[
            SeedEdition(title="Paperback", fmt="Paperback", publisher="Bantam Spectra", release_date=date(2004, 6, 1),
                        isbn="9780553293357", imprint="Spectra",
                        variants=[SeedVariant(name="Paperback", variant_type="physical", cover_price_cents=899, currency="USD",
                                             isbn="9780553293357")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.book, franchise="1984", publisher="Secker & Warburg",
        series="1984", slug="nineteen-eighty-four",
        volume="1984", volume_number=1, start_year=1949,
        item_number="1", title="1984",
        synopsis="In a totalitarian future, a man rebels against the oppressive government that controls every aspect of life.",
        release_date=date(1949, 6, 8), page_count=328,
        series_status="completed", series_country="GB",
        creators=[SeedCreator("George Orwell", "author")],
        characters=[SeedCharacter("Winston Smith", "main"), SeedCharacter("Big Brother", "antagonist"),
                    SeedCharacter("Julia", "supporting"), SeedCharacter("O'Brien", "antagonist")],
        tags=["dystopia", "political fiction", "surveillance", "classic"],
        editions=[
            SeedEdition(title="Centennial Edition", fmt="Hardcover", publisher="Plume", release_date=date(2003, 5, 6),
                        release_status="released",
                        variants=[SeedVariant(name="Centennial HC", variant_type="physical",
                                             description="Special centennial anniversary edition")]),
            SeedEdition(title="Penguin Paperback", fmt="Paperback", publisher="Penguin", release_date=date(1961, 1, 1),
                        imprint="Penguin Classics",
                        variants=[SeedVariant(name="Penguin PB", variant_type="physical", cover_price_cents=1299, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.book, franchise="Neuromancer", publisher="Ace Books",
        series="Sprawl Trilogy", slug="sprawl-trilogy",
        volume="Sprawl Trilogy", volume_number=1, start_year=1984,
        item_number="1", title="Neuromancer",
        synopsis="A washed-up computer hacker is hired for one last job in a world of artificial intelligence and mega-corporations.",
        release_date=date(1984, 7, 1), page_count=271,
        series_status="completed",
        creators=[SeedCreator("William Gibson", "author")],
        characters=[SeedCharacter("Case", "main"), SeedCharacter("Molly Millions", "supporting"),
                    SeedCharacter("Wintermute", "antagonist")],
        tags=["cyberpunk", "sci-fi", "AI", "hacking"],
    ),
    SeedEntry(
        kind=ItemKind.book, franchise="Hitchhiker's Guide", publisher="Pan Books",
        series="The Hitchhiker's Guide to the Galaxy", slug="hitchhikers-guide",
        volume="The Hitchhiker's Guide to the Galaxy", volume_number=1, start_year=1979,
        item_number="1", title="The Hitchhiker's Guide to the Galaxy",
        synopsis="Seconds before Earth is destroyed, Arthur Dent is saved by his friend Ford Prefect, a researcher for the Guide.",
        release_date=date(1979, 10, 12), page_count=180,
        series_status="completed", series_country="GB",
        creators=[SeedCreator("Douglas Adams", "author")],
        characters=[SeedCharacter("Arthur Dent", "main"), SeedCharacter("Ford Prefect", "main"),
                    SeedCharacter("Zaphod Beeblebrox", "supporting"), SeedCharacter("Marvin", "supporting")],
        tags=["sci-fi", "comedy", "satire", "absurdist"],
        editions=[
            SeedEdition(title="Illustrated Edition", fmt="Hardcover", publisher="Del Rey", release_date=date(2007, 4, 10),
                        isbn="9780345453747", subtitle="The Illustrated Edition",
                        variants=[SeedVariant(name="Illustrated HC", variant_type="physical", cover_price_cents=2500, currency="USD",
                                             isbn="9780345453747")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.book, franchise="Lord of the Rings", publisher="George Allen & Unwin",
        series="The Lord of the Rings", slug="lord-of-the-rings",
        volume="The Lord of the Rings", volume_number=1, start_year=1954,
        item_number="1", title="The Fellowship of the Ring",
        synopsis="A hobbit inherits a ring of power and begins a journey to destroy it.",
        release_date=date(1954, 7, 29), page_count=423,
        series_status="completed", series_country="GB",
        creators=[SeedCreator("J.R.R. Tolkien", "author")],
        characters=[SeedCharacter("Frodo Baggins", "main"), SeedCharacter("Gandalf", "supporting"),
                    SeedCharacter("Aragorn", "supporting"), SeedCharacter("Sauron", "antagonist")],
        story_arcs=["War of the Ring"],
        tags=["fantasy", "epic", "quest", "classic"],
    ),
    SeedEntry(
        kind=ItemKind.book, franchise="Lord of the Rings", publisher="George Allen & Unwin",
        series="The Lord of the Rings", slug="lord-of-the-rings",
        volume="The Lord of the Rings", volume_number=1, start_year=1954,
        item_number="2", title="The Two Towers",
        synopsis="The fellowship is broken as war spreads and the quest to destroy the ring continues.",
        release_date=date(1954, 11, 11), page_count=352,
        creators=[SeedCreator("J.R.R. Tolkien", "author")],
        characters=[SeedCharacter("Frodo Baggins", "main"), SeedCharacter("Samwise Gamgee", "main"),
                    SeedCharacter("Gollum", "antagonist"), SeedCharacter("Aragorn", "supporting")],
        story_arcs=["War of the Ring"],
        tags=["fantasy", "epic", "war"],
    ),
    SeedEntry(
        kind=ItemKind.book, franchise="Lord of the Rings", publisher="George Allen & Unwin",
        series="The Lord of the Rings", slug="lord-of-the-rings",
        volume="The Lord of the Rings", volume_number=1, start_year=1954,
        item_number="3", title="The Return of the King",
        synopsis="The final battle for Middle-earth begins while Frodo approaches Mount Doom.",
        release_date=date(1955, 10, 20), page_count=416,
        creators=[SeedCreator("J.R.R. Tolkien", "author")],
        characters=[SeedCharacter("Frodo Baggins", "main"), SeedCharacter("Aragorn", "main"),
                    SeedCharacter("Sauron", "antagonist")],
        story_arcs=["War of the Ring"],
        tags=["fantasy", "epic", "coronation"],
    ),
    SeedEntry(
        kind=ItemKind.book, franchise="The Martian", publisher="Crown Publishing",
        series="The Martian", slug="the-martian",
        volume="The Martian", volume_number=1, start_year=2011,
        item_number="1", title="The Martian",
        synopsis="An astronaut must rely on his ingenuity to survive alone on Mars after being presumed dead.",
        release_date=date(2011, 3, 1), page_count=369,
        series_status="completed",
        creators=[SeedCreator("Andy Weir", "author")],
        characters=[SeedCharacter("Mark Watney", "main"), SeedCharacter("Melissa Lewis", "supporting")],
        tags=["sci-fi", "survival", "hard science", "humor"],
        editions=[
            SeedEdition(title="Hardcover", fmt="Hardcover", publisher="Crown", release_date=date(2014, 2, 11),
                        isbn="9780804139021", release_status="released",
                        variants=[SeedVariant(name="Hardcover", variant_type="physical", cover_price_cents=2400, currency="USD",
                                             isbn="9780804139021")]),
            SeedEdition(title="Audiobook", fmt="Audiobook", publisher="Podium Audio", release_date=date(2014, 3, 22),
                        catalog_number="PODIUM-MARTIAN-01",
                        variants=[SeedVariant(name="Audiobook", variant_type="digital",
                                             description="Narrated by R.C. Bray")]),
        ],
    ),
]

# MANGA seed data removed (merged into comics)

# ===================================================================
#  MUSIC (10)
# ===================================================================
SEED_MUSIC = [
    SeedEntry(
        kind=ItemKind.music, franchise="Radiohead", publisher="Parlophone",
        series="Radiohead", slug="radiohead",
        volume="Radiohead", volume_number=1, start_year=1993,
        item_number="3", title="OK Computer",
        synopsis="Radiohead's seminal third album exploring themes of modern alienation.",
        release_date=date(1997, 5, 21),
        series_status="ongoing", series_country="GB",
        metadata_json={"track_count": 12},
        creators=[SeedCreator("Thom Yorke", "vocalist"), SeedCreator("Jonny Greenwood", "guitarist"),
                  SeedCreator("Nigel Godrich", "producer")],
        tags=["alternative rock", "art rock", "electronic"],
        editions=[
            SeedEdition(title="CD", fmt="CD", publisher="Parlophone", release_date=date(1997, 6, 16),
                        region="US", catalog_number="CDNODATA 02", release_status="released",
                        variants=[SeedVariant(name="CD", variant_type="physical", cover_price_cents=1399, currency="USD",
                                             barcode="724385522925")]),
            SeedEdition(title="Vinyl LP", fmt="Vinyl", publisher="Parlophone", release_date=date(1997, 6, 16),
                        region="US",
                        variants=[SeedVariant(name="LP", variant_type="physical", cover_price_cents=2499, currency="USD")]),
            SeedEdition(title="OKNOTOK Deluxe", fmt="Vinyl Box Set", publisher="XL Recordings", release_date=date(2017, 6, 23),
                        subtitle="OKNOTOK 1997-2017", catalog_number="XLLP868BOX",
                        variants=[SeedVariant(name="Deluxe Box", variant_type="physical", cover_price_cents=12999, currency="USD",
                                             description="3xLP + cassette + art book + sketchbook")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.music, franchise="Radiohead", publisher="XL Recordings",
        series="Radiohead", slug="radiohead",
        volume="Radiohead", volume_number=1, start_year=1993,
        item_number="4", title="Kid A",
        synopsis="Radiohead's radical departure into electronic and experimental territory.",
        release_date=date(2000, 10, 2),
        metadata_json={"track_count": 10},
        creators=[SeedCreator("Thom Yorke", "vocalist"), SeedCreator("Nigel Godrich", "producer")],
        tags=["electronic", "experimental", "art rock"],
        editions=[
            SeedEdition(title="CD", fmt="CD", publisher="Parlophone", release_date=date(2000, 10, 2),
                        variants=[SeedVariant(name="CD", variant_type="physical")]),
            SeedEdition(title="Vinyl", fmt="Vinyl", publisher="XL Recordings", release_date=date(2000, 10, 2),
                        variants=[SeedVariant(name="LP", variant_type="physical", cover_price_cents=2999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.music, franchise="Pink Floyd", publisher="Harvest",
        series="Pink Floyd", slug="pink-floyd",
        volume="Pink Floyd", volume_number=1, start_year=1967,
        item_number="8", title="The Dark Side of the Moon",
        synopsis="A concept album exploring conflict, greed, time, death, and mental illness.",
        release_date=date(1973, 3, 1),
        series_status="completed", series_country="GB",
        metadata_json={"track_count": 10},
        creators=[SeedCreator("Roger Waters", "bassist"), SeedCreator("David Gilmour", "guitarist"),
                  SeedCreator("Alan Parsons", "engineer")],
        story_arcs=["The Human Condition"],
        tags=["progressive rock", "art rock", "concept album"],
        editions=[
            SeedEdition(title="Vinyl LP", fmt="Vinyl", publisher="Harvest", release_date=date(1973, 3, 1),
                        region="GB", catalog_number="SHVL 804",
                        variants=[SeedVariant(name="Original LP", variant_type="physical",
                                             description="Original UK pressing with posters and stickers")]),
            SeedEdition(title="SACD", fmt="SACD", publisher="EMI", release_date=date(2003, 3, 24),
                        subtitle="30th Anniversary Edition",
                        variants=[SeedVariant(name="SACD", variant_type="physical", cover_price_cents=2499, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.music, franchise="Kendrick Lamar", publisher="Top Dawg / Interscope",
        series="Kendrick Lamar", slug="kendrick-lamar",
        volume="Kendrick Lamar", volume_number=1, start_year=2011,
        item_number="2", title="good kid, m.A.A.d city",
        synopsis="A concept album following Kendrick's experiences growing up in Compton.",
        release_date=date(2012, 10, 22),
        series_status="ongoing", series_country="US",
        metadata_json={"track_count": 12},
        creators=[SeedCreator("Kendrick Lamar", "artist"), SeedCreator("Dr. Dre", "producer"),
                  SeedCreator("Pharrell Williams", "producer")],
        story_arcs=["Compton Chronicles"],
        tags=["hip hop", "concept album", "west coast"],
        editions=[
            SeedEdition(title="Deluxe CD", fmt="CD", publisher="Interscope", release_date=date(2012, 10, 22),
                        imprint="Top Dawg Entertainment", catalog_number="B001792502",
                        variants=[SeedVariant(name="Deluxe CD", variant_type="physical", cover_price_cents=1399, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.music, franchise="Kendrick Lamar", publisher="Top Dawg / Interscope",
        series="Kendrick Lamar", slug="kendrick-lamar",
        volume="Kendrick Lamar", volume_number=1, start_year=2011,
        item_number="3", title="To Pimp a Butterfly",
        synopsis="An exploration of African-American culture, politics, and Kendrick's own struggles with fame.",
        release_date=date(2015, 3, 15),
        metadata_json={"track_count": 16},
        creators=[SeedCreator("Kendrick Lamar", "artist"), SeedCreator("Flying Lotus", "producer"),
                  SeedCreator("Thundercat", "bassist")],
        tags=["hip hop", "funk", "jazz rap", "spoken word"],
    ),
    SeedEntry(
        kind=ItemKind.music, franchise="Daft Punk", publisher="Virgin",
        series="Daft Punk", slug="daft-punk",
        volume="Daft Punk", volume_number=1, start_year=1997,
        item_number="3", title="Discovery",
        synopsis="A landmark electronic album blending house music with pop, funk, and disco influences.",
        release_date=date(2001, 3, 12),
        series_status="completed", series_country="FR", series_language="fr",
        metadata_json={"track_count": 14},
        creators=[SeedCreator("Thomas Bangalter", "artist"), SeedCreator("Guy-Manuel de Homem-Christo", "artist")],
        tags=["electronic", "house", "french touch", "disco"],
        editions=[
            SeedEdition(title="Vinyl LP", fmt="Vinyl", publisher="Virgin", release_date=date(2001, 3, 12),
                        region="FR",
                        variants=[SeedVariant(name="2xLP", variant_type="physical", cover_price_cents=2999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.music, franchise="Miles Davis", publisher="Columbia",
        series="Miles Davis", slug="miles-davis",
        volume="Miles Davis", volume_number=1, start_year=1951,
        item_number="5", title="Kind of Blue",
        synopsis="The best-selling jazz album of all time, a masterclass in modal jazz.",
        release_date=date(1959, 8, 17),
        series_status="completed", series_country="US",
        metadata_json={"track_count": 5},
        creators=[SeedCreator("Miles Davis", "artist"), SeedCreator("John Coltrane", "saxophonist"),
                  SeedCreator("Bill Evans", "pianist")],
        tags=["jazz", "modal jazz", "cool jazz"],
        editions=[
            SeedEdition(title="Original LP", fmt="Vinyl", publisher="Columbia", release_date=date(1959, 8, 17),
                        catalog_number="CL 1355",
                        variants=[SeedVariant(name="Mono LP", variant_type="physical",
                                             description="Original Columbia mono pressing")]),
            SeedEdition(title="Legacy Edition CD", fmt="CD", publisher="Columbia/Legacy", release_date=date(2009, 9, 29),
                        subtitle="50th Anniversary Legacy Edition", catalog_number="88697-53891-2",
                        variants=[SeedVariant(name="2xCD", variant_type="physical", cover_price_cents=1999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.music, franchise="Björk", publisher="One Little Indian",
        series="Björk", slug="bjork",
        volume="Björk", volume_number=1, start_year=1993,
        item_number="3", title="Homogenic",
        synopsis="A dense, emotional album blending electronic beats with orchestral strings.",
        release_date=date(1997, 9, 22),
        series_status="ongoing", series_country="IS", series_language="is",
        metadata_json={"track_count": 10},
        creators=[SeedCreator("Björk", "artist"), SeedCreator("Mark Bell", "producer"),
                  SeedCreator("Eumir Deodato", "orchestrator")],
        tags=["electronic", "experimental", "trip hop", "orchestral"],
    ),
    SeedEntry(
        kind=ItemKind.music, franchise="Massive Attack", publisher="Wild Bunch / Virgin",
        series="Massive Attack", slug="massive-attack",
        volume="Massive Attack", volume_number=1, start_year=1991,
        item_number="3", title="Mezzanine",
        synopsis="A dark, brooding trip-hop masterpiece featuring Teardrop and Angel.",
        release_date=date(1998, 4, 20),
        series_status="ongoing", series_country="GB",
        metadata_json={"track_count": 11},
        creators=[SeedCreator("Robert Del Naja", "artist"), SeedCreator("Grant Marshall", "artist"),
                  SeedCreator("Neil Davidge", "producer")],
        tags=["trip hop", "electronic", "dark ambient"],
        editions=[
            SeedEdition(title="Vinyl LP", fmt="Vinyl", publisher="Virgin", release_date=date(1998, 4, 20),
                        region="GB",
                        variants=[SeedVariant(name="2xLP", variant_type="physical")]),
            SeedEdition(title="Deluxe Remaster CD", fmt="CD", publisher="Virgin", release_date=date(2019, 2, 1),
                        subtitle="20th Anniversary Deluxe Remaster", catalog_number="V2940DX",
                        variants=[SeedVariant(name="2xCD Deluxe", variant_type="physical", cover_price_cents=1699, currency="USD",
                                             description="Remastered with bonus disc of Mad Professor dub versions")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.music, franchise="Portishead", publisher="Go! Beat",
        series="Portishead", slug="portishead",
        volume="Portishead", volume_number=1, start_year=1994,
        item_number="1", title="Dummy",
        synopsis="The definitive trip-hop debut, fusing hip-hop beats with cinematic string arrangements.",
        release_date=date(1994, 8, 22),
        series_status="ongoing", series_country="GB",
        metadata_json={"track_count": 11},
        creators=[SeedCreator("Beth Gibbons", "vocalist"), SeedCreator("Geoff Barrow", "producer"),
                  SeedCreator("Adrian Utley", "guitarist")],
        tags=["trip hop", "downtempo", "cinematic"],
    ),
]

# ===================================================================
#  GAMES (10)
# ===================================================================
SEED_GAMES = [
    SeedEntry(
        kind=ItemKind.game, franchise="The Witcher", publisher="CD Projekt Red",
        series="The Witcher", slug="the-witcher",
        volume="The Witcher", volume_number=1, start_year=2007,
        item_number="3", title="The Witcher 3: Wild Hunt",
        synopsis="Geralt of Rivia sets out to find his adopted daughter in a war-torn fantasy world.",
        release_date=date(2015, 5, 19), metadata_json={"platforms": ["PC", "PS4", "Xbox One", "Switch"]},
        series_status="completed",
        creators=[SeedCreator("CD Projekt Red", "developer"), SeedCreator("Marcin Przybyłowicz", "composer"),
                  SeedCreator("Konrad Tomaszkiewicz", "director")],
        characters=[SeedCharacter("Geralt of Rivia", "main"), SeedCharacter("Ciri", "main"),
                    SeedCharacter("Yennefer", "supporting"), SeedCharacter("The Wild Hunt", "antagonist")],
        story_arcs=["Wild Hunt Pursuit"],
        tags=["RPG", "open world", "fantasy", "action"],
        editions=[
            SeedEdition(title="Standard PC", fmt="PC", publisher="CD Projekt Red", release_date=date(2015, 5, 19),
                        age_rating="M", release_status="released",
                        variants=[SeedVariant(name="PC", variant_type="physical", platform="PC",
                                             sku="WITCHER3-PC-STD")]),
            SeedEdition(title="Complete Edition Switch", fmt="Switch", publisher="CD Projekt Red", release_date=date(2019, 10, 15),
                        subtitle="Complete Edition",
                        variants=[SeedVariant(name="Switch", variant_type="physical", platform="Switch", cover_price_cents=5999, currency="USD")]),
            SeedEdition(title="GOTY PS4", fmt="PS4", publisher="CD Projekt Red", release_date=date(2016, 8, 30),
                        subtitle="Game of the Year Edition", age_rating="M",
                        variants=[SeedVariant(name="GOTY PS4", variant_type="physical", platform="PS4", cover_price_cents=4999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.game, franchise="Dark Souls", publisher="FromSoftware",
        series="Dark Souls", slug="dark-souls",
        volume="Dark Souls", volume_number=1, start_year=2011,
        item_number="1", title="Dark Souls",
        synopsis="An action RPG set in a dark fantasy world, known for its difficulty and deep lore.",
        release_date=date(2011, 9, 22), metadata_json={"platforms": ["PC", "PS3", "Xbox 360"]},
        series_status="completed", series_country="JP", series_language="ja",
        creators=[SeedCreator("Hidetaka Miyazaki", "director"), SeedCreator("FromSoftware", "developer"),
                  SeedCreator("Motoi Sakuraba", "composer")],
        characters=[SeedCharacter("Chosen Undead", "main"), SeedCharacter("Solaire", "supporting"),
                    SeedCharacter("Gwyn", "antagonist")],
        story_arcs=["Age of Fire"],
        tags=["RPG", "action", "souls-like", "dark fantasy"],
        editions=[
            SeedEdition(title="Remastered PS4", fmt="PS4", publisher="Bandai Namco", release_date=date(2018, 5, 25),
                        subtitle="Remastered", age_rating="T",
                        variants=[SeedVariant(name="PS4", variant_type="physical", platform="PS4", cover_price_cents=3999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.game, franchise="Dark Souls", publisher="FromSoftware",
        series="Dark Souls", slug="dark-souls",
        volume="Dark Souls", volume_number=1, start_year=2011,
        item_number="3", title="Dark Souls III",
        synopsis="The final entry in the Dark Souls trilogy, featuring faster combat and interconnected worlds.",
        release_date=date(2016, 3, 24), metadata_json={"platforms": ["PC", "PS4", "Xbox One"]},
        creators=[SeedCreator("Hidetaka Miyazaki", "director"), SeedCreator("Yui Tanimura", "co-director")],
        characters=[SeedCharacter("Ashen One", "main"), SeedCharacter("Fire Keeper", "supporting"),
                    SeedCharacter("Soul of Cinder", "antagonist")],
        story_arcs=["Age of Fire"],
        tags=["RPG", "action", "souls-like"],
    ),
    SeedEntry(
        kind=ItemKind.game, franchise="Elden Ring", publisher="FromSoftware",
        series="Elden Ring", slug="elden-ring",
        volume="Elden Ring", volume_number=1, start_year=2022,
        item_number="1", title="Elden Ring",
        synopsis="An open-world action RPG set in the Lands Between, created with George R. R. Martin.",
        release_date=date(2022, 2, 25), metadata_json={"platforms": ["PC", "PS5", "PS4", "Xbox Series", "Xbox One"]},
        series_status="ongoing",
        creators=[SeedCreator("Hidetaka Miyazaki", "director"), SeedCreator("George R.R. Martin", "world builder"),
                  SeedCreator("FromSoftware", "developer")],
        characters=[SeedCharacter("Tarnished", "main"), SeedCharacter("Melina", "supporting"),
                    SeedCharacter("Radahn", "antagonist"), SeedCharacter("Ranni", "supporting")],
        tags=["RPG", "open world", "souls-like", "dark fantasy"],
        editions=[
            SeedEdition(title="Standard PS5", fmt="PS5", publisher="Bandai Namco", release_date=date(2022, 2, 25),
                        age_rating="M", release_status="released",
                        variants=[SeedVariant(name="PS5", variant_type="physical", platform="PS5", cover_price_cents=5999, currency="USD")]),
            SeedEdition(title="Collector's Edition", fmt="PS5", publisher="Bandai Namco", release_date=date(2022, 2, 25),
                        subtitle="Collector's Edition", age_rating="M",
                        variants=[SeedVariant(name="Collector PS5", variant_type="physical", platform="PS5", cover_price_cents=18999, currency="USD",
                                             description="Includes statue, art book, steelbook, and digital soundtrack")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.game, franchise="Hollow Knight", publisher="Team Cherry",
        series="Hollow Knight", slug="hollow-knight",
        volume="Hollow Knight", volume_number=1, start_year=2017,
        item_number="1", title="Hollow Knight",
        synopsis="A 2D metroidvania through a vast underground kingdom of insects and heroes.",
        release_date=date(2017, 2, 24), metadata_json={"platforms": ["PC", "PS4", "Xbox One", "Switch"]},
        series_status="ongoing", series_country="AU",
        creators=[SeedCreator("Team Cherry", "developer"), SeedCreator("Christopher Larkin", "composer")],
        characters=[SeedCharacter("The Knight", "main"), SeedCharacter("Hornet", "supporting"),
                    SeedCharacter("The Hollow Knight", "antagonist"), SeedCharacter("The Radiance", "antagonist")],
        tags=["metroidvania", "indie", "platformer", "atmospheric"],
    ),
    SeedEntry(
        kind=ItemKind.game, franchise="Disco Elysium", publisher="ZA/UM",
        series="Disco Elysium", slug="disco-elysium",
        volume="Disco Elysium", volume_number=1, start_year=2019,
        item_number="1", title="Disco Elysium",
        synopsis="An amnesiac detective solves a murder in a city torn by political conflict.",
        release_date=date(2019, 10, 15), metadata_json={"platforms": ["PC", "PS5", "PS4", "Xbox Series", "Switch"]},
        series_status="completed", series_country="EE",
        creators=[SeedCreator("Robert Kurvitz", "designer"), SeedCreator("ZA/UM", "developer"),
                  SeedCreator("British Sea Power", "composer")],
        characters=[SeedCharacter("Harry Du Bois", "main"), SeedCharacter("Kim Kitsuragi", "supporting"),
                    SeedCharacter("The Deserter", "antagonist")],
        tags=["RPG", "detective", "narrative", "isometric"],
        editions=[
            SeedEdition(title="The Final Cut PC", fmt="PC", publisher="ZA/UM", release_date=date(2021, 3, 30),
                        subtitle="The Final Cut", release_status="released",
                        variants=[SeedVariant(name="PC", variant_type="digital", platform="PC")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.game, franchise="Hades", publisher="Supergiant Games",
        series="Hades", slug="hades",
        volume="Hades", volume_number=1, start_year=2020,
        item_number="1", title="Hades",
        synopsis="Zagreus, prince of the Underworld, tries to escape his father's domain in this roguelike.",
        release_date=date(2020, 9, 17), metadata_json={"platforms": ["PC", "PS5", "PS4", "Xbox Series", "Switch"]},
        series_status="ongoing",
        creators=[SeedCreator("Supergiant Games", "developer"), SeedCreator("Darren Korb", "composer"),
                  SeedCreator("Greg Kasavin", "writer")],
        characters=[SeedCharacter("Zagreus", "main"), SeedCharacter("Hades", "antagonist"),
                    SeedCharacter("Megaera", "supporting"), SeedCharacter("Thanatos", "supporting")],
        tags=["roguelike", "action", "mythology", "indie"],
    ),
    SeedEntry(
        kind=ItemKind.game, franchise="Outer Wilds", publisher="Mobius Digital",
        series="Outer Wilds", slug="outer-wilds",
        volume="Outer Wilds", volume_number=1, start_year=2019,
        item_number="1", title="Outer Wilds",
        synopsis="An astronaut explores a solar system stuck in a time loop, uncovering the secrets of an ancient civilization.",
        release_date=date(2019, 5, 28), metadata_json={"platforms": ["PC", "PS4", "Xbox One"]},
        series_status="completed",
        creators=[SeedCreator("Mobius Digital", "developer"), SeedCreator("Andrew Prahlow", "composer")],
        characters=[SeedCharacter("Hearthian", "main"), SeedCharacter("Solanum", "supporting")],
        tags=["exploration", "puzzle", "time loop", "space"],
    ),
    SeedEntry(
        kind=ItemKind.game, franchise="Baldur's Gate", publisher="Larian Studios",
        series="Baldur's Gate", slug="baldurs-gate",
        volume="Baldur's Gate", volume_number=1, start_year=1998,
        item_number="3", title="Baldur's Gate 3",
        synopsis="A party-based RPG set in the Forgotten Realms, featuring a story of parasitic mind flayers.",
        release_date=date(2023, 8, 3), metadata_json={"platforms": ["PC", "PS5", "Xbox Series"]},
        series_status="ongoing",
        creators=[SeedCreator("Larian Studios", "developer"), SeedCreator("Swen Vincke", "director"),
                  SeedCreator("Borislav Slavov", "composer")],
        characters=[SeedCharacter("Tav", "main"), SeedCharacter("Shadowheart", "supporting"),
                    SeedCharacter("Astarion", "supporting"), SeedCharacter("The Absolute", "antagonist")],
        story_arcs=["Illithid Invasion"],
        tags=["RPG", "turn-based", "D&D", "party-based"],
        editions=[
            SeedEdition(title="Standard PC", fmt="PC", publisher="Larian Studios", release_date=date(2023, 8, 3),
                        release_status="released",
                        variants=[SeedVariant(name="PC", variant_type="digital", platform="PC")]),
            SeedEdition(title="Deluxe PS5", fmt="PS5", publisher="Larian Studios", release_date=date(2023, 9, 6),
                        subtitle="Deluxe Edition", age_rating="M",
                        variants=[SeedVariant(name="Deluxe PS5", variant_type="physical", platform="PS5", cover_price_cents=7999, currency="USD",
                                             description="Includes map poster and sticker sheet")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.game, franchise="Celeste", publisher="Matt Makes Games",
        series="Celeste", slug="celeste",
        volume="Celeste", volume_number=1, start_year=2018,
        item_number="1", title="Celeste",
        synopsis="A young woman named Madeline climbs Celeste Mountain while battling her inner demons.",
        release_date=date(2018, 1, 25), metadata_json={"platforms": ["PC", "PS4", "Xbox One", "Switch"]},
        series_status="completed",
        creators=[SeedCreator("Maddy Thorson", "designer"), SeedCreator("Lena Raine", "composer"),
                  SeedCreator("Noel Berry", "programmer")],
        characters=[SeedCharacter("Madeline", "main"), SeedCharacter("Badeline", "antagonist"),
                    SeedCharacter("Theo", "supporting")],
        tags=["platformer", "indie", "precision", "narrative"],
    ),
]

# ===================================================================
#  BOARD GAMES (10)
# ===================================================================
SEED_BOARDGAMES = [
    SeedEntry(
        kind=ItemKind.boardgame, franchise="Gloomhaven", publisher="Cephalofair Games",
        series="Gloomhaven", slug="gloomhaven",
        volume="Gloomhaven", volume_number=1, start_year=2017,
        item_number="1", title="Gloomhaven",
        synopsis="A cooperative dungeon-crawling board game with a branching narrative and tactical combat.",
        release_date=date(2017, 4, 1),
        series_status="ongoing",
        creators=[SeedCreator("Isaac Childres", "designer")],
        characters=[SeedCharacter("Brute", "main"), SeedCharacter("Spellweaver", "main"),
                    SeedCharacter("Scoundrel", "supporting")],
        tags=["cooperative", "dungeon crawl", "campaign", "tactical"],
        editions=[
            SeedEdition(title="2nd Printing", fmt="Board Game", publisher="Cephalofair Games", release_date=date(2017, 10, 1),
                        age_rating="14+", release_status="released",
                        variants=[SeedVariant(name="Standard", variant_type="physical", cover_price_cents=14000, currency="USD",
                                             description="20+ lb box with 95 scenarios")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.boardgame, franchise="Gloomhaven", publisher="Cephalofair Games",
        series="Gloomhaven", slug="gloomhaven",
        volume="Gloomhaven", volume_number=1, start_year=2017,
        item_number="2", title="Gloomhaven: Jaws of the Lion",
        synopsis="A standalone prequel to Gloomhaven with simplified rules and a built-in tutorial.",
        release_date=date(2020, 6, 18),
        creators=[SeedCreator("Isaac Childres", "designer")],
        characters=[SeedCharacter("Valrath Red Guard", "main"), SeedCharacter("Inox Hatchet", "main"),
                    SeedCharacter("Human Voidwarden", "supporting")],
        tags=["cooperative", "dungeon crawl", "introductory"],
    ),
    SeedEntry(
        kind=ItemKind.boardgame, franchise="Wingspan", publisher="Stonemaier Games",
        series="Wingspan", slug="wingspan",
        volume="Wingspan", volume_number=1, start_year=2019,
        item_number="1", title="Wingspan",
        synopsis="A competitive bird-collection engine-building board game for nature enthusiasts.",
        release_date=date(2019, 3, 8),
        series_status="ongoing",
        creators=[SeedCreator("Elizabeth Hargrave", "designer"), SeedCreator("Natalia Rojas", "artist"),
                  SeedCreator("Ana Maria Martinez Jaramillo", "artist")],
        tags=["engine building", "card game", "nature", "educational"],
        editions=[
            SeedEdition(title="Core Game", fmt="Board Game", publisher="Stonemaier Games", release_date=date(2019, 3, 8),
                        age_rating="10+", release_status="released",
                        variants=[SeedVariant(name="Standard", variant_type="physical", cover_price_cents=6500, currency="USD")]),
            SeedEdition(title="Nesting Box", fmt="Board Game Collector", publisher="Stonemaier Games", release_date=date(2020, 1, 1),
                        subtitle="Nesting Box Collector's Edition",
                        variants=[SeedVariant(name="Collector Box", variant_type="physical", cover_price_cents=8500, currency="USD",
                                             description="Premium storage solution with all expansions space")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.boardgame, franchise="Pandemic", publisher="Z-Man Games",
        series="Pandemic", slug="pandemic",
        volume="Pandemic", volume_number=1, start_year=2008,
        item_number="1", title="Pandemic",
        synopsis="A cooperative game where players work together to stop global outbreaks and find cures.",
        release_date=date(2008, 1, 1),
        series_status="ongoing",
        creators=[SeedCreator("Matt Leacock", "designer")],
        characters=[SeedCharacter("Medic", "main"), SeedCharacter("Scientist", "main"),
                    SeedCharacter("Researcher", "supporting")],
        tags=["cooperative", "strategy", "disease", "global"],
    ),
    SeedEntry(
        kind=ItemKind.boardgame, franchise="Pandemic", publisher="Z-Man Games",
        series="Pandemic", slug="pandemic",
        volume="Pandemic", volume_number=1, start_year=2008,
        item_number="2", title="Pandemic Legacy: Season 1",
        synopsis="A legacy-style Pandemic where each game permanently alters the board and rules.",
        release_date=date(2015, 10, 8),
        creators=[SeedCreator("Matt Leacock", "designer"), SeedCreator("Rob Daviau", "designer")],
        story_arcs=["Legacy Campaign"],
        tags=["cooperative", "legacy", "campaign", "narrative"],
    ),
    SeedEntry(
        kind=ItemKind.boardgame, franchise="Terraforming Mars", publisher="FryxGames",
        series="Terraforming Mars", slug="terraforming-mars",
        volume="Terraforming Mars", volume_number=1, start_year=2016,
        item_number="1", title="Terraforming Mars",
        synopsis="Corporations compete to terraform Mars by raising temperature, oxygen, and ocean coverage.",
        release_date=date(2016, 10, 1),
        series_status="ongoing", series_country="SE",
        creators=[SeedCreator("Jacob Fryxelius", "designer")],
        tags=["engine building", "science", "Mars", "corporate"],
        editions=[
            SeedEdition(title="Standard", fmt="Board Game", publisher="Stronghold Games", release_date=date(2016, 10, 1),
                        age_rating="12+",
                        variants=[SeedVariant(name="Standard", variant_type="physical", cover_price_cents=6999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.boardgame, franchise="Spirit Island", publisher="Greater Than Games",
        series="Spirit Island", slug="spirit-island",
        volume="Spirit Island", volume_number=1, start_year=2017,
        item_number="1", title="Spirit Island",
        synopsis="Spirits of the land work together to drive off colonizing invaders in this cooperative strategy game.",
        release_date=date(2017, 9, 22),
        series_status="ongoing",
        creators=[SeedCreator("R. Eric Reuss", "designer")],
        characters=[SeedCharacter("Lightning's Swift Strike", "main"), SeedCharacter("River Surges in Sunlight", "main"),
                    SeedCharacter("Vital Strength of the Earth", "supporting")],
        tags=["cooperative", "strategy", "anti-colonial", "asymmetric"],
    ),
    SeedEntry(
        kind=ItemKind.boardgame, franchise="Root", publisher="Leder Games",
        series="Root", slug="root",
        volume="Root", volume_number=1, start_year=2018,
        item_number="1", title="Root",
        synopsis="An asymmetric war game where woodland factions battle for control of a vast forest.",
        release_date=date(2018, 8, 1),
        series_status="ongoing",
        creators=[SeedCreator("Cole Wehrle", "designer"), SeedCreator("Kyle Ferrin", "artist")],
        characters=[SeedCharacter("Marquise de Cat", "main"), SeedCharacter("Eyrie Dynasties", "main"),
                    SeedCharacter("Woodland Alliance", "main"), SeedCharacter("Vagabond", "main")],
        tags=["asymmetric", "war game", "area control", "woodland"],
        editions=[
            SeedEdition(title="Standard", fmt="Board Game", publisher="Leder Games", release_date=date(2018, 8, 1),
                        age_rating="10+", release_status="released",
                        variants=[SeedVariant(name="Standard", variant_type="physical", cover_price_cents=6000, currency="USD")]),
            SeedEdition(title="Marauder Expansion", fmt="Expansion", publisher="Leder Games", release_date=date(2022, 7, 1),
                        subtitle="The Marauder Expansion",
                        variants=[SeedVariant(name="Marauder", variant_type="physical", cover_price_cents=4000, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.boardgame, franchise="Brass", publisher="Roxley Games",
        series="Brass", slug="brass",
        volume="Brass", volume_number=1, start_year=2018,
        item_number="1", title="Brass: Birmingham",
        synopsis="Build industries and networks in Birmingham during the industrial revolution.",
        release_date=date(2018, 12, 1),
        series_status="completed", series_country="CA",
        creators=[SeedCreator("Gavan Brown", "designer"), SeedCreator("Matt Tolman", "designer"),
                  SeedCreator("Martin Wallace", "original designer")],
        tags=["economic", "network building", "industrial", "strategy"],
    ),
    SeedEntry(
        kind=ItemKind.boardgame, franchise="Scythe", publisher="Stonemaier Games",
        series="Scythe", slug="scythe",
        volume="Scythe", volume_number=1, start_year=2016,
        item_number="1", title="Scythe",
        synopsis="An alternate-history 1920s strategy game featuring mechs and farming in Eastern Europe.",
        release_date=date(2016, 8, 18),
        series_status="ongoing",
        creators=[SeedCreator("Jamey Stegmaier", "designer"), SeedCreator("Jakub Różalski", "artist")],
        characters=[SeedCharacter("Anna & Wojtek", "main"), SeedCharacter("Gunter & Nacht", "main")],
        tags=["strategy", "area control", "alternate history", "mechs"],
        editions=[
            SeedEdition(title="Standard", fmt="Board Game", publisher="Stonemaier Games", release_date=date(2016, 8, 18),
                        age_rating="14+", release_status="released",
                        variants=[SeedVariant(name="Standard", variant_type="physical", cover_price_cents=8000, currency="USD")]),
            SeedEdition(title="Collector's Edition", fmt="Board Game Collector", publisher="Stonemaier Games", release_date=date(2016, 8, 18),
                        subtitle="Collector's Edition",
                        variants=[SeedVariant(name="Collector", variant_type="physical", cover_price_cents=16500, currency="USD",
                                             description="Includes metal coins, realistic resources, and extended board")]),
        ],
    ),
]

# ===================================================================
#  Collect all entries
# ===================================================================
ALL_SEED_ENTRIES: list[SeedEntry] = (
    SEED_MOVIES + SEED_TV + SEED_BOOKS
    + SEED_MUSIC + SEED_GAMES + SEED_BOARDGAMES
    + []  # comics are in seed_comics.py already
)


# ---------------------------------------------------------------------------
#  Database helpers (mirrors seed_comics.py patterns)
# ---------------------------------------------------------------------------
async def _get_or_create_franchise(db, name: str) -> Franchise:
    result = await db.execute(select(Franchise).where(Franchise.name == name))
    franchise = result.scalar_one_or_none()
    if franchise is not None:
        return franchise
    franchise = Franchise(name=name, description=f"{name} seed data.")
    db.add(franchise)
    await db.flush()
    return franchise


async def _get_or_create_series(db, entry: SeedEntry, franchise: Franchise) -> Series:
    result = await db.execute(select(Series).where(Series.slug == entry.slug))
    series = result.scalar_one_or_none()
    if series is not None:
        return series
    series = Series(
        franchise=franchise,
        kind=entry.kind,
        title=entry.series,
        slug=entry.slug,
        description=f"Seed data for {entry.series}.",
        original_title=entry.series_original_title,
        start_date=date(entry.start_year, 1, 1),
        status=entry.series_status,
        language=entry.series_language,
        country=entry.series_country,
    )
    db.add(series)
    await db.flush()
    return series


async def _get_or_create_volume(db, entry: SeedEntry, series: Series) -> Volume:
    result = await db.execute(select(Volume).where(Volume.name == entry.volume))
    volume = result.scalar_one_or_none()
    if volume is not None:
        return volume
    volume = Volume(
        series=series,
        name=entry.volume,
        volume_number=entry.volume_number,
        start_year=entry.start_year,
        start_date=date(entry.start_year, 1, 1),
        description=f"Volume {entry.volume_number} of {entry.series}.",
    )
    db.add(volume)
    await db.flush()
    return volume


async def _get_or_create_item(db, entry: SeedEntry, volume: Volume) -> Item:
    result = await db.execute(
        select(Item).where(
            Item.volume_id == volume.id,
            Item.item_number == entry.item_number,
            Item.kind == entry.kind,
        )
    )
    item = result.scalar_one_or_none()
    if item is not None:
        item.title = entry.title
        item.title_extension = entry.title_extension
        item.sort_key = entry.sort_key
        item.synopsis = entry.synopsis
        item.runtime_minutes = entry.runtime_minutes
        item.page_count = entry.page_count
        item.season_number = entry.season_number
        item.episode_number = entry.episode_number
        item.metadata_json = entry.metadata_json
        return item

    item = Item(
        volume=volume,
        kind=entry.kind,
        title=entry.title,
        title_extension=entry.title_extension,
        item_number=entry.item_number,
        sort_key=entry.sort_key,
        synopsis=entry.synopsis,
        runtime_minutes=entry.runtime_minutes,
        page_count=entry.page_count,
        season_number=entry.season_number,
        episode_number=entry.episode_number,
        metadata_json=entry.metadata_json,
    )
    db.add(item)
    await db.flush()
    return item


async def _ensure_editions_and_variants(db, entry: SeedEntry, item: Item) -> None:
    edition_defs = entry.editions if entry.editions else [_default_edition(entry)]
    cover_url, thumbnail_url = await resolve_seed_cover_urls(
        kind=entry.kind,
        slug=entry.slug,
        title=entry.title,
        series=entry.series,
        fallback_key=f"collectarr-{entry.kind.value}-{entry.slug}-{entry.item_number}",
    )
    for ed_def in edition_defs:
        result = await db.execute(
            select(Edition).where(
                Edition.item_id == item.id,
                Edition.title == ed_def.title,
            )
        )
        edition = result.scalar_one_or_none()
        if edition is None:
            edition = Edition(
                item=item,
                title=ed_def.title,
                format=ed_def.fmt,
                publisher=ed_def.publisher or entry.publisher,
                language=ed_def.language,
                region=ed_def.region,
                release_date=ed_def.release_date or entry.release_date,
                isbn=ed_def.isbn,
                upc=ed_def.upc,
                imprint=ed_def.imprint,
                subtitle=ed_def.subtitle,
                series_group=ed_def.series_group,
                age_rating=ed_def.age_rating,
                catalog_number=ed_def.catalog_number,
                release_status=ed_def.release_status,
                metadata_json={"seed": True},
            )
            db.add(edition)
            await db.flush()
        else:
            edition.format = ed_def.fmt
            edition.publisher = ed_def.publisher or entry.publisher
            edition.language = ed_def.language
            edition.region = ed_def.region
            edition.release_date = ed_def.release_date or entry.release_date
            edition.imprint = ed_def.imprint
            edition.subtitle = ed_def.subtitle
            edition.series_group = ed_def.series_group
            edition.age_rating = ed_def.age_rating
            edition.catalog_number = ed_def.catalog_number
            edition.release_status = ed_def.release_status
            edition.metadata_json = {"seed": True}

        for var_def in ed_def.variants:
            result = await db.execute(
                select(Variant).where(
                    Variant.edition_id == edition.id,
                    Variant.name == var_def.name,
                )
            )
            variant = result.scalar_one_or_none()
            if variant is None:
                variant = Variant(
                    edition=edition,
                    name=var_def.name,
                    variant_type=var_def.variant_type,
                    barcode=var_def.barcode,
                    isbn=var_def.isbn,
                    sku=var_def.sku,
                    region=var_def.region,
                    is_primary=var_def.is_primary,
                    cover_price_cents=var_def.cover_price_cents,
                    currency=var_def.currency,
                    platform=var_def.platform,
                    description=var_def.description,
                    cover_image_url=cover_url,
                    thumbnail_image_url=thumbnail_url,
                    metadata_json=var_def.metadata_json,
                )
                db.add(variant)
            else:
                variant.variant_type = var_def.variant_type
                variant.barcode = var_def.barcode
                variant.isbn = var_def.isbn
                variant.sku = var_def.sku
                variant.region = var_def.region
                variant.is_primary = var_def.is_primary
                variant.cover_price_cents = var_def.cover_price_cents
                variant.currency = var_def.currency
                variant.platform = var_def.platform
                variant.description = var_def.description
                variant.cover_image_url = cover_url
                variant.thumbnail_image_url = thumbnail_url
                variant.metadata_json = var_def.metadata_json


async def _ensure_provider_id(db, entry: SeedEntry, item: Item) -> None:
    result = await db.execute(
        select(ItemProviderLink).where(
            ItemProviderLink.provider == entry.provider,
            ItemProviderLink.provider_item_id == entry.provider_id,
        )
    )
    existing = result.scalar_one_or_none()
    site_url = f"https://seed.collectarr.local/{entry.kind.value}/{entry.slug}/{entry.item_number}"
    api_url = (
        "https://seed.collectarr.local/api/"
        f"providers/{entry.provider.value}/items/{entry.provider_id}"
    )
    if existing is None:
        db.add(ItemProviderLink(
            provider=entry.provider,
            provider_item_id=entry.provider_id,
            item_id=item.id,
            site_url=site_url,
            api_url=api_url,
        ))
        return

    existing.site_url = site_url
    existing.api_url = api_url


def _bundle_format_for_kind(kind: ItemKind) -> str:
    if kind in {ItemKind.music, ItemKind.tv, ItemKind.movie}:
        return "Box Set"
    if kind == ItemKind.game:
        return "Collector Bundle"
    if kind == ItemKind.boardgame:
        return "Core + Expansion"
    return "Collection"


async def _ensure_series_bundle_releases(
    db,
    *,
    entry: SeedEntry,
    series: Series,
    volume: Volume,
    items: list[Item],
) -> None:
    if len(items) < 2:
        return

    # Keep bundle composition deterministic even if incoming order drifts.
    sorted_items = sorted(items, key=lambda item: item.sort_key or "")

    for bundle_index, start in enumerate(range(0, len(sorted_items), 3), start=1):
        chunk = sorted_items[start : start + 3]
        if len(chunk) < 2:
            continue

        bundle_title = f"{entry.series} Collection {bundle_index}"
        bundle_provider_id = f"seed-{entry.slug}-bundle-{bundle_index}"
        cover_url, thumb_url = await resolve_seed_cover_urls(
            kind=entry.kind,
            slug=entry.slug,
            title=bundle_title,
            series=entry.series,
            fallback_key=f"collectarr-{entry.kind.value}-{entry.slug}-bundle-{bundle_index}",
        )

        result = await db.execute(
            select(BundleRelease).where(
                BundleRelease.kind == entry.kind,
                BundleRelease.title == bundle_title,
                BundleRelease.series_id == series.id,
            )
        )
        bundle = result.scalar_one_or_none()
        if bundle is None:
            bundle = BundleRelease(
                kind=entry.kind,
                title=bundle_title,
                bundle_type="collection",
                franchise_id=series.franchise_id,
                series_id=series.id,
                volume_id=volume.id,
                primary_item_id=chunk[0].id,
                format=_bundle_format_for_kind(entry.kind),
                variant_type="standard",
                packaging_type="boxed",
                region="US",
                language=entry.series_language,
                publisher=entry.publisher,
                sku=f"SEED-{entry.slug.upper().replace('-', '')}-B{bundle_index:02d}",
                barcode=f"9900{bundle_index:02d}{len(chunk):02d}{entry.start_year}",
                release_date=entry.release_date,
                cover_image_url=cover_url,
                thumbnail_image_url=thumb_url,
                metadata_json={"seed": True, "series_slug": entry.slug, "bundle_index": bundle_index},
            )
            db.add(bundle)
            await db.flush()
        else:
            bundle.primary_item_id = chunk[0].id
            bundle.cover_image_url = cover_url
            bundle.thumbnail_image_url = thumb_url
            bundle.release_date = entry.release_date
            bundle.metadata_json = {
                "seed": True,
                "series_slug": entry.slug,
                "bundle_index": bundle_index,
            }

        link_result = await db.execute(
            select(BundleReleaseProviderLink).where(
                BundleReleaseProviderLink.bundle_release_id == bundle.id,
                BundleReleaseProviderLink.provider == entry.provider,
            )
        )
        bundle_provider_link = link_result.scalar_one_or_none()
        if bundle_provider_link is None:
            db.add(
                BundleReleaseProviderLink(
                    bundle_release_id=bundle.id,
                    provider=entry.provider,
                    provider_item_id=bundle_provider_id,
                    site_url=(
                        "https://seed.collectarr.local/bundles/"
                        f"{entry.kind.value}/{entry.slug}/{bundle_index}"
                    ),
                    api_url=(
                        "https://seed.collectarr.local/api/providers/"
                        f"{entry.provider.value}/bundles/{bundle_provider_id}"
                    ),
                )
            )
        else:
            bundle_provider_link.provider_item_id = bundle_provider_id
            bundle_provider_link.site_url = (
                "https://seed.collectarr.local/bundles/"
                f"{entry.kind.value}/{entry.slug}/{bundle_index}"
            )
            bundle_provider_link.api_url = (
                "https://seed.collectarr.local/api/providers/"
                f"{entry.provider.value}/bundles/{bundle_provider_id}"
            )

        for sequence, member in enumerate(chunk, start=1):
            member_result = await db.execute(
                select(BundleReleaseItem).where(
                    BundleReleaseItem.bundle_release_id == bundle.id,
                    BundleReleaseItem.item_id == member.id,
                )
            )
            existing_member = member_result.scalar_one_or_none()
            if existing_member is None:
                db.add(
                    BundleReleaseItem(
                        bundle_release_id=bundle.id,
                        item_id=member.id,
                        role="included",
                        sequence_number=sequence,
                        disc_number=1,
                        disc_label=f"Disc {sequence}",
                        quantity=1,
                        is_primary=(sequence == 1),
                        metadata_json={"seed": True},
                    )
                )
                continue

            existing_member.sequence_number = sequence
            existing_member.disc_label = f"Disc {sequence}"
            existing_member.is_primary = (sequence == 1)
            existing_member.metadata_json = {"seed": True}


# ---------------------------------------------------------------------------
#  Entity helpers – Person, Organization, Character, Tag, StoryArc
# ---------------------------------------------------------------------------
async def _get_or_create_person(db, name: str, _cache: dict[str, Person]) -> Person:
    if name in _cache:
        return _cache[name]
    result = await db.execute(select(Person).where(Person.name == name))
    person = result.scalar_one_or_none()
    if person is None:
        person = Person(name=name)
        db.add(person)
        await db.flush()
    _cache[name] = person
    return person


async def _get_or_create_organization(
    db, name: str, org_type: str | None, _cache: dict[str, Organization],
) -> Organization:
    if name in _cache:
        return _cache[name]
    result = await db.execute(select(Organization).where(Organization.name == name))
    org = result.scalar_one_or_none()
    if org is None:
        org = Organization(name=name, type=org_type)
        db.add(org)
        await db.flush()
    _cache[name] = org
    return org


async def _get_or_create_character(
    db, name: str, _cache: dict[str, Character],
) -> Character:
    if name in _cache:
        return _cache[name]
    result = await db.execute(select(Character).where(Character.name == name))
    char = result.scalar_one_or_none()
    if char is None:
        char = Character(name=name, canonical_name=name)
        db.add(char)
        await db.flush()
    _cache[name] = char
    return char


async def _get_or_create_tag(
    db, kind: str, name: str, _cache: dict[str, Tag],
) -> Tag:
    cache_key = f"{kind}:{name}"
    if cache_key in _cache:
        return _cache[cache_key]
    result = await db.execute(select(Tag).where(Tag.kind == kind, Tag.name == name))
    tag = result.scalar_one_or_none()
    if tag is None:
        tag = Tag(kind=kind, name=name)
        db.add(tag)
        await db.flush()
    _cache[cache_key] = tag
    return tag


async def _get_or_create_story_arc(
    db, name: str, publisher: str | None, _cache: dict[str, StoryArc],
) -> StoryArc:
    cache_key = f"{name}:{publisher or ''}"
    if cache_key in _cache:
        return _cache[cache_key]
    result = await db.execute(
        select(StoryArc).where(StoryArc.name == name, StoryArc.publisher == publisher)
    )
    arc = result.scalar_one_or_none()
    if arc is None:
        arc = StoryArc(name=name, publisher=publisher, description=f"Story arc: {name}")
        db.add(arc)
        await db.flush()
    _cache[cache_key] = arc
    return arc


async def _ensure_creators(
    db, entry: SeedEntry, item: Item, person_cache: dict[str, Person],
) -> None:
    for creator in entry.creators:
        person = await _get_or_create_person(db, creator.name, person_cache)
        result = await db.execute(
            select(EntityPerson).where(
                EntityPerson.entity_type == "item",
                EntityPerson.entity_id == item.id,
                EntityPerson.person_id == person.id,
                EntityPerson.role == creator.role,
            )
        )
        if result.scalar_one_or_none() is None:
            db.add(EntityPerson(
                entity_type="item", entity_id=item.id,
                person_id=person.id, role=creator.role,
            ))


async def _ensure_publisher_org(
    db, entry: SeedEntry, item: Item, org_cache: dict[str, Organization],
) -> None:
    org = await _get_or_create_organization(db, entry.publisher, "publisher", org_cache)
    result = await db.execute(
        select(EntityOrganization).where(
            EntityOrganization.entity_type == "item",
            EntityOrganization.entity_id == item.id,
            EntityOrganization.organization_id == org.id,
            EntityOrganization.role == "publisher",
        )
    )
    if result.scalar_one_or_none() is None:
        db.add(EntityOrganization(
            entity_type="item", entity_id=item.id,
            organization_id=org.id, role="publisher",
        ))


async def _ensure_characters(
    db, entry: SeedEntry, item: Item, char_cache: dict[str, Character],
) -> None:
    for ch in entry.characters:
        character = await _get_or_create_character(db, ch.name, char_cache)
        result = await db.execute(
            select(CharacterAppearance).where(
                CharacterAppearance.character_id == character.id,
                CharacterAppearance.item_id == item.id,
            )
        )
        if result.scalar_one_or_none() is None:
            db.add(CharacterAppearance(
                character_id=character.id, item_id=item.id, role=ch.role,
            ))


async def _ensure_tags(
    db, entry: SeedEntry, item: Item, tag_cache: dict[str, Tag],
) -> None:
    tag_kind = entry.kind.value  # "movie", "book", etc.
    for tag_name in entry.tags:
        tag = await _get_or_create_tag(db, tag_kind, tag_name, tag_cache)
        result = await db.execute(
            select(EntityTag).where(
                EntityTag.entity_type == "item",
                EntityTag.entity_id == item.id,
                EntityTag.tag_id == tag.id,
            )
        )
        if result.scalar_one_or_none() is None:
            db.add(EntityTag(
                entity_type="item", entity_id=item.id, tag_id=tag.id,
            ))


async def _ensure_story_arcs(
    db, entry: SeedEntry, item: Item, arc_cache: dict[str, StoryArc],
) -> None:
    for arc_name in entry.story_arcs:
        arc = await _get_or_create_story_arc(db, arc_name, entry.publisher, arc_cache)
        result = await db.execute(
            select(StoryArcItem).where(
                StoryArcItem.story_arc_id == arc.id,
                StoryArcItem.item_id == item.id,
            )
        )
        if result.scalar_one_or_none() is None:
            db.add(StoryArcItem(story_arc_id=arc.id, item_id=item.id))


# ---------------------------------------------------------------------------
#  Main seed function
# ---------------------------------------------------------------------------
async def seed() -> None:
    async with AsyncSessionLocal() as db:
        franchises: dict[str, Franchise] = {}
        series_by_slug: dict[str, Series] = {}
        volumes_by_name: dict[str, Volume] = {}
        person_cache: dict[str, Person] = {}
        org_cache: dict[str, Organization] = {}
        char_cache: dict[str, Character] = {}
        tag_cache: dict[str, Tag] = {}
        arc_cache: dict[str, StoryArc] = {}
        items_by_slug: dict[str, list[Item]] = {}
        series_by_slug_context: dict[str, tuple[SeedEntry, Series, Volume]] = {}

        for entry in ALL_SEED_ENTRIES:
            franchise = franchises.get(entry.franchise)
            if franchise is None:
                franchise = await _get_or_create_franchise(db, entry.franchise)
                franchises[entry.franchise] = franchise

            series = series_by_slug.get(entry.slug)
            if series is None:
                series = await _get_or_create_series(db, entry, franchise)
                series_by_slug[entry.slug] = series

            volume = volumes_by_name.get(entry.volume)
            if volume is None:
                volume = await _get_or_create_volume(db, entry, series)
                volumes_by_name[entry.volume] = volume

            item = await _get_or_create_item(db, entry, volume)
            await _ensure_editions_and_variants(db, entry, item)
            await _ensure_provider_id(db, entry, item)
            await _ensure_publisher_org(db, entry, item, org_cache)
            await _ensure_creators(db, entry, item, person_cache)
            await _ensure_characters(db, entry, item, char_cache)
            await _ensure_tags(db, entry, item, tag_cache)
            await _ensure_story_arcs(db, entry, item, arc_cache)

            items_by_slug.setdefault(entry.slug, []).append(item)
            series_by_slug_context[entry.slug] = (entry, series, volume)

        for slug, items in items_by_slug.items():
            entry, series, volume = series_by_slug_context[slug]
            await _ensure_series_bundle_releases(
                db,
                entry=entry,
                series=series,
                volume=volume,
                items=items,
            )

        await db.commit()
        print(f"Seeded {len(ALL_SEED_ENTRIES)} items across all library types.")
        print(f"  Persons: {len(person_cache)}, Organizations: {len(org_cache)}, "
              f"Characters: {len(char_cache)}, Tags: {len(tag_cache)}, Story Arcs: {len(arc_cache)}")


if __name__ == "__main__":
    asyncio.run(seed())
