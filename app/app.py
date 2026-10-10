"""Flask dashboard for the latest Cineo movie scrape."""

from pathlib import Path

import pandas as pd
from flask import Flask, abort, render_template, request, send_file, url_for

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LATEST_CSV = PROJECT_ROOT / "data" / "latest.csv"
app = Flask(__name__)


def _load_movies() -> pd.DataFrame:
    if not LATEST_CSV.is_file():
        return pd.DataFrame(
            columns=["rank", "title", "year", "imdb_rating", "votes", "movie_url", "scraped_at"]
        )
    frame = pd.read_csv(LATEST_CSV)
    for column in ("rank", "year", "imdb_rating", "votes"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


@app.route("/")
def index():
    movies = _load_movies()
    title_query = str(request.args.get("q", "")).strip()
    min_year = request.args.get("min_year", type=int)
    max_year = request.args.get("max_year", type=int)
    min_rating = request.args.get("min_rating", type=float)
    sort_key = request.args.get("sort", "rank")
    order = request.args.get("order", "asc")

    filtered = movies.copy()
    if title_query and "title" in filtered:
        filtered = filtered[
            filtered["title"].fillna("").str.contains(title_query, case=False, regex=False)
        ]
    if min_year is not None and "year" in filtered:
        filtered = filtered[filtered["year"] >= min_year]
    if max_year is not None and "year" in filtered:
        filtered = filtered[filtered["year"] <= max_year]
    if min_rating is not None and "imdb_rating" in filtered:
        filtered = filtered[filtered["imdb_rating"] >= min_rating]

    allowed_sort = {"rank", "title", "year", "imdb_rating"}
    if sort_key not in allowed_sort or sort_key not in filtered.columns:
        sort_key = "rank"
    if order not in {"asc", "desc"}:
        order = "asc"
    filtered = filtered.sort_values(
        sort_key, ascending=order == "asc", na_position="last"
    )
    filtered = filtered.astype(object).where(pd.notna(filtered), None)

    ratings = pd.to_numeric(movies.get("imdb_rating", pd.Series(dtype=float)), errors="coerce")
    average_rating = ratings.mean()
    if not movies.empty and ratings.notna().any():
        highest_index = ratings.idxmax()
        highest_movie = movies.loc[highest_index].get("title", "—")
        highest_rating = ratings.loc[highest_index]
        highest_label = f"{highest_movie} ({highest_rating:.1f})"
    else:
        highest_label = "—"
    if not movies.empty and "year" in movies:
        decades = (movies["year"].dropna().astype(int) // 10 * 10)
        decade_counts = decades.value_counts().sort_index()
        most_common_decade = (
            f"{int(decade_counts.idxmax())}s" if not decade_counts.empty else "—"
        )
        decade_labels = [f"{int(year)}s" for year in decade_counts.index]
        decade_values = decade_counts.astype(int).tolist()
    else:
        most_common_decade = "—"
        decade_labels = []
        decade_values = []
    last_updated = "Unavailable"
    if "scraped_at" in movies and movies["scraped_at"].notna().any():
        last_updated = str(movies["scraped_at"].dropna().iloc[0])

    columns = list(filtered.columns)
    return render_template(
        "index.html",
        movies=filtered.to_dict(orient="records"),
        columns=columns,
        query=title_query,
        min_year=min_year,
        max_year=max_year,
        min_rating=min_rating,
        sort=sort_key,
        order=order,
        total=len(movies),
        average_rating=f"{average_rating:.2f}" if pd.notna(average_rating) else "—",
        highest_label=highest_label,
        most_common_decade=most_common_decade,
        last_updated=last_updated,
        decade_labels=decade_labels,
        decade_values=decade_values,
        download_url=url_for("download_csv"),
    )


@app.route("/download")
def download_csv():
    if not LATEST_CSV.is_file():
        abort(404, description="No scrape CSV is available yet.")
    return send_file(LATEST_CSV, as_attachment=True, download_name="cineo_latest.csv")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
