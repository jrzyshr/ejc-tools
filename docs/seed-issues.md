# seed_issues.py

Bulk-creates GitHub Issues from `towns.csv`, one issue per town, with a structured body, checklist, and labels. Replaces manual issue creation for the 564-town pipeline.

## Prerequisites

- [GitHub CLI (`gh`)](https://cli.github.com/) installed and authenticated (`gh auth login`)
- `data/towns.csv` must exist (run `python scripts/generate_towns_csv.py` first)
- No additional Python packages beyond the standard library

## Usage

### Create issues for all visited towns

```bash
python scripts/seed_issues.py --csv data/towns.csv --repo OWNER/ejc-tools
```

### Dry run (preview without creating)

```bash
python scripts/seed_issues.py --csv data/towns.csv --repo OWNER/ejc-tools --dry-run
```

### Filter by status

```bash
python scripts/seed_issues.py --csv data/towns.csv --repo OWNER/ejc-tools --status visited
```

### Single town

```bash
python scripts/seed_issues.py --csv data/towns.csv --repo OWNER/ejc-tools --town "Hoboken"
```

### Include unvisited towns

```bash
python scripts/seed_issues.py --csv data/towns.csv --repo OWNER/ejc-tools --include-unvisited
```

## CLI Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--csv PATH` | Yes | Path to `towns.csv` |
| `--repo OWNER/REPO` | Yes | GitHub repository (e.g., `jrzyshr/ejc-tools`) |
| `--dry-run` | No | Preview issue creation without making API calls |
| `--status STATUS` | No | Only create issues for towns with this status |
| `--town NAME` | No | Only create an issue for this specific town |
| `--include-unvisited` | No | Also create issues for `not_visited` towns (skipped by default) |
| `--delay SECONDS` | No | Seconds between API calls for rate limiting (default: `1.0`) |

## Status to Stage Mapping

The CSV `status` column maps to GitHub labels as follows:

| CSV Status | GitHub Stage Label | Issue Created? |
|------------|--------------------|----------------|
| `not_visited` | *(none)* | No (unless `--include-unvisited`) |
| `visited` | `stage:raw-footage` | Yes |
| `indexed` | `stage:indexed` | Yes |
| `researched` | `stage:researched` | Yes |
| `scripted` | `stage:scripted` | Yes |
| `vo_recorded` | `stage:vo-recorded` | Yes |
| `edited` | `stage:edited` | Yes |
| `published` | `stage:published` | Yes |

## Issue Structure

Each issue is created with:

- **Title**: `Town #N: Town Name` (or just `Town Name` if no town number)
- **Labels**:
  - County label (e.g., `county:hudson`)
  - Stage label (e.g., `stage:raw-footage`)
- **Body** (markdown sections):
  - **Town Info** — name, type, county, number, restaurant, meal, visit date, notes
  - **Research** — placeholder for Wikipedia/LLM extraction
  - **Video/Photo Index** — placeholder for clip cataloging
  - **Script** — placeholder for draft/final script
  - **Checklist** — 16 items tracking the full production pipeline

## Labels

The script auto-creates labels in the repo if they don't already exist:

- **County labels**: `county:{name}` for all 21 NJ counties, each with a unique color
- **Stage labels**: `stage:raw-footage`, `stage:indexed`, `stage:researched`, `stage:scripted`, `stage:vo-recorded`, `stage:edited`, `stage:published`

## Edge Cases

- **`gh` must be authenticated**: The script verifies `gh` is available before proceeding. Run `gh auth login` if you see authentication errors.
- **No deduplication**: Running the script twice creates duplicate issues. There is no check for existing issues with the same title. Always use `--dry-run` first to preview what will be created.
- **Rate limiting**: GitHub's API has rate limits (~5,000 requests/hour for authenticated users). The default 1.0-second delay between issues is conservative. For large batches (500+ towns), consider increasing `--delay` if you encounter `403` errors.
- **Dry run skips label creation**: In `--dry-run` mode, labels are not created in the repo. The script prints what would be created instead.
- **Default filter excludes unvisited**: By default, towns with `status=not_visited` are skipped. Use `--include-unvisited` to create issues for all towns, or `--status` to target a specific status.
- **CSV must exist**: The script exits with an error if the CSV file is not found, and suggests running `generate_towns_csv.py` first.
- **Label idempotency**: Label creation is safe to repeat — if a label already exists, the script silently skips it.
