# generate_towns_csv.py

Generates the master `data/towns.csv` list by scraping Wikipedia's [List of municipalities in New Jersey](https://en.wikipedia.org/wiki/List_of_municipalities_in_New_Jersey). This is a one-time setup script — run it once to create the initial data file.

## Prerequisites

- Python packages: `requests`, `beautifulsoup4`

## Usage

```bash
python scripts/generate_towns_csv.py
```

No arguments are required.

## What It Does

1. Fetches the Wikipedia page listing all NJ municipalities
2. Parses the sortable table to extract town name, municipality type, and county
3. Cleans up footnote markers (e.g., `[note 1]`) from town names
4. Normalizes municipality types to: Borough, City, Town, Township, Village
5. Writes `data/towns.csv` with all 564 municipalities
6. Prints a summary breakdown by county

## Output

Creates `data/towns.csv` with the following schema:

| Column | Description | Initial Value |
|--------|-------------|---------------|
| `town_number` | Visit order number | (empty) |
| `town_name` | Municipality name | From Wikipedia |
| `municipality_type` | Borough, City, Town, Township, or Village | From Wikipedia |
| `county` | County name | From Wikipedia |
| `status` | Pipeline status | `not_visited` |
| `restaurant` | Restaurant visited | (empty) |
| `meal_type` | Type of meal | (empty) |
| `visit_date` | Date of visit | (empty) |
| `instagram_url` | Published reel URL | (empty) |
| `notes` | Freeform notes | (empty) |

## Edge Cases

- **Overwrites without warning**: Running the script again overwrites `data/towns.csv` completely. If you've manually added data (visit dates, restaurants, etc.), those changes will be lost. Back up the file before re-running.
- **Wikipedia format changes**: The scraper looks for a `<table class="wikitable sortable">`. If Wikipedia reorganizes the page, the scraper may find the wrong table or fail entirely. The script exits with an error if no sortable table is found.
- **Low municipality count warning**: If fewer than 500 municipalities are parsed, the script prints a warning. This likely indicates the Wikipedia table format has changed and the output should be reviewed manually.
- **Footnote cleaning**: Regex-based removal of `[...]` markers. In rare cases this could strip legitimate bracketed text from town names, though none are known to exist.
- **Internet required**: Fetches live from Wikipedia on each run. The script has a 30-second request timeout.
