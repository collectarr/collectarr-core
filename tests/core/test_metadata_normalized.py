from app.metadata_normalized import (
    NORMALIZED_SCHEMA_VERSION,
    clean_normalized_metadata,
    merge_normalized_metadata,
    normalized_metadata_issues,
)
from app.models.base import ItemKind


def test_clean_normalized_metadata_applies_kind_specific_schema() -> None:
    payload = {
        "genres": ["Action"],
        "platforms": ["PC"],
        "track_count": 10,
        "tracks": [{"title": "Theme"}],
    }

    cleaned = clean_normalized_metadata(payload, kind=ItemKind.game)

    assert cleaned == {
        "genres": ["Action"],
        "platforms": ["PC"],
        "schema_version": NORMALIZED_SCHEMA_VERSION,
    }


def test_clean_normalized_metadata_keeps_music_tracks_and_validates_shape() -> None:
    payload = {
        "track_count": 2,
        "tracks": [
            {"title": "Intro", "position": 1, "duration_seconds": 70},
            {"title": "Main Theme", "position": 2, "artist": "Various"},
        ],
        "platforms": ["Should be dropped"],
    }

    cleaned = clean_normalized_metadata(payload, kind=ItemKind.music)

    assert cleaned == {
        "track_count": 2,
        "tracks": [
            {"title": "Intro", "position": 1, "duration_seconds": 70},
            {"title": "Main Theme", "position": 2, "artist": "Various"},
        ],
        "schema_version": NORMALIZED_SCHEMA_VERSION,
    }


def test_merge_normalized_metadata_rewrites_schema_version() -> None:
    merged = merge_normalized_metadata(
        {"normalized": {"genres": ["Sci-Fi"], "schema_version": 999}},
        {"genres": ["Sci-Fi", "Drama"]},
        kind=ItemKind.movie,
    )

    assert merged["normalized"] == {
        "genres": ["Sci-Fi", "Drama"],
        "schema_version": NORMALIZED_SCHEMA_VERSION,
    }


def test_normalized_metadata_issues_reports_schema_and_unknown_keys() -> None:
    issues = normalized_metadata_issues(
        {
            "schema_version": 999,
            "track_count": 10,
            "unknown_key": "x",
        },
        kind=ItemKind.music,
    )

    assert "schema_version_mismatch" in issues
    assert "unknown_key:unknown_key" in issues
