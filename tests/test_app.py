"""Dashboard route tests using a temporary CSV instead of a live scrape."""

import pandas as pd

from app import app as app_module


def test_dashboard_filters_sorts_and_downloads_csv(tmp_path, monkeypatch) -> None:
    csv_path = tmp_path / "latest.csv"
    pd.DataFrame(
        [
            {
                "rank": 2,
                "title": "Second Film",
                "year": 2001,
                "imdb_rating": 8.5,
                "votes": 1200,
                "movie_url": "https://www.imdb.com/title/tt0000002/",
                "scraped_at": "2026-10-08T10:00:00+00:00",
            },
            {
                "rank": 1,
                "title": "First Film",
                "year": 1999,
                "imdb_rating": 9.0,
                "votes": 3100000,
                "movie_url": "https://www.imdb.com/title/tt0000001/",
                "scraped_at": "2026-10-08T10:00:00+00:00",
            },
        ]
    ).to_csv(csv_path, index=False)
    monkeypatch.setattr(app_module, "LATEST_CSV", csv_path)
    client = app_module.app.test_client()

    response = client.get("/?q=second&min_year=2000&min_rating=8.0")
    assert response.status_code == 200
    assert b"Second Film" in response.data
    assert b"1 results" in response.data

    sorted_response = client.get("/?sort=imdb_rating&order=asc")
    assert sorted_response.status_code == 200
    assert sorted_response.data.index(b">Second Film</a>") < sorted_response.data.index(
        b">First Film</a>"
    )
    download = client.get("/download")
    assert download.status_code == 200
    assert b"Second Film" in download.data
