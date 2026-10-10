"""IMDb Top 250 page scraper."""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from scraper import config
from scraper.driver import get_driver
from scraper.parser import parse_year, parse_votes, split_rank_title

LOGGER = logging.getLogger(__name__)


def _text(element: Any) -> str | None:
    try:
        value = element.text.strip()
        if not value:
            value = (element.get_attribute("textContent") or "").strip()
    except (AttributeError, WebDriverException):
        return None
    return value or None


def _attribute(element: Any, name: str) -> str | None:
    try:
        return element.get_attribute(name)
    except (AttributeError, WebDriverException):
        return None


def _script_content(element: Any) -> str | None:
    return _attribute(element, "textContent") or _text(element)


def _dismiss_consent(driver: Any) -> None:
    for selector in config.SELECTORS["consent_buttons"]:
        try:
            buttons = driver.find_elements(By.CSS_SELECTOR, selector)
            if buttons and buttons[0].is_displayed():
                buttons[0].click()
                LOGGER.info("Dismissed IMDb consent prompt.")
                return
        except WebDriverException:
            continue


def _scroll_until_loaded(driver: Any, target_count: int) -> None:
    previous_count = -1
    unchanged_rounds = 0
    while unchanged_rounds < 4:
        cards = driver.find_elements(
            By.CSS_SELECTOR, config.SELECTORS["movie_card"]
        )
        count = len(cards)
        if count >= target_count:
            break
        if count != previous_count:
            LOGGER.info("Scraped %d/%d movie cards.", min(count, target_count), target_count)
            unchanged_rounds = 0
        else:
            unchanged_rounds += 1
        previous_count = count
        driver.execute_script(
            "window.scrollBy(0, Math.max(window.innerHeight * 0.8, 600));"
        )
        try:
            WebDriverWait(driver, config.SCROLL_DELAY_SECONDS + 1).until(
                lambda current: len(
                    current.find_elements(
                        By.CSS_SELECTOR, config.SELECTORS["movie_card"]
                    )
                )
                > count
            )
        except TimeoutException:
            time.sleep(config.SCROLL_DELAY_SECONDS)


def _json_ld_objects(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for entry in value for item in _json_ld_objects(entry)]
    if not isinstance(value, dict):
        return []
    objects = [value]
    graph = value.get("@graph")
    if graph:
        objects.extend(_json_ld_objects(graph))
    return objects


