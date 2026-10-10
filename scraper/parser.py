"""Parsing and validation helpers for IMDb movie records."""

import re
from typing import Any, Iterable

import pandas as pd

MOVIE_COLUMNS = [
    "rank",
    "title",
    "year",
    "imdb_rating",
    "votes",
    "movie_url",
    "scraped_at",
]
DETAIL_COLUMNS = ["genre", "director", "top_cast", "runtime"]
_RANK_TITLE_RE = re.compile(r"^\s*(\d+)\s*[.):\-]\s*(.*?)\s*$")
_YEAR_RE = re.compile(r"\b(18|19|20|21)\d{2}\b")
_VOTE_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*([KMB])?", re.IGNORECASE)


def split_rank_title(value: Any) -> tuple[int | None, str | None]:
    """Split a list label such as ``1. The Shawshank Redemption``."""
    if value is None:
        return None, None
    match = _RANK_TITLE_RE.match(str(value))
    if match:
        return int(match.group(1)), match.group(2).strip() or None
    title = str(value).strip()
    return None, title or None


def parse_year(value: Any) -> int | None:
    """Extract a four-digit year from a metadata label."""
    if value is None:
        return None
    match = _YEAR_RE.search(str(value))
    return int(match.group(0)) if match else None


def parse_rating(value: Any) -> float | None:
    """Convert an IMDb rating value to a float."""
    if value is None or str(value).strip() == "":
        return None
    match = re.search(r"\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group(0)) if match else None


def parse_votes(value: Any) -> int | None:
    """Convert vote counts such as ``3.1M`` or ``2,918,123`` to integers."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    matches = list(_VOTE_RE.finditer(text))
    if not matches:
        return None
    match = matches[-1]
    if not match.group(2) and "." in match.group(1):
        return None
    number = float(match.group(1).replace(",", ""))
    suffix = (match.group(2) or "").upper()
    multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(
        suffix, 1
    )
    return int(number * multiplier)


def normalize_movie(movie: dict[str, Any]) -> dict[str, Any]:
    """Normalize one scraped movie dictionary into the CSV schema."""
    rank = movie.get("rank")
    title = movie.get("title")
    parsed_rank, parsed_title = split_rank_title(title)
    if rank is None:
        rank = parsed_rank
    elif parsed_rank is not None and parsed_title:
        title = parsed_title
    return {
        "rank": int(rank) if rank is not None and str(rank).strip() else None,
        "title": str(title).strip() if title is not None else None,
        "year": parse_year(movie.get("year")),
        "imdb_rating": parse_rating(movie.get("imdb_rating")),
        "votes": parse_votes(movie.get("votes")),
        "movie_url": movie.get("movie_url"),
        "scraped_at": movie.get("scraped_at"),
        **{key: movie.get(key) for key in DETAIL_COLUMNS if key in movie},
    }


def validate_movies(
    movies: Iterable[dict[str, Any]], expected_count: int | None = 250
) -> pd.DataFrame:
    """Validate records and return a DataFrame ordered by rank."""
    rows = [normalize_movie(movie) for movie in movies]
    frame = pd.DataFrame(rows)
    for column in MOVIE_COLUMNS:
        if column not in frame:
            frame[column] = pd.Series(dtype="object")

    if expected_count is not None and len(frame) != expected_count:
        raise ValueError(
            f"Expected {expected_count} movies, received {len(frame)}."
        )
    ranks = frame["rank"].dropna()
    if ranks.duplicated().any():
        duplicates = sorted(ranks[ranks.duplicated(keep=False)].astype(int).unique())
        raise ValueError(f"Duplicate movie ranks found: {duplicates}.")
    ratings = frame["imdb_rating"].dropna()
    invalid_ratings = ratings[(ratings < 0) | (ratings > 10)]
    if not invalid_ratings.empty:
        raise ValueError("IMDb ratings must be between 0 and 10.")

    frame["rank"] = pd.to_numeric(frame["rank"], errors="coerce").astype("Int64")
    frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype("Int64")
    frame["votes"] = pd.to_numeric(frame["votes"], errors="coerce").astype("Int64")
    frame["imdb_rating"] = pd.to_numeric(
        frame["imdb_rating"], errors="coerce"
    )
    return frame.sort_values("rank", na_position="last").reset_index(drop=True)
