"""Configuration shared by the Cineo scraper."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOP_250_URL = "https://www.imdb.com/chart/top/"
EXPECTED_MOVIE_COUNT = 250
REQUEST_TIMEOUT_SECONDS = 20
RETRY_COUNT = 3
RETRY_DELAY_SECONDS = 3
SCROLL_DELAY_SECONDS = 0.4
DETAIL_DELAY_SECONDS = 1.2

SELECTORS = {
    "movie_card": "li.ipc-metadata-list-summary-item",
    "title": "h3.ipc-title__text, h3, [data-testid='title']",
    "year": "span.cli-title-metadata-item",
    "year_fallback": "span",
    "rating": "span.ipc-rating-star--rating",
    "rating_container": "span.ipc-rating-star",
    "link": "a.ipc-title-link-wrapper",
    "json_ld": 'script[type="application/ld+json"]',
    "consent_buttons": (
        'button[data-testid="accept-button"]',
        'button[aria-label*="Accept"]',
    ),
}

DETAIL_SELECTORS = {
    "json_ld": SELECTORS["json_ld"],
}

DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"
LATEST_CSV = DATA_DIR / "latest.csv"
