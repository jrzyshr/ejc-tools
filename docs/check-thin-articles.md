# Check Thin Articles

Identify NJ municipalities with thin or missing Wikipedia articles that need manual research. Generates a report with article lengths, links, and optionally attempts to find official municipal websites.

## Prerequisites

- Wikipedia articles cached (run `fetch_wikipedia.py --all` first)
- `data/towns.csv` must exist

## Usage

### Basic check

```bash
python scripts/check_thin_articles.py
```

### Custom threshold

Default threshold is 2,000 characters. Adjust as needed:

```bash
python scripts/check_thin_articles.py --threshold 3000
```

### Include unfetched towns

Show towns that haven't been cached yet:

```bash
python scripts/check_thin_articles.py --include-missing
```

### Save report to file

```bash
python scripts/check_thin_articles.py --output data/thin_articles_report.md
```

### Find official websites

Attempt to locate official municipal government websites for flagged towns:

```bash
python scripts/check_thin_articles.py --find-websites
```

This tries common NJ municipal URL patterns (e.g., `{town}nj.gov`, `{town}nj.org`) and reports which ones resolve.

## Output

The report includes:

### Summary table

| Category | Description |
|----------|-------------|
| OK | Articles above the character threshold |
| Thin | Articles below the threshold (sorted shortest-first) |
| Missing | Towns where no Wikipedia article was found |
| Not yet fetched | Towns not yet cached (with `--include-missing`) |

### Thin articles table

For each thin article: town name, county, extract length, Wikipedia byte size, number of sections, and link to the article.

### Official websites

With `--find-websites`, the script probes common URL patterns for each flagged town. Found websites are listed with links; unfound towns are marked for manual search.

## Configuration

The threshold can also be set in `config.json` under `wikipedia.thin_article_threshold` (default: `2000`).

## Workflow

Typical workflow for handling thin articles:

1. Run `fetch_wikipedia.py --all` to cache all articles
2. Run `check_thin_articles.py --output data/thin_articles_report.md` to generate the report
3. Review the report for towns needing manual research
4. For thin-article towns, check official websites and local history resources
5. Run `extract_research.py` — it will note sparse data in the research brief
