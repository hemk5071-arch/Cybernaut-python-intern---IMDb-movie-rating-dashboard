"""Tests for merging structured IMDb fields into card records."""

from scraper.scraper import _enrich_with_json_ld


def test_json_ld_fills_missing_card_fields() -> None:
    cards = [
        {
            "rank": 1,
            "title": "The Shawshank Redemption",
            "year": None,
            "movie_url": "https://www.imdb.com/title/tt0111161/?ref_=chart",
        }
    ]
    structured = [
        {
            "rank": 1,
            "title": "The Shawshank Redemption",
            "year": "1994",
            "votes": 3_000_000,
            "movie_url": "https://www.imdb.com/title/tt0111161/",
        }
    ]

    enriched = _enrich_with_json_ld(cards, structured)

    assert enriched[0]["year"] == "1994"
    assert enriched[0]["votes"] == 3_000_000
    assert enriched[0]["movie_url"].endswith("?ref_=chart")
