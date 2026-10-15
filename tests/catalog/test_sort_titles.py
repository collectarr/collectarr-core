import pytest

from app.catalog.sort_titles import (
    automatic_sort_title,
    follow_title_change,
    resolve_sort_title,
)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("The Wall", "Wall, The"),
        ("A Night at the Opera", "Night at the Opera, A"),
        ("An Awesome Wave", "Awesome Wave, An"),
        ("the bends", "bends, the"),
        ("Live From The Sabaton Cruise 2014 (CD2)", "Live From The Sabaton Cruise 2014 (CD2)"),
        ("Theatre of Tragedy", "Theatre of Tragedy"),
        ("Anastasis", "Anastasis"),
        ("The", "The"),
    ],
)
def test_automatic_sort_title_moves_a_leading_article(title, expected):
    assert automatic_sort_title(title) == expected


def test_explicit_sort_title_wins():
    assert resolve_sort_title("The Wall", "Pink Floyd Wall") == "Pink Floyd Wall"
    assert resolve_sort_title("The Wall", None) == "Wall, The"
    assert resolve_sort_title("The Wall", "") == "Wall, The"


def test_automatic_sort_title_follows_title_corrections():
    assert follow_title_change("The Wal", "The Wall", "Wal, The") == "Wall, The"
    assert follow_title_change("The Wal", "The Wall", None) == "Wall, The"
    assert follow_title_change("The Wal", "The Wall", "Custom") == "Custom"
