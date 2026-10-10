# Cineo

Cineo is a Python command-line scraper and companion dashboard for the IMDb
Top 250 chart. It uses Selenium with Chrome, normalizes movie metadata, writes
dated and `latest.csv` exports, and provides a searchable Flask dashboard.

> **Responsible use:** This project is intended for educational and personal
> use. Review and respect IMDb's terms of service, robots guidance, and rate
> limits before running it. Do not use the optional detail scrape to make
> frequent or high-volume requests. IMDb also publishes official datasets at
> <https://datasets.imdbws.com/>.

## Features

- Selenium/Chrome scraping with a webdriver-manager-managed ChromeDriver.
- Headless and visible-browser modes, explicit waits, lazy-load scrolling,
  consent handling, retries, and JSON-LD fallback.
- Normalized rank, title, year, rating, vote count, movie URL, and UTC scrape
  timestamp values.
- CSV output and comparison of ratings against the previous `latest.csv`.
- Optional genre, director, cast, and runtime extraction.
- Flask dashboard with title search, year/rating filters, sortable columns,
  summary cards, a decade chart, and CSV download.
- Parser/validation unit tests that do not require a browser.

## Tech stack

Python 3.10+, Selenium, Chrome, webdriver-manager, pandas, Flask, Jinja2,
python-dotenv, and pytest.

## Project layout

```text
cineo/
├── scraper/
│   ├── __init__.py
│   ├── config.py         # IMDb URL, selectors, timeouts, and paths
│   ├── driver.py         # Chrome WebDriver setup
│   ├── parser.py         # Normalization and validation
│   └── scraper.py        # Page loading and data extraction
├── app/
│   ├── app.py
│   ├── templates/index.html
│   └── static/style.css
├── data/                 # Generated CSV exports (git-ignored)
├── logs/                 # Generated cineo.log (git-ignored)
├── tests/test_parser.py
├── main.py
├── requirements.txt
└── README.md
```

## Installation

Install Python 3.10 or newer and Google Chrome (or Chromium). From the project
directory, create and activate a virtual environment.

**Windows PowerShell**

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, use `.\.venv\Scripts\python.exe` directly or
select the `.venv` interpreter in VS Code.

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

webdriver-manager downloads a compatible ChromeDriver on the first scraper
run. Chrome itself must already be installed.

## Usage

Run a visible-browser test scrape of ten movies:

```bash
python main.py --no-headless --limit 10
```

Run the full Top 250 headlessly (the default):

```bash
python main.py
```

Other options:

```bash
python main.py --headless --limit 25
python main.py --output exports/top250.csv
python main.py --limit 10 --details
python main.py --help
```

`--limit` accepts values from 1 to 250. By default the primary export is
`data/movies_YYYY-MM-DD.csv`; each run also refreshes `data/latest.csv`.
`--output PATH` changes the primary export location while still updating
`data/latest.csv`. CSV files use UTF-8 encoding and do not include a pandas
index. A run compares the new ratings with the previous `latest.csv` and
prints changes for movies matched by rank and title.

Start the dashboard from the project root:

```bash
python app/app.py
```

Open <http://127.0.0.1:5000>. The dashboard reads `data/latest.csv`; before
the first scrape it displays an empty-state message. Use the **Download CSV**
button to download the latest scrape.

Run parser tests:

```bash
pytest
```

## CSV preview

```csv
rank,title,year,imdb_rating,votes,movie_url,scraped_at
1,The Shawshank Redemption,1994,9.3,3000000,https://www.imdb.com/title/tt0111161/,2026-10-08T10:00:00+00:00
2,The Godfather,1972,9.2,2100000,https://www.imdb.com/title/tt0068646/,2026-10-08T10:00:00+00:00
```

Vote values such as `3.1M` are converted to integer counts. The CSV timestamp
is UTC ISO-8601.

## Updating IMDb selectors

All chart and JSON-LD selectors, timeouts, and the target chart URL are in
`scraper/config.py`. The primary strategy reads list cards, title, metadata,
rating, rating label, and movie link from the chart. If that markup is absent
or incomplete, Cineo attempts to use an `ItemList` in the page's JSON-LD.
After changing selectors, verify with a small visible scrape:

```bash
python main.py --no-headless --limit 10
```

The parser enforces the requested row count, unique ranks, and a rating range
of 0–10 before any CSV is written. Missing individual fields are retained as
empty CSV values; an incomplete number of records causes a retry and then a
clear failure rather than a misleading successful export.

## Daily scheduling

To track rating changes over time, schedule the full headless command daily.
Keep the working directory set to the Cineo project so generated files remain
under its `data/` and `logs/` folders.

- **Windows Task Scheduler:** create a daily task whose program is the
  environment's `python.exe` (for example, `C:\path\to\cineo\.venv\Scripts\python.exe`),
  argument is `main.py`, and **Start in** directory is the project folder.
- **cron (macOS/Linux):** activate no shell environment in cron; call the
  virtual-environment interpreter directly, for example:

  ```cron
  0 7 * * * /path/to/cineo/.venv/bin/python /path/to/cineo/main.py >> /path/to/cineo/logs/scheduled.log 2>&1
  ```

Historical dated exports are created per calendar day. The latest export is
replaced each run and is the comparison baseline for the next run.

## Troubleshooting

- **ChromeDriver/Chrome version mismatch:** update Chrome and retry. The
  webdriver-manager cache can be refreshed by removing only its cached
  ChromeDriver version and rerunning Cineo. Check the log at
  `logs/cineo.log` for the actual driver error.
- **Blocked requests or consent screen:** reduce run frequency, avoid repeated
  detail scrapes, and wait before retrying. IMDb may block automated access;
  respect its terms rather than attempting to evade a block.
- **Empty or incomplete results:** check network access and the current IMDb
  markup, review `logs/cineo.log`, and update the selectors in
  `scraper/config.py`. IMDb's chart and structured data can change.
- **Dashboard has no movies:** run `python main.py` first and confirm
  `data/latest.csv` exists.
- **Chrome cannot start on Linux:** install the system Chrome/Chromium
  dependencies required by your distribution. `--no-sandbox` is already set
  for container-compatible operation.

## Future enhancements

- Richer genre/cast scraping and movie recommendations.
- Database-backed snapshots and rating-history/trend charts.
- Additional export formats and scheduled dashboard refreshes.

