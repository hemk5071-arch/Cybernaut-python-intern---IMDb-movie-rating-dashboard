"""Cineo command-line entry point."""

import argparse
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

import pandas as pd
from dotenv import load_dotenv

from scraper import config
from scraper.parser import MOVIE_COLUMNS, validate_movies
from scraper.scraper import scrape_movies


def _positive_limit(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("limit must be an integer") from error
    if not 1 <= limit <= config.EXPECTED_MOVIE_COUNT:
        raise argparse.ArgumentTypeError("limit must be between 1 and 250")
    return limit


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape and export the IMDb Top 250 movies."
    )
    headless_group = parser.add_mutually_exclusive_group()
    headless_group.add_argument(
        "--headless", dest="headless", action="store_true", help="Run Chrome headlessly."
    )
    headless_group.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Show the Chrome browser window.",
    )
    parser.set_defaults(headless=True)
    parser.add_argument(
        "--limit",
        type=_positive_limit,
        help="Scrape only the first N movies (1-250).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the main CSV to this path instead of the dated default.",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Visit movie pages to collect genre, director, cast, and runtime.",
    )
    return parser


def _configure_logging() -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(config.LOG_DIR / "cineo.log", encoding="utf-8"),
        ],
        force=True,
    )


def _print_rating_changes(
    previous: pd.DataFrame | None, current: pd.DataFrame
) -> None:
    if previous is None:
        print("\nNo previous latest.csv found; rating comparison skipped.")
        return
    needed = {"rank", "title", "imdb_rating"}
    if not needed.issubset(previous.columns):
        logging.getLogger(__name__).warning(
            "Previous CSV is missing comparison columns; rating comparison skipped."
        )
        return
    current_comparable = current[["rank", "title", "imdb_rating"]].copy()
    previous_comparable = previous[["rank", "title", "imdb_rating"]].copy()
    for frame in (current_comparable, previous_comparable):
        frame["rank"] = pd.to_numeric(frame["rank"], errors="coerce")
        frame["title"] = frame["title"].astype("string")
        frame.dropna(subset=["rank", "title"], inplace=True)
    if previous_comparable.empty or current_comparable.empty:
        logging.getLogger(__name__).warning(
            "No comparable ranked titles in the previous or current CSV."
        )
        print("\nNo comparable ranked titles; rating comparison skipped.")
        return
    comparison = current_comparable.merge(
        previous_comparable,
        on=["rank", "title"],
        how="inner",
        suffixes=("_current", "_previous"),
    )
    comparison["change"] = (
        comparison["imdb_rating_current"] - comparison["imdb_rating_previous"]
    )
    changed = comparison[comparison["change"].fillna(0).ne(0)]
    print(f"\nRating changes vs previous run: {len(changed)}")
    if not changed.empty:
        display = changed.rename(
            columns={
                "imdb_rating_previous": "previous",
                "imdb_rating_current": "current",
                "change": "change",
            }
        )
        print(
            display[["rank", "title", "previous", "current", "change"]]
            .sort_values("rank")
            .to_string(index=False, formatters={"change": "{:+.1f}".format})
        )


def run(args: argparse.Namespace) -> int:
    _configure_logging()
    logger = logging.getLogger(__name__)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    previous = (
        pd.read_csv(config.LATEST_CSV)
        if config.LATEST_CSV.is_file()
        else None
    )
    logger.info("Starting Cineo scrape.")
    records = scrape_movies(
        headless=args.headless, limit=args.limit, details=args.details
    )
    expected_count = args.limit or config.EXPECTED_MOVIE_COUNT
    frame = validate_movies(records, expected_count=expected_count)
    columns = [column for column in MOVIE_COLUMNS if column in frame.columns]
    columns.extend(
        column
        for column in ("genre", "director", "top_cast", "runtime")
        if column in frame.columns
    )
    frame = frame[columns]

    dated_path = config.DATA_DIR / f"movies_{date.today().isoformat()}.csv"
    output_path = args.output.expanduser() if args.output else dated_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False, encoding="utf-8")
    frame.to_csv(config.LATEST_CSV, index=False, encoding="utf-8")
    logger.info("Saved %d movies to %s and %s.", len(frame), output_path, config.LATEST_CSV)

    print("\nCineo - IMDb Top 250")
    print(
        frame.head(10)[["rank", "title", "year", "imdb_rating", "votes"]]
        .to_string(index=False)
    )
    _print_rating_changes(previous, frame)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except Exception:
        logging.getLogger(__name__).exception("Cineo scrape failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
