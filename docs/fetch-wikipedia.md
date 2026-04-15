# Fetch Wikipedia Articles

Batch-fetch Wikipedia articles for all 564 NJ municipalities. Caches raw article data (text, summaries, sections, coordinates, infobox) as JSON files for downstream processing by `extract_research.py`.

## Prerequisites

- `data/towns.csv` must exist (see [generate-towns-csv.md](generate-towns-csv.md))
- Python dependency: `requests` (included in requirements.txt)

## Usage

### Fetch all towns

```bash
python scripts/fetch_wikipedia.py --all
```

### Single town

```bash
python scripts/fetch_wikipedia.py --town "Hoboken"
```

### Disambiguation

For towns with the same name in multiple counties:

```bash
python scripts/fetch_wikipedia.py --town "Lawrence" --county Mercer
python scripts/fetch_wikipedia.py --town "Washington Township" --county Morris
```

### Force re-fetch (ignore cache)

```bash
python scripts/fetch_wikipedia.py --all --force
```

### Dry run

Preview what would be fetched without making API calls:

```bash
python scripts/fetch_wikipedia.py --all --dry-run
```

### Custom rate limit

Adjust delay between API requests (default: 200 ms):

```bash
python scripts/fetch_wikipedia.py --all --rate-limit 300
```

## Output

Cached articles are saved to `data/wikipedia_cache/{town_name}_{county}.json`.

Each JSON file contains:

| Field | Description |
|-------|-------------|
| `title` | Resolved Wikipedia article title |
| `url` | Full Wikipedia URL |
| `pageid` | Wikipedia page ID |
| `length` | Article size in bytes (from Wikipedia) |
| `extract` | Full plain-text article content |
| `summary` | Short summary paragraph |
| `sections` | Array of `{heading, text}` section objects |
| `infobox` | Key-value pairs from the article's infobox |
| `coordinates` | Geographic coordinates (if available) |
| `categories` | Article categories |
| `town_name` | Original town name from `towns.csv` |
| `county` | County name |
| `municipality_type` | Township, Borough, City, etc. |
| `search_title` | The Wikipedia title variant that matched |

Towns with no article get a stub JSON with `"missing": true`.

## Disambiguation strategy

Wikipedia article titles for NJ municipalities follow these conventions:

- Cities: `"{Name}, New Jersey"` (e.g., "Hoboken, New Jersey")
- Townships: `"{Name} township, {County} County, New Jersey"` (e.g., "Lawrence township, Mercer County, New Jersey")
- Boroughs: `"{Name} borough, {County} County, New Jersey"`

The script tries multiple title variants in order, from most specific to least specific, and uses the first one that resolves to an article. Wikipedia redirects are followed automatically.

## Rate limiting

The script respects Wikipedia API guidelines with a configurable delay between requests (default: 200 ms). The `User-Agent` header identifies the tool per Wikipedia's bot policy.

## Configuration

Settings in `config.json` under `wikipedia`:

| Key | Default | Description |
|-----|---------|-------------|
| `rate_limit_ms` | `200` | Milliseconds between API requests |
| `thin_article_threshold` | `2000` | Character threshold for thin article warnings |
| `cache_dir` | `data/wikipedia_cache` | Cache directory path |

## Thin articles

After fetching, the script reports articles below 2,000 characters. Use `check_thin_articles.py` for a detailed audit:

```bash
python scripts/check_thin_articles.py
```
