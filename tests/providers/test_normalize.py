"""Tests for shared provider normalization utilities."""

import pytest

from app.providers.normalize import issue_sort_key, normalize_title, title_aliases


class TestNormalizeTitle:
    def test_basic_lowercase(self):
        assert normalize_title("Batman") == "batman"

    def test_whitespace_collapse(self):
        assert normalize_title("  Batman   Returns  ") == "batman returns"

    def test_accent_stripping(self):
        assert normalize_title("Café") == "cafe"
        assert normalize_title("naïve") == "naive"
        assert normalize_title("São Paulo") == "sao paulo"

    def test_punctuation_handling(self):
        assert normalize_title("Spider-Man: Homecoming") == "spider man homecoming"

    def test_ampersand(self):
        assert normalize_title("Batman & Robin") == "batman robin"

    def test_none_value(self):
        assert normalize_title(None) == ""

    def test_empty_string(self):
        assert normalize_title("") == ""


class TestTitleAliases:
    def test_the_prefix(self):
        aliases = title_aliases("The Amazing Spider-Man")
        titles_lower = [a.lower() for a in aliases]
        assert any("the" not in t.split()[0] for t in titles_lower if t)

    def test_ampersand_and(self):
        aliases = title_aliases("Batman & Robin")
        texts = " ".join(aliases).lower()
        assert "and" in texts

    def test_deduplication(self):
        aliases = title_aliases("Batman")
        keys = [normalize_title(a) for a in aliases]
        assert len(keys) == len(set(keys))

    def test_max_five(self):
        aliases = title_aliases("The Amazing Spider-Man: Homecoming & Return")
        assert len(aliases) <= 5


class TestIssueSortKey:
    def test_numeric_ordering(self):
        keys = [issue_sort_key(str(n)) for n in [1, 2, 10, 100]]
        assert keys == sorted(keys)

    def test_decimal_issues(self):
        keys = [issue_sort_key(v) for v in ["1", "1.5", "2"]]
        assert keys == sorted(keys)

    def test_alphanumeric_suffix(self):
        keys = [issue_sort_key(v) for v in ["1", "1A", "1B", "2"]]
        assert keys == sorted(keys)

    def test_empty_value(self):
        key = issue_sort_key("")
        assert key[0] == 2  # lowest priority

    def test_none_value(self):
        key = issue_sort_key(None)
        assert key[0] == 2

    def test_non_numeric(self):
        key = issue_sort_key("Annual")
        assert key[0] == 1  # below numeric, above empty

    def test_mixed_sorting(self):
        values = ["10", "1A", "2", "Annual", "1", "1B", ""]
        sorted_values = sorted(values, key=issue_sort_key)
        # Numeric first (1, 1A, 1B, 2, 10), then non-numeric, then empty
        assert sorted_values[0] == "1"
        assert sorted_values[1] == "1A"
        assert sorted_values[2] == "1B"
        assert sorted_values[3] == "2"
        assert sorted_values[4] == "10"