def _extract_json_ld(driver: Any) -> list[dict[str, Any]]:
    movies: list[dict[str, Any]] = []
    scripts = driver.find_elements(
        By.CSS_SELECTOR, config.SELECTORS["json_ld"]
    )
    for script in scripts:
        raw = _script_content(script)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            LOGGER.debug("Skipping malformed IMDb JSON-LD.")
            continue
        for item_list in _json_ld_objects(payload):
            if item_list.get("@type") not in ("ItemList", ["ItemList"]):
                continue
            for entry in item_list.get("itemListElement", []):
                if not isinstance(entry, dict):
                    continue
                item = entry.get("item", entry)
                if not isinstance(item, dict):
                    continue
                aggregate = item.get("aggregateRating") or {}
                rank = entry.get("position")
                name = item.get("name")
                if rank is None and name:
                    rank, name = split_rank_title(name)
                movies.append(
                    {
                        "rank": rank,
                        "title": name,
                        "year": item.get("datePublished"),
                        "imdb_rating": aggregate.get("ratingValue"),
                        "votes": aggregate.get("ratingCount"),
                        "movie_url": item.get("url") or entry.get("url"),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
    return movies


def _extract_cards(driver: Any) -> list[dict[str, Any]]:
    cards = driver.find_elements(
        By.CSS_SELECTOR, config.SELECTORS["movie_card"]
    )
    scraped_at = datetime.now(timezone.utc).isoformat()
    movies = []
    for position, card in enumerate(cards, start=1):
        card_text = _text(card) or ""
        try:
            title_element = card.find_element(
                By.CSS_SELECTOR, config.SELECTORS["title"]
            )
            title_label = _text(title_element)
        except NoSuchElementException:
            title_label = None
        if not title_label:
            try:
                title_link = card.find_element(
                    By.CSS_SELECTOR, config.SELECTORS["link"]
                )
                title_label = (
                    _text(title_link) or _attribute(title_link, "aria-label")
                )
            except NoSuchElementException:
                title_label = None
        if not title_label:
            for line in card_text.splitlines():
                parsed_rank, parsed_title = split_rank_title(line)
                if parsed_rank is not None and parsed_title:
                    title_label = line
                    break
        rank, title = split_rank_title(title_label)
        rank = rank or position

        try:
            year_elements = card.find_elements(
                By.CSS_SELECTOR, config.SELECTORS["year"]
            )
        except WebDriverException:
            year_elements = []
        year = next(
            (
                parsed_year
                for element in year_elements
                if (parsed_year := parse_year(_text(element))) is not None
            ),
            None,
        )
        if year is None:
            try:
                year_elements = card.find_elements(
                    By.CSS_SELECTOR, config.SELECTORS["year_fallback"]
                )
            except WebDriverException:
                year_elements = []
            year = next(
                (
                    parsed_year
                    for element in year_elements
                    if (parsed_year := parse_year(_text(element))) is not None
                ),
                None,
            )
        if year is None:
            year = card_text
        try:
            rating_element = card.find_element(
                By.CSS_SELECTOR, config.SELECTORS["rating"]
            )
            rating = _text(rating_element)
        except NoSuchElementException:
            rating = None
        try:
            rating_container = card.find_element(
                By.CSS_SELECTOR, config.SELECTORS["rating_container"]
            )
            rating_label = _attribute(rating_container, "aria-label")
        except NoSuchElementException:
            rating_label = None
        votes = parse_votes(rating_label) if rating_label else None
        try:
            link_element = card.find_element(
                By.CSS_SELECTOR, config.SELECTORS["link"]
            )
            movie_url = _attribute(link_element, "href")
        except NoSuchElementException:
            movie_url = None
        movies.append(
            {
                "rank": rank,
                "title": title,
                "year": year,
                "imdb_rating": rating,
                "votes": votes,
                "movie_url": movie_url,
                "scraped_at": scraped_at,
            }
        )
    return movies


def _enrich_with_json_ld(
    movies: list[dict[str, Any]], structured_movies: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Fill missing card fields from matching structured movie records."""
    by_rank = {
        str(movie.get("rank")): movie
        for movie in structured_movies
        if movie.get("rank") is not None
    }
    by_url = {
        movie.get("movie_url", "").split("?")[0]: movie
        for movie in structured_movies
        if movie.get("movie_url")
    }
    for movie in movies:
        structured = by_rank.get(str(movie.get("rank")))
        if structured is None and movie.get("movie_url"):
            structured = by_url.get(movie["movie_url"].split("?")[0])
        if structured is None:
            continue
        for field, value in structured.items():
            if movie.get(field) is None and value is not None:
                movie[field] = value
    return movies


def _scrape_details(driver: Any, movie: dict[str, Any]) -> dict[str, Any]:
    details = {"genre": None, "director": None, "top_cast": None, "runtime": None}
    url = movie.get("movie_url")
    if not url:
        return details
    try:
        driver.get(url)
        WebDriverWait(driver, config.REQUEST_TIMEOUT_SECONDS).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, config.DETAIL_SELECTORS["json_ld"])
            )
        )
    except TimeoutException:
        LOGGER.warning("Timed out loading details for %s.", movie.get("title"))
        return details
    finally:
        time.sleep(config.DETAIL_DELAY_SECONDS)

    for payload in _page_json_ld(driver):
        if payload.get("@type") not in ("Movie", ["Movie"]):
            continue
        director = payload.get("director")
        actors = payload.get("actor")
        details["genre"] = payload.get("genre")
        details["director"] = (
            director.get("name")
            if isinstance(director, dict)
            else ", ".join(
                person.get("name", "") for person in director or []
            )
            if isinstance(director, list)
            else director
        )
        details["top_cast"] = ", ".join(
            person.get("name", "") for person in actors or []
        ) if isinstance(actors, list) else actors
        details["runtime"] = payload.get("duration")
        break
    return details


def _page_json_ld(driver: Any) -> list[dict[str, Any]]:
    payloads = []
    for script in driver.find_elements(
        By.CSS_SELECTOR, config.DETAIL_SELECTORS["json_ld"]
    ):
        raw = _script_content(script)
        if not raw:
            continue
        try:
            payloads.extend(_json_ld_objects(json.loads(raw)))
        except json.JSONDecodeError:
            LOGGER.debug("Skipping malformed detail JSON-LD.")
    return payloads


def scrape_movies(
    headless: bool = True, limit: int | None = None, details: bool = False
) -> list[dict[str, Any]]:
    """Scrape movie records, retrying page loads and always closing Chrome."""
    target_count = min(limit, config.EXPECTED_MOVIE_COUNT) if limit else config.EXPECTED_MOVIE_COUNT
    last_error: Exception | None = None
    for attempt in range(1, config.RETRY_COUNT + 1):
        driver = None
        try:
            LOGGER.info("Starting IMDb scrape attempt %d/%d.", attempt, config.RETRY_COUNT)
            driver = get_driver(headless=headless)
            driver.set_page_load_timeout(config.REQUEST_TIMEOUT_SECONDS)
            driver.get(config.TOP_250_URL)
            _dismiss_consent(driver)
            try:
                WebDriverWait(driver, config.REQUEST_TIMEOUT_SECONDS).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, config.SELECTORS["movie_card"])
                    )
                )
            except TimeoutException:
                LOGGER.warning("Movie cards did not appear; trying JSON-LD data.")
            _scroll_until_loaded(driver, target_count)
            movies = _extract_cards(driver)
            structured_movies = _extract_json_ld(driver)
            if len(structured_movies) > len(movies):
                movies = structured_movies
            else:
                movies = _enrich_with_json_ld(movies, structured_movies)
            movies = movies[:target_count]
            if len(movies) != target_count:
                raise RuntimeError(
                    f"Expected {target_count} movies, received {len(movies)}."
                )
            missing_years = sum(movie.get("year") is None for movie in movies)
            if missing_years:
                LOGGER.warning(
                    "IMDb did not expose year metadata for %d/%d movies; "
                    "year fields will be blank.",
                    missing_years,
                    len(movies),
                )
            if details:
                for index, movie in enumerate(movies, start=1):
                    movie.update(_scrape_details(driver, movie))
                    if index % 10 == 0 or index == len(movies):
                        LOGGER.info("Scraped details for %d/%d movies.", index, len(movies))
            if not movies:
                raise RuntimeError("IMDb returned no movie records.")
            LOGGER.info("Scraped %d/%d movies.", len(movies), target_count)
            return movies
        except (TimeoutException, WebDriverException, RuntimeError) as error:
            last_error = error
            LOGGER.warning(
                "Scrape attempt %d/%d failed: %s",
                attempt,
                config.RETRY_COUNT,
                error,
            )
            if attempt < config.RETRY_COUNT:
                time.sleep(config.RETRY_DELAY_SECONDS)
        finally:
            if driver is not None:
                driver.quit()
    raise RuntimeError(
        f"IMDb scrape failed after {config.RETRY_COUNT} attempts."
    ) from last_error
