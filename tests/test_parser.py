"""Unit tests for Cineo's parsing and validation helpers."""

import pytest

from scraper.parser import (
    parse_votes,
    split_rank_title,
    validate_movies,
)


def test_split_rank_and_title() -> None:
    assert split_rank_title("1. The Shawshank Redemption") == (
        1,
        "The Shawshank Redemption",
    )
    assert split_rank_title("250: The Last Movie") == (250, "The Last Movie")
    assert split_rank_title("A movie without a rank") == (
        None,
        "A movie without a rank",
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("3.1M", 3_100_000),
        ("2.9M user ratings", 2_900_000),
        ("9.3 (based on 3.1M user ratings)", 3_100_000),
        ("1.2K", 1_200),
        ("2,918,123", 2_918_123),
        (None, None),
    ],
)
def test_parse_votes(value: str | None, expected: int | None) -> None:
    assert parse_votes(value) == expected


def test_validation_normalizes_and_sorts_rows() -> None:
    movies = [
        {
            "rank": 2,
            "title": "2. Second",
            "year": "2001",
            "imdb_rating": "8.5",
            "votes": "3.1M",
        },
        {"rank": 1, "title": "1. First", "year": "1999", "imdb_rating": "9.0"},
    ]
    frame = validate_movies(movies, expected_count=2)
    assert frame["rank"].tolist() == [1, 2]
    assert frame.loc[0, "title"] == "First"
    assert frame.loc[1, "votes"] == 3_100_000


def test_validation_rejects_wrong_count_duplicate_rank_and_bad_rating() -> None:
    with pytest.raises(ValueError, match="Expected 2 movies"):
        validate_movies([{"rank": 1}], expected_count=2)
    with pytest.raises(ValueError, match="Duplicate movie ranks"):
        validate_movies([{"rank": 1}, {"rank": 1}], expected_count=2)
    with pytest.raises(ValueError, match="between 0 and 10"):
        validate_movies(
            [{"rank": 1, "imdb_rating": 10.1}], expected_count=1
        )
