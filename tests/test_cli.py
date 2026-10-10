"""Tests for CLI rating-history comparisons."""

import pandas as pd

from main import _print_rating_changes


def test_rating_changes_match_records_by_rank_and_title(capsys) -> None:
    previous = pd.DataFrame(
        [{"rank": 1, "title": "Film", "imdb_rating": 8.5}]
    )
    current = pd.DataFrame(
        [{"rank": 1, "title": "Film", "imdb_rating": 9.0}]
    )

    _print_rating_changes(previous, current)

    assert "Rating changes vs previous run: 1" in capsys.readouterr().out


def test_rating_comparison_skips_blank_historical_rows(capsys) -> None:
    previous = pd.DataFrame(
        [{"rank": None, "title": None, "imdb_rating": 9.0}]
    )
    current = pd.DataFrame(
        [{"rank": 1, "title": "Film", "imdb_rating": 9.0}]
    )

    _print_rating_changes(previous, current)

    assert "No comparable ranked titles" in capsys.readouterr().out
