from uuid import uuid4

from app.models.catalog_music_item import MusicItem
from app.search.documents import music_item_search_document


def _music_item(*, release_date=None, original_release_date=None) -> MusicItem:
    return MusicItem(
        id=uuid4(),
        title="Deluxe Edition",
        artist_credits=[],
        release_date=release_date,
        original_release_date=original_release_date,
        genres=[],
        extra=[],
        credits=[],
        external_links=[],
        discs=[
            {
                "id": uuid4(),
                "disc_number": 1,
                "sound_types": [],
                "recording_date": {"year": 2025},
                "recording_locations": [],
                "credits": [],
                "tracks": [],
            }
        ],
    )


def test_disc_recording_date_does_not_fill_edition_release_date():
    document = music_item_search_document(_music_item())

    assert document["release_date"] is None
    assert document["release_year"] is None


def test_root_edition_release_date_remains_search_date_with_recording_dates():
    document = music_item_search_document(
        _music_item(release_date={"year": 1997, "month": 5, "day": 21})
    )

    assert document["release_date"] == "1997-05-21"
    assert document["release_year"] == 1997
