"""Seed data for ALL library types — 10 items each with varied editions/variants."""

import asyncio
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import (
    Edition,
    ExternalProviderId,
    Franchise,
    Item,
    Series,
    Variant,
    Volume,
)

# ---------------------------------------------------------------------------
# Provider mapping per kind
# ---------------------------------------------------------------------------
_PROVIDER_FOR_KIND: dict[ItemKind, ExternalProvider] = {
    ItemKind.comic: ExternalProvider.comicvine,
    ItemKind.manga: ExternalProvider.mangadex,
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
    runtime_minutes: int | None = None
    page_count: int | None = None
    season_number: int | None = None
    episode_number: int | None = None
    metadata_json: dict | None = None
    editions: list["SeedEdition"] = field(default_factory=list)

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
    variants: list["SeedVariant"] = field(default_factory=list)


@dataclass(frozen=True)
class SeedVariant:
    name: str
    variant_type: str | None = None
    barcode: str | None = None
    is_primary: bool = True
    cover_price_cents: int | None = None
    currency: str | None = None
    platform: str | None = None
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
        item_number="1", title="Batman Begins",
        synopsis="After witnessing his parents' murder, Bruce Wayne trains to become a symbol of justice.",
        release_date=date(2005, 6, 15), runtime_minutes=140,
        editions=[
            SeedEdition(title="DVD", fmt="DVD", publisher="Warner Bros.", release_date=date(2005, 10, 18),
                        variants=[SeedVariant(name="DVD", variant_type="physical", cover_price_cents=1999, currency="USD")]),
            SeedEdition(title="Blu-ray", fmt="Blu-ray", publisher="Warner Bros.", release_date=date(2008, 7, 8),
                        variants=[SeedVariant(name="Blu-ray", variant_type="physical", cover_price_cents=2499, currency="USD")]),
            SeedEdition(title="4K UHD", fmt="4K UHD", publisher="Warner Bros.", release_date=date(2017, 12, 19),
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
        editions=[
            SeedEdition(title="Blu-ray", fmt="Blu-ray", publisher="Warner Bros.", release_date=date(2008, 12, 9),
                        variants=[SeedVariant(name="Blu-ray", variant_type="physical", cover_price_cents=2499, currency="USD")]),
            SeedEdition(title="4K UHD Steelbook", fmt="4K UHD", publisher="Warner Bros.", release_date=date(2017, 12, 19),
                        variants=[SeedVariant(name="Steelbook", variant_type="physical", cover_price_cents=3499, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.movie, franchise="The Dark Knight Trilogy", publisher="Warner Bros.",
        series="The Dark Knight Trilogy", slug="dark-knight-trilogy",
        volume="The Dark Knight Trilogy", volume_number=1, start_year=2005,
        item_number="3", title="The Dark Knight Rises",
        synopsis="Eight years after the Joker's reign, Bane forces Batman out of exile.",
        release_date=date(2012, 7, 20), runtime_minutes=165,
    ),
    SeedEntry(
        kind=ItemKind.movie, franchise="Blade Runner", publisher="Warner Bros.",
        series="Blade Runner", slug="blade-runner",
        volume="Blade Runner", volume_number=1, start_year=1982,
        item_number="1", title="Blade Runner",
        synopsis="A blade runner must pursue and terminate four replicants who have returned to Earth.",
        release_date=date(1982, 6, 25), runtime_minutes=117,
        editions=[
            SeedEdition(title="The Final Cut", fmt="Blu-ray", publisher="Warner Bros.", release_date=date(2007, 12, 18),
                        variants=[SeedVariant(name="The Final Cut Blu-ray", variant_type="physical")]),
            SeedEdition(title="Director's Cut", fmt="DVD", publisher="Warner Bros.", release_date=date(1997, 9, 9),
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
    ),
    SeedEntry(
        kind=ItemKind.movie, franchise="Interstellar", publisher="Paramount Pictures",
        series="Interstellar", slug="interstellar",
        volume="Interstellar", volume_number=1, start_year=2014,
        item_number="1", title="Interstellar",
        synopsis="A team of explorers travel through a wormhole in space to ensure humanity's survival.",
        release_date=date(2014, 11, 7), runtime_minutes=169,
        editions=[
            SeedEdition(title="IMAX Blu-ray", fmt="Blu-ray", publisher="Paramount", release_date=date(2015, 3, 31),
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
        editions=[
            SeedEdition(title="Black & Chrome Edition", fmt="Blu-ray", publisher="Warner Bros.", release_date=date(2016, 12, 6),
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
    ),
    SeedEntry(
        kind=ItemKind.movie, franchise="Alien", publisher="20th Century Fox",
        series="Alien", slug="alien",
        volume="Alien", volume_number=1, start_year=1979,
        item_number="2", title="Aliens",
        synopsis="Ripley returns to the planet where her crew encountered the hostile alien creature.",
        release_date=date(1986, 7, 18), runtime_minutes=137,
    ),
    SeedEntry(
        kind=ItemKind.movie, franchise="The Matrix", publisher="Warner Bros.",
        series="The Matrix", slug="the-matrix",
        volume="The Matrix", volume_number=1, start_year=1999,
        item_number="1", title="The Matrix",
        synopsis="A computer hacker learns about the true nature of reality and his role in the war against its controllers.",
        release_date=date(1999, 3, 31), runtime_minutes=136,
        editions=[
            SeedEdition(title="DVD", fmt="DVD", publisher="Warner Bros.", release_date=date(1999, 9, 21),
                        variants=[SeedVariant(name="DVD", variant_type="physical", cover_price_cents=1499, currency="USD")]),
            SeedEdition(title="4K UHD", fmt="4K UHD", publisher="Warner Bros.", release_date=date(2018, 5, 22),
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
        item_number="1", title="Breaking Bad",
        synopsis="A high school chemistry teacher turned methamphetamine manufacturer partners with a former student.",
        release_date=date(2008, 1, 20), runtime_minutes=49, season_number=1,
        editions=[
            SeedEdition(title="Complete Series Blu-ray", fmt="Blu-ray", publisher="Sony", release_date=date(2014, 11, 25),
                        variants=[SeedVariant(name="Barrel Set", variant_type="physical", cover_price_cents=7999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.tv, franchise="Breaking Bad", publisher="AMC",
        series="Better Call Saul", slug="better-call-saul",
        volume="Better Call Saul", volume_number=1, start_year=2015,
        item_number="1", title="Better Call Saul",
        synopsis="The transformation of Jimmy McGill into Saul Goodman, the morally challenged lawyer.",
        release_date=date(2015, 2, 8), runtime_minutes=53, season_number=1,
    ),
    SeedEntry(
        kind=ItemKind.tv, franchise="The Wire", publisher="HBO",
        series="The Wire", slug="the-wire",
        volume="The Wire", volume_number=1, start_year=2002,
        item_number="1", title="The Wire",
        synopsis="Examines the Baltimore drug scene through the eyes of law enforcers and drug dealers.",
        release_date=date(2002, 6, 2), runtime_minutes=60, season_number=1,
        editions=[
            SeedEdition(title="Complete Series DVD", fmt="DVD", publisher="HBO", release_date=date(2011, 6, 7),
                        variants=[SeedVariant(name="DVD Box Set", variant_type="physical")]),
            SeedEdition(title="Complete Series Blu-ray", fmt="Blu-ray", publisher="HBO", release_date=date(2015, 6, 2),
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
    ),
    SeedEntry(
        kind=ItemKind.tv, franchise="The Sopranos", publisher="HBO",
        series="The Sopranos", slug="the-sopranos",
        volume="The Sopranos", volume_number=1, start_year=1999,
        item_number="1", title="The Sopranos",
        synopsis="New Jersey mob boss Tony Soprano deals with personal and professional issues in his family.",
        release_date=date(1999, 1, 10), runtime_minutes=55, season_number=1,
        editions=[
            SeedEdition(title="Complete Series Blu-ray", fmt="Blu-ray", publisher="HBO", release_date=date(2014, 11, 18),
                        variants=[SeedVariant(name="Complete Blu-ray", variant_type="physical", cover_price_cents=8999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.tv, franchise="True Detective", publisher="HBO",
        series="True Detective", slug="true-detective",
        volume="True Detective", volume_number=1, start_year=2014,
        item_number="1", title="True Detective",
        synopsis="Two detectives trace a Louisiana serial murder case across seventeen years.",
        release_date=date(2014, 1, 12), runtime_minutes=58, season_number=1,
    ),
    SeedEntry(
        kind=ItemKind.tv, franchise="Band of Brothers", publisher="HBO",
        series="Band of Brothers", slug="band-of-brothers",
        volume="Band of Brothers", volume_number=1, start_year=2001,
        item_number="1", title="Band of Brothers",
        synopsis="The story of Easy Company during World War II from their training to V-J Day.",
        release_date=date(2001, 9, 9), runtime_minutes=70,
        editions=[
            SeedEdition(title="Blu-ray", fmt="Blu-ray", publisher="HBO", release_date=date(2008, 11, 11),
                        variants=[SeedVariant(name="Blu-ray Box", variant_type="physical")]),
            SeedEdition(title="4K UHD", fmt="4K UHD", publisher="Warner Bros.", release_date=date(2023, 6, 6),
                        variants=[SeedVariant(name="4K UHD", variant_type="physical", cover_price_cents=5999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.tv, franchise="Dark", publisher="Netflix",
        series="Dark", slug="dark-tv",
        volume="Dark", volume_number=1, start_year=2017,
        item_number="1", title="Dark",
        synopsis="A missing child triggers events that unravel the secrets of four interconnected families.",
        release_date=date(2017, 12, 1), runtime_minutes=52, season_number=1,
    ),
    SeedEntry(
        kind=ItemKind.tv, franchise="Fargo", publisher="FX",
        series="Fargo", slug="fargo-tv",
        volume="Fargo", volume_number=1, start_year=2014,
        item_number="1", title="Fargo",
        synopsis="An anthology series exploring deception, crime, and intrigue across the American Midwest.",
        release_date=date(2014, 4, 15), runtime_minutes=53, season_number=1,
    ),
    SeedEntry(
        kind=ItemKind.tv, franchise="Fleabag", publisher="BBC / Amazon",
        series="Fleabag", slug="fleabag",
        volume="Fleabag", volume_number=1, start_year=2016,
        item_number="1", title="Fleabag",
        synopsis="A dry-witted woman navigates life in London while dealing with loss and complicated relationships.",
        release_date=date(2016, 7, 21), runtime_minutes=27, season_number=1,
    ),
]

# ===================================================================
#  ANIME (10)
# ===================================================================
SEED_ANIME = [
    SeedEntry(
        kind=ItemKind.anime, franchise="Cowboy Bebop", publisher="Sunrise",
        series="Cowboy Bebop", slug="cowboy-bebop",
        volume="Cowboy Bebop", volume_number=1, start_year=1998,
        item_number="1", title="Cowboy Bebop",
        synopsis="A ragtag group of bounty hunters chase criminals across the solar system in 2071.",
        release_date=date(1998, 4, 3), runtime_minutes=25, season_number=1,
        editions=[
            SeedEdition(title="Blu-ray Complete", fmt="Blu-ray", publisher="Funimation", release_date=date(2014, 12, 16),
                        variants=[SeedVariant(name="Blu-ray", variant_type="physical", cover_price_cents=4499, currency="USD")]),
            SeedEdition(title="4K UHD Collector", fmt="4K UHD", publisher="Funimation", release_date=date(2023, 6, 27),
                        variants=[SeedVariant(name="Collector's 4K", variant_type="physical", cover_price_cents=8999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.anime, franchise="Neon Genesis Evangelion", publisher="Gainax",
        series="Neon Genesis Evangelion", slug="neon-genesis-evangelion",
        volume="Neon Genesis Evangelion", volume_number=1, start_year=1995,
        item_number="1", title="Neon Genesis Evangelion",
        synopsis="Shinji Ikari is recruited by his father to pilot a giant mecha against monstrous beings called Angels.",
        release_date=date(1995, 10, 4), runtime_minutes=24, season_number=1,
        editions=[
            SeedEdition(title="Ultimate Edition Blu-ray", fmt="Blu-ray", publisher="GKIDS", release_date=date(2021, 12, 7),
                        variants=[SeedVariant(name="Ultimate Edition", variant_type="physical", cover_price_cents=19999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.anime, franchise="Studio Ghibli", publisher="Studio Ghibli",
        series="Spirited Away", slug="spirited-away",
        volume="Spirited Away", volume_number=1, start_year=2001,
        item_number="1", title="Spirited Away",
        synopsis="A young girl becomes trapped in a strange world of spirits and must find a way to free herself and her parents.",
        release_date=date(2001, 7, 20), runtime_minutes=125,
        editions=[
            SeedEdition(title="DVD", fmt="DVD", publisher="Walt Disney Home", release_date=date(2003, 4, 15),
                        variants=[SeedVariant(name="DVD", variant_type="physical")]),
            SeedEdition(title="Blu-ray", fmt="Blu-ray", publisher="GKIDS / Shout Factory", release_date=date(2017, 10, 17),
                        variants=[SeedVariant(name="Blu-ray", variant_type="physical", cover_price_cents=2999, currency="USD")]),
            SeedEdition(title="Steelbook", fmt="Blu-ray", publisher="GKIDS", release_date=date(2019, 11, 12),
                        variants=[SeedVariant(name="Steelbook", variant_type="physical", cover_price_cents=3499, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.anime, franchise="Studio Ghibli", publisher="Studio Ghibli",
        series="Princess Mononoke", slug="princess-mononoke",
        volume="Princess Mononoke", volume_number=1, start_year=1997,
        item_number="1", title="Princess Mononoke",
        synopsis="A prince becomes embroiled in a struggle between forest gods and a mining colony.",
        release_date=date(1997, 7, 12), runtime_minutes=134,
    ),
    SeedEntry(
        kind=ItemKind.anime, franchise="Fullmetal Alchemist", publisher="Bones",
        series="Fullmetal Alchemist: Brotherhood", slug="fmab",
        volume="Fullmetal Alchemist: Brotherhood", volume_number=1, start_year=2009,
        item_number="1", title="Fullmetal Alchemist: Brotherhood",
        synopsis="Two brothers use alchemy to search for the Philosopher's Stone to restore their bodies.",
        release_date=date(2009, 4, 5), runtime_minutes=24, season_number=1,
        editions=[
            SeedEdition(title="Complete Blu-ray Box", fmt="Blu-ray", publisher="Funimation", release_date=date(2016, 8, 2),
                        variants=[SeedVariant(name="Complete Box", variant_type="physical", cover_price_cents=5999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.anime, franchise="Attack on Titan", publisher="Wit Studio / MAPPA",
        series="Attack on Titan", slug="attack-on-titan",
        volume="Attack on Titan", volume_number=1, start_year=2013,
        item_number="1", title="Attack on Titan",
        synopsis="Humanity fights for survival against enormous humanoid creatures known as Titans.",
        release_date=date(2013, 4, 7), runtime_minutes=24, season_number=1,
    ),
    SeedEntry(
        kind=ItemKind.anime, franchise="Steins;Gate", publisher="White Fox",
        series="Steins;Gate", slug="steins-gate",
        volume="Steins;Gate", volume_number=1, start_year=2011,
        item_number="1", title="Steins;Gate",
        synopsis="A self-proclaimed mad scientist accidentally creates a time machine using a microwave.",
        release_date=date(2011, 4, 6), runtime_minutes=24, season_number=1,
    ),
    SeedEntry(
        kind=ItemKind.anime, franchise="Death Note", publisher="Madhouse",
        series="Death Note", slug="death-note-anime",
        volume="Death Note", volume_number=1, start_year=2006,
        item_number="1", title="Death Note",
        synopsis="A high school student discovers a supernatural notebook that can kill anyone whose name is written in it.",
        release_date=date(2006, 10, 4), runtime_minutes=23, season_number=1,
        editions=[
            SeedEdition(title="Complete Series DVD", fmt="DVD", publisher="Viz Media", release_date=date(2008, 11, 18),
                        variants=[SeedVariant(name="DVD Box", variant_type="physical")]),
            SeedEdition(title="Complete Series Blu-ray", fmt="Blu-ray", publisher="Viz Media", release_date=date(2016, 10, 4),
                        variants=[SeedVariant(name="Blu-ray", variant_type="physical", cover_price_cents=3999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.anime, franchise="One Punch Man", publisher="Madhouse",
        series="One Punch Man", slug="one-punch-man",
        volume="One Punch Man", volume_number=1, start_year=2015,
        item_number="1", title="One Punch Man",
        synopsis="A hero who can defeat any opponent with a single punch struggles with boredom.",
        release_date=date(2015, 10, 5), runtime_minutes=24, season_number=1,
    ),
    SeedEntry(
        kind=ItemKind.anime, franchise="Akira", publisher="TMS Entertainment",
        series="Akira", slug="akira",
        volume="Akira", volume_number=1, start_year=1988,
        item_number="1", title="Akira",
        synopsis="A secret military project endangers Neo-Tokyo when it turns a biker gang member into a rampaging psychic.",
        release_date=date(1988, 7, 16), runtime_minutes=124,
        editions=[
            SeedEdition(title="4K UHD Limited Edition", fmt="4K UHD", publisher="Funimation", release_date=date(2020, 12, 22),
                        variants=[SeedVariant(name="4K Limited", variant_type="physical", cover_price_cents=3499, currency="USD")]),
        ],
    ),
]

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
        editions=[
            SeedEdition(title="Mass Market Paperback", fmt="Paperback", publisher="Ace Books", release_date=date(1990, 9, 1),
                        isbn="9780441172719",
                        variants=[SeedVariant(name="Paperback", variant_type="physical", cover_price_cents=999, currency="USD")]),
            SeedEdition(title="Hardcover", fmt="Hardcover", publisher="Chilton Books", release_date=date(1965, 8, 1),
                        variants=[SeedVariant(name="Hardcover", variant_type="physical")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.book, franchise="Dune", publisher="Chilton Books",
        series="Dune", slug="dune",
        volume="Dune", volume_number=1, start_year=1965,
        item_number="2", title="Dune Messiah",
        synopsis="Paul Atreides faces a conspiracy to overthrow him twelve years after becoming Emperor.",
        release_date=date(1969, 10, 1), page_count=256,
    ),
    SeedEntry(
        kind=ItemKind.book, franchise="Foundation", publisher="Gnome Press",
        series="Foundation", slug="foundation",
        volume="Foundation", volume_number=1, start_year=1951,
        item_number="1", title="Foundation",
        synopsis="A mathematician predicts the fall of the Galactic Empire and creates a plan to preserve knowledge.",
        release_date=date(1951, 5, 1), page_count=244,
        editions=[
            SeedEdition(title="Paperback", fmt="Paperback", publisher="Bantam Spectra", release_date=date(2004, 6, 1),
                        isbn="9780553293357",
                        variants=[SeedVariant(name="Paperback", variant_type="physical", cover_price_cents=899, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.book, franchise="1984", publisher="Secker & Warburg",
        series="1984", slug="nineteen-eighty-four",
        volume="1984", volume_number=1, start_year=1949,
        item_number="1", title="1984",
        synopsis="In a totalitarian future, a man rebels against the oppressive government that controls every aspect of life.",
        release_date=date(1949, 6, 8), page_count=328,
        editions=[
            SeedEdition(title="Centennial Edition", fmt="Hardcover", publisher="Plume", release_date=date(2003, 5, 6),
                        variants=[SeedVariant(name="Centennial HC", variant_type="physical")]),
            SeedEdition(title="Penguin Paperback", fmt="Paperback", publisher="Penguin", release_date=date(1961, 1, 1),
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
    ),
    SeedEntry(
        kind=ItemKind.book, franchise="Hitchhiker's Guide", publisher="Pan Books",
        series="The Hitchhiker's Guide to the Galaxy", slug="hitchhikers-guide",
        volume="The Hitchhiker's Guide to the Galaxy", volume_number=1, start_year=1979,
        item_number="1", title="The Hitchhiker's Guide to the Galaxy",
        synopsis="Seconds before Earth is destroyed, Arthur Dent is saved by his friend Ford Prefect, a researcher for the Guide.",
        release_date=date(1979, 10, 12), page_count=180,
        editions=[
            SeedEdition(title="Illustrated Edition", fmt="Hardcover", publisher="Del Rey", release_date=date(2007, 4, 10),
                        isbn="9780345453747",
                        variants=[SeedVariant(name="Illustrated HC", variant_type="physical", cover_price_cents=2500, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.book, franchise="Lord of the Rings", publisher="George Allen & Unwin",
        series="The Lord of the Rings", slug="lord-of-the-rings",
        volume="The Lord of the Rings", volume_number=1, start_year=1954,
        item_number="1", title="The Fellowship of the Ring",
        synopsis="A hobbit inherits a ring of power and begins a journey to destroy it.",
        release_date=date(1954, 7, 29), page_count=423,
    ),
    SeedEntry(
        kind=ItemKind.book, franchise="Lord of the Rings", publisher="George Allen & Unwin",
        series="The Lord of the Rings", slug="lord-of-the-rings",
        volume="The Lord of the Rings", volume_number=1, start_year=1954,
        item_number="2", title="The Two Towers",
        synopsis="The fellowship is broken as war spreads and the quest to destroy the ring continues.",
        release_date=date(1954, 11, 11), page_count=352,
    ),
    SeedEntry(
        kind=ItemKind.book, franchise="Lord of the Rings", publisher="George Allen & Unwin",
        series="The Lord of the Rings", slug="lord-of-the-rings",
        volume="The Lord of the Rings", volume_number=1, start_year=1954,
        item_number="3", title="The Return of the King",
        synopsis="The final battle for Middle-earth begins while Frodo approaches Mount Doom.",
        release_date=date(1955, 10, 20), page_count=416,
    ),
    SeedEntry(
        kind=ItemKind.book, franchise="The Martian", publisher="Crown Publishing",
        series="The Martian", slug="the-martian",
        volume="The Martian", volume_number=1, start_year=2011,
        item_number="1", title="The Martian",
        synopsis="An astronaut must rely on his ingenuity to survive alone on Mars after being presumed dead.",
        release_date=date(2011, 3, 1), page_count=369,
        editions=[
            SeedEdition(title="Hardcover", fmt="Hardcover", publisher="Crown", release_date=date(2014, 2, 11),
                        isbn="9780804139021",
                        variants=[SeedVariant(name="Hardcover", variant_type="physical", cover_price_cents=2400, currency="USD")]),
            SeedEdition(title="Audiobook", fmt="Audiobook", publisher="Podium Audio", release_date=date(2014, 3, 22),
                        variants=[SeedVariant(name="Audiobook", variant_type="digital")]),
        ],
    ),
]

# ===================================================================
#  MANGA (10)
# ===================================================================
SEED_MANGA = [
    SeedEntry(
        kind=ItemKind.manga, franchise="Berserk", publisher="Hakusensha",
        series="Berserk", slug="berserk",
        volume="Berserk", volume_number=1, start_year=1989,
        item_number="1", title="Berserk, Vol. 1",
        synopsis="Guts, a lone mercenary, battles demons in a dark medieval fantasy world.",
        release_date=date(1990, 11, 26), page_count=224,
        editions=[
            SeedEdition(title="Dark Horse English", fmt="Tankōbon", publisher="Dark Horse", language="en", release_date=date(2003, 10, 22),
                        isbn="9781593070205",
                        variants=[SeedVariant(name="Tankōbon", variant_type="physical", cover_price_cents=1499, currency="USD")]),
            SeedEdition(title="Deluxe Edition", fmt="Hardcover", publisher="Dark Horse", language="en", release_date=date(2019, 3, 12),
                        isbn="9781506711980",
                        variants=[SeedVariant(name="Deluxe HC", variant_type="physical", cover_price_cents=4999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.manga, franchise="Berserk", publisher="Hakusensha",
        series="Berserk", slug="berserk",
        volume="Berserk", volume_number=1, start_year=1989,
        item_number="2", title="Berserk, Vol. 2",
        synopsis="Guts continues his relentless war against the demonic Apostles.",
        release_date=date(1991, 6, 28), page_count=232,
    ),
    SeedEntry(
        kind=ItemKind.manga, franchise="Vagabond", publisher="Kodansha",
        series="Vagabond", slug="vagabond",
        volume="Vagabond", volume_number=1, start_year=1998,
        item_number="1", title="Vagabond, Vol. 1",
        synopsis="The story of Miyamoto Musashi's journey to become Japan's greatest swordsman.",
        release_date=date(1999, 3, 24), page_count=240,
        editions=[
            SeedEdition(title="Viz English", fmt="Tankōbon", publisher="Viz Media", language="en", release_date=date(2002, 4, 2),
                        variants=[SeedVariant(name="Tankōbon", variant_type="physical", cover_price_cents=995, currency="USD")]),
            SeedEdition(title="VizBig Edition", fmt="Omnibus", publisher="Viz Media", language="en", release_date=date(2008, 9, 16),
                        variants=[SeedVariant(name="VizBig", variant_type="physical", cover_price_cents=1999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.manga, franchise="One Piece", publisher="Shueisha",
        series="One Piece", slug="one-piece",
        volume="One Piece", volume_number=1, start_year=1997,
        item_number="1", title="One Piece, Vol. 1",
        synopsis="Monkey D. Luffy sets out to become King of the Pirates.",
        release_date=date(1997, 12, 24), page_count=208,
    ),
    SeedEntry(
        kind=ItemKind.manga, franchise="Vinland Saga", publisher="Kodansha",
        series="Vinland Saga", slug="vinland-saga",
        volume="Vinland Saga", volume_number=1, start_year=2005,
        item_number="1", title="Vinland Saga, Vol. 1",
        synopsis="Young Thorfinn vows revenge against the Viking leader who killed his father.",
        release_date=date(2005, 7, 15), page_count=460,
        editions=[
            SeedEdition(title="Kodansha English", fmt="Hardcover", publisher="Kodansha Comics", language="en", release_date=date(2013, 10, 15),
                        isbn="9781612624204",
                        variants=[SeedVariant(name="Hardcover", variant_type="physical", cover_price_cents=1999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.manga, franchise="Monster", publisher="Shogakukan",
        series="Monster", slug="monster-manga",
        volume="Monster", volume_number=1, start_year=1994,
        item_number="1", title="Monster, Vol. 1",
        synopsis="A Japanese surgeon living in Germany discovers the boy whose life he saved has grown up to become a serial killer.",
        release_date=date(1995, 6, 18), page_count=232,
    ),
    SeedEntry(
        kind=ItemKind.manga, franchise="Pluto", publisher="Shogakukan",
        series="Pluto", slug="pluto",
        volume="Pluto", volume_number=1, start_year=2003,
        item_number="1", title="Pluto, Vol. 1",
        synopsis="A retelling of Astro Boy's 'Greatest Robot on Earth' arc as a murder mystery.",
        release_date=date(2004, 9, 30), page_count=200,
    ),
    SeedEntry(
        kind=ItemKind.manga, franchise="Chainsaw Man", publisher="Shueisha",
        series="Chainsaw Man", slug="chainsaw-man",
        volume="Chainsaw Man", volume_number=1, start_year=2018,
        item_number="1", title="Chainsaw Man, Vol. 1",
        synopsis="Denji, a poor young man, merges with his chainsaw devil pet to become Chainsaw Man.",
        release_date=date(2019, 3, 4), page_count=192,
        editions=[
            SeedEdition(title="Viz English", fmt="Tankōbon", publisher="Viz Media", language="en", release_date=date(2020, 10, 6),
                        isbn="9781974709939",
                        variants=[SeedVariant(name="Tankōbon", variant_type="physical", cover_price_cents=999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.manga, franchise="20th Century Boys", publisher="Shogakukan",
        series="20th Century Boys", slug="20th-century-boys",
        volume="20th Century Boys", volume_number=1, start_year=1999,
        item_number="1", title="20th Century Boys, Vol. 1",
        synopsis="A group of childhood friends discover their old fantasy stories are being used as a blueprint for world destruction.",
        release_date=date(2000, 1, 1), page_count=216,
    ),
    SeedEntry(
        kind=ItemKind.manga, franchise="Slam Dunk", publisher="Shueisha",
        series="Slam Dunk", slug="slam-dunk",
        volume="Slam Dunk", volume_number=1, start_year=1990,
        item_number="1", title="Slam Dunk, Vol. 1",
        synopsis="A delinquent named Hanamichi Sakuragi joins his school's basketball team to impress a girl.",
        release_date=date(1991, 2, 8), page_count=192,
    ),
]

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
        metadata_json={"track_count": 12},
        editions=[
            SeedEdition(title="CD", fmt="CD", publisher="Parlophone", release_date=date(1997, 6, 16),
                        variants=[SeedVariant(name="CD", variant_type="physical", cover_price_cents=1399, currency="USD")]),
            SeedEdition(title="Vinyl LP", fmt="Vinyl", publisher="Parlophone", release_date=date(1997, 6, 16),
                        variants=[SeedVariant(name="LP", variant_type="physical", cover_price_cents=2499, currency="USD")]),
            SeedEdition(title="OKNOTOK Deluxe", fmt="Vinyl Box Set", publisher="XL Recordings", release_date=date(2017, 6, 23),
                        variants=[SeedVariant(name="Deluxe Box", variant_type="physical", cover_price_cents=12999, currency="USD")]),
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
        metadata_json={"track_count": 10},
        editions=[
            SeedEdition(title="Vinyl LP", fmt="Vinyl", publisher="Harvest", release_date=date(1973, 3, 1),
                        variants=[SeedVariant(name="Original LP", variant_type="physical")]),
            SeedEdition(title="SACD", fmt="SACD", publisher="EMI", release_date=date(2003, 3, 24),
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
        metadata_json={"track_count": 12},
        editions=[
            SeedEdition(title="Deluxe CD", fmt="CD", publisher="Interscope", release_date=date(2012, 10, 22),
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
    ),
    SeedEntry(
        kind=ItemKind.music, franchise="Daft Punk", publisher="Virgin",
        series="Daft Punk", slug="daft-punk",
        volume="Daft Punk", volume_number=1, start_year=1997,
        item_number="3", title="Discovery",
        synopsis="A landmark electronic album blending house music with pop, funk, and disco influences.",
        release_date=date(2001, 3, 12),
        metadata_json={"track_count": 14},
        editions=[
            SeedEdition(title="Vinyl LP", fmt="Vinyl", publisher="Virgin", release_date=date(2001, 3, 12),
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
        metadata_json={"track_count": 5},
        editions=[
            SeedEdition(title="Original LP", fmt="Vinyl", publisher="Columbia", release_date=date(1959, 8, 17),
                        variants=[SeedVariant(name="Mono LP", variant_type="physical")]),
            SeedEdition(title="Legacy Edition CD", fmt="CD", publisher="Columbia/Legacy", release_date=date(2009, 9, 29),
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
        metadata_json={"track_count": 10},
    ),
    SeedEntry(
        kind=ItemKind.music, franchise="Massive Attack", publisher="Wild Bunch / Virgin",
        series="Massive Attack", slug="massive-attack",
        volume="Massive Attack", volume_number=1, start_year=1991,
        item_number="3", title="Mezzanine",
        synopsis="A dark, brooding trip-hop masterpiece featuring Teardrop and Angel.",
        release_date=date(1998, 4, 20),
        metadata_json={"track_count": 11},
        editions=[
            SeedEdition(title="Vinyl LP", fmt="Vinyl", publisher="Virgin", release_date=date(1998, 4, 20),
                        variants=[SeedVariant(name="2xLP", variant_type="physical")]),
            SeedEdition(title="Deluxe Remaster CD", fmt="CD", publisher="Virgin", release_date=date(2019, 2, 1),
                        variants=[SeedVariant(name="2xCD Deluxe", variant_type="physical", cover_price_cents=1699, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.music, franchise="Portishead", publisher="Go! Beat",
        series="Portishead", slug="portishead",
        volume="Portishead", volume_number=1, start_year=1994,
        item_number="1", title="Dummy",
        synopsis="The definitive trip-hop debut, fusing hip-hop beats with cinematic string arrangements.",
        release_date=date(1994, 8, 22),
        metadata_json={"track_count": 11},
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
        editions=[
            SeedEdition(title="Standard PC", fmt="PC", publisher="CD Projekt Red", release_date=date(2015, 5, 19),
                        variants=[SeedVariant(name="PC", variant_type="physical", platform="PC")]),
            SeedEdition(title="Complete Edition Switch", fmt="Switch", publisher="CD Projekt Red", release_date=date(2019, 10, 15),
                        variants=[SeedVariant(name="Switch", variant_type="physical", platform="Switch", cover_price_cents=5999, currency="USD")]),
            SeedEdition(title="GOTY PS4", fmt="PS4", publisher="CD Projekt Red", release_date=date(2016, 8, 30),
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
        editions=[
            SeedEdition(title="Remastered PS4", fmt="PS4", publisher="Bandai Namco", release_date=date(2018, 5, 25),
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
    ),
    SeedEntry(
        kind=ItemKind.game, franchise="Elden Ring", publisher="FromSoftware",
        series="Elden Ring", slug="elden-ring",
        volume="Elden Ring", volume_number=1, start_year=2022,
        item_number="1", title="Elden Ring",
        synopsis="An open-world action RPG set in the Lands Between, created with George R. R. Martin.",
        release_date=date(2022, 2, 25), metadata_json={"platforms": ["PC", "PS5", "PS4", "Xbox Series", "Xbox One"]},
        editions=[
            SeedEdition(title="Standard PS5", fmt="PS5", publisher="Bandai Namco", release_date=date(2022, 2, 25),
                        variants=[SeedVariant(name="PS5", variant_type="physical", platform="PS5", cover_price_cents=5999, currency="USD")]),
            SeedEdition(title="Collector's Edition", fmt="PS5", publisher="Bandai Namco", release_date=date(2022, 2, 25),
                        variants=[SeedVariant(name="Collector PS5", variant_type="physical", platform="PS5", cover_price_cents=18999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.game, franchise="Hollow Knight", publisher="Team Cherry",
        series="Hollow Knight", slug="hollow-knight",
        volume="Hollow Knight", volume_number=1, start_year=2017,
        item_number="1", title="Hollow Knight",
        synopsis="A 2D metroidvania through a vast underground kingdom of insects and heroes.",
        release_date=date(2017, 2, 24), metadata_json={"platforms": ["PC", "PS4", "Xbox One", "Switch"]},
    ),
    SeedEntry(
        kind=ItemKind.game, franchise="Disco Elysium", publisher="ZA/UM",
        series="Disco Elysium", slug="disco-elysium",
        volume="Disco Elysium", volume_number=1, start_year=2019,
        item_number="1", title="Disco Elysium",
        synopsis="An amnesiac detective solves a murder in a city torn by political conflict.",
        release_date=date(2019, 10, 15), metadata_json={"platforms": ["PC", "PS5", "PS4", "Xbox Series", "Switch"]},
        editions=[
            SeedEdition(title="The Final Cut PC", fmt="PC", publisher="ZA/UM", release_date=date(2021, 3, 30),
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
    ),
    SeedEntry(
        kind=ItemKind.game, franchise="Outer Wilds", publisher="Mobius Digital",
        series="Outer Wilds", slug="outer-wilds",
        volume="Outer Wilds", volume_number=1, start_year=2019,
        item_number="1", title="Outer Wilds",
        synopsis="An astronaut explores a solar system stuck in a time loop, uncovering the secrets of an ancient civilization.",
        release_date=date(2019, 5, 28), metadata_json={"platforms": ["PC", "PS4", "Xbox One"]},
    ),
    SeedEntry(
        kind=ItemKind.game, franchise="Baldur's Gate", publisher="Larian Studios",
        series="Baldur's Gate", slug="baldurs-gate",
        volume="Baldur's Gate", volume_number=1, start_year=1998,
        item_number="3", title="Baldur's Gate 3",
        synopsis="A party-based RPG set in the Forgotten Realms, featuring a story of parasitic mind flayers.",
        release_date=date(2023, 8, 3), metadata_json={"platforms": ["PC", "PS5", "Xbox Series"]},
        editions=[
            SeedEdition(title="Standard PC", fmt="PC", publisher="Larian Studios", release_date=date(2023, 8, 3),
                        variants=[SeedVariant(name="PC", variant_type="digital", platform="PC")]),
            SeedEdition(title="Deluxe PS5", fmt="PS5", publisher="Larian Studios", release_date=date(2023, 9, 6),
                        variants=[SeedVariant(name="Deluxe PS5", variant_type="physical", platform="PS5", cover_price_cents=7999, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.game, franchise="Celeste", publisher="Matt Makes Games",
        series="Celeste", slug="celeste",
        volume="Celeste", volume_number=1, start_year=2018,
        item_number="1", title="Celeste",
        synopsis="A young woman named Madeline climbs Celeste Mountain while battling her inner demons.",
        release_date=date(2018, 1, 25), metadata_json={"platforms": ["PC", "PS4", "Xbox One", "Switch"]},
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
        editions=[
            SeedEdition(title="2nd Printing", fmt="Board Game", publisher="Cephalofair Games", release_date=date(2017, 10, 1),
                        variants=[SeedVariant(name="Standard", variant_type="physical", cover_price_cents=14000, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.boardgame, franchise="Gloomhaven", publisher="Cephalofair Games",
        series="Gloomhaven", slug="gloomhaven",
        volume="Gloomhaven", volume_number=1, start_year=2017,
        item_number="2", title="Gloomhaven: Jaws of the Lion",
        synopsis="A standalone prequel to Gloomhaven with simplified rules and a built-in tutorial.",
        release_date=date(2020, 6, 18),
    ),
    SeedEntry(
        kind=ItemKind.boardgame, franchise="Wingspan", publisher="Stonemaier Games",
        series="Wingspan", slug="wingspan",
        volume="Wingspan", volume_number=1, start_year=2019,
        item_number="1", title="Wingspan",
        synopsis="A competitive bird-collection engine-building board game for nature enthusiasts.",
        release_date=date(2019, 3, 8),
        editions=[
            SeedEdition(title="Core Game", fmt="Board Game", publisher="Stonemaier Games", release_date=date(2019, 3, 8),
                        variants=[SeedVariant(name="Standard", variant_type="physical", cover_price_cents=6500, currency="USD")]),
            SeedEdition(title="Nesting Box", fmt="Board Game Collector", publisher="Stonemaier Games", release_date=date(2020, 1, 1),
                        variants=[SeedVariant(name="Collector Box", variant_type="physical", cover_price_cents=8500, currency="USD")]),
        ],
    ),
    SeedEntry(
        kind=ItemKind.boardgame, franchise="Pandemic", publisher="Z-Man Games",
        series="Pandemic", slug="pandemic",
        volume="Pandemic", volume_number=1, start_year=2008,
        item_number="1", title="Pandemic",
        synopsis="A cooperative game where players work together to stop global outbreaks and find cures.",
        release_date=date(2008, 1, 1),
    ),
    SeedEntry(
        kind=ItemKind.boardgame, franchise="Pandemic", publisher="Z-Man Games",
        series="Pandemic", slug="pandemic",
        volume="Pandemic", volume_number=1, start_year=2008,
        item_number="2", title="Pandemic Legacy: Season 1",
        synopsis="A legacy-style Pandemic where each game permanently alters the board and rules.",
        release_date=date(2015, 10, 8),
    ),
    SeedEntry(
        kind=ItemKind.boardgame, franchise="Terraforming Mars", publisher="FryxGames",
        series="Terraforming Mars", slug="terraforming-mars",
        volume="Terraforming Mars", volume_number=1, start_year=2016,
        item_number="1", title="Terraforming Mars",
        synopsis="Corporations compete to terraform Mars by raising temperature, oxygen, and ocean coverage.",
        release_date=date(2016, 10, 1),
        editions=[
            SeedEdition(title="Standard", fmt="Board Game", publisher="Stronghold Games", release_date=date(2016, 10, 1),
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
    ),
    SeedEntry(
        kind=ItemKind.boardgame, franchise="Root", publisher="Leder Games",
        series="Root", slug="root",
        volume="Root", volume_number=1, start_year=2018,
        item_number="1", title="Root",
        synopsis="An asymmetric war game where woodland factions battle for control of a vast forest.",
        release_date=date(2018, 8, 1),
        editions=[
            SeedEdition(title="Standard", fmt="Board Game", publisher="Leder Games", release_date=date(2018, 8, 1),
                        variants=[SeedVariant(name="Standard", variant_type="physical", cover_price_cents=6000, currency="USD")]),
            SeedEdition(title="Marauder Expansion", fmt="Expansion", publisher="Leder Games", release_date=date(2022, 7, 1),
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
    ),
    SeedEntry(
        kind=ItemKind.boardgame, franchise="Scythe", publisher="Stonemaier Games",
        series="Scythe", slug="scythe",
        volume="Scythe", volume_number=1, start_year=2016,
        item_number="1", title="Scythe",
        synopsis="An alternate-history 1920s strategy game featuring mechs and farming in Eastern Europe.",
        release_date=date(2016, 8, 18),
        editions=[
            SeedEdition(title="Standard", fmt="Board Game", publisher="Stonemaier Games", release_date=date(2016, 8, 18),
                        variants=[SeedVariant(name="Standard", variant_type="physical", cover_price_cents=8000, currency="USD")]),
            SeedEdition(title="Collector's Edition", fmt="Board Game Collector", publisher="Stonemaier Games", release_date=date(2016, 8, 18),
                        variants=[SeedVariant(name="Collector", variant_type="physical", cover_price_cents=16500, currency="USD")]),
        ],
    ),
]

# ===================================================================
#  Collect all entries
# ===================================================================
ALL_SEED_ENTRIES: list[SeedEntry] = (
    SEED_MOVIES + SEED_TV + SEED_ANIME + SEED_BOOKS
    + SEED_MANGA + SEED_MUSIC + SEED_GAMES + SEED_BOARDGAMES
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
            )
            db.add(edition)
            await db.flush()
        else:
            edition.format = ed_def.fmt
            edition.publisher = ed_def.publisher or entry.publisher
            edition.language = ed_def.language
            edition.region = ed_def.region
            edition.release_date = ed_def.release_date or entry.release_date

        for var_def in ed_def.variants:
            result = await db.execute(
                select(Variant).where(
                    Variant.edition_id == edition.id,
                    Variant.name == var_def.name,
                )
            )
            variant = result.scalar_one_or_none()
            if variant is None:
                db.add(Variant(
                    edition=edition,
                    name=var_def.name,
                    variant_type=var_def.variant_type,
                    barcode=var_def.barcode,
                    is_primary=var_def.is_primary,
                    cover_price_cents=var_def.cover_price_cents,
                    currency=var_def.currency,
                    platform=var_def.platform,
                    metadata_json=var_def.metadata_json,
                ))


async def _ensure_provider_id(db, entry: SeedEntry, item: Item) -> None:
    result = await db.execute(
        select(ExternalProviderId).where(
            ExternalProviderId.provider == entry.provider,
            ExternalProviderId.provider_item_id == entry.provider_id,
        )
    )
    if result.scalar_one_or_none() is not None:
        return
    db.add(ExternalProviderId(
        provider=entry.provider,
        provider_item_id=entry.provider_id,
        entity_type="item",
        entity_id=item.id,
    ))


# ---------------------------------------------------------------------------
#  Main seed function
# ---------------------------------------------------------------------------
async def seed() -> None:
    async with AsyncSessionLocal() as db:
        franchises: dict[str, Franchise] = {}
        series_by_slug: dict[str, Series] = {}
        volumes_by_name: dict[str, Volume] = {}

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

        await db.commit()
        print(f"Seeded {len(ALL_SEED_ENTRIES)} items across all library types.")


if __name__ == "__main__":
    asyncio.run(seed())
