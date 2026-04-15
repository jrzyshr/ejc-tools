#!/usr/bin/env python3
"""
Identify NJ municipalities with thin or missing Wikipedia articles.

Scans the wikipedia_cache directory and flags towns whose articles are under a
configurable character threshold (default: 2000). For thin-article towns,
attempts to find official government websites and history pages.

Outputs a report listing towns that need manual research.

Usage:
    # Check all cached articles (default threshold: 2000 chars)
    python scripts/check_thin_articles.py

    # Custom threshold
    python scripts/check_thin_articles.py --threshold 3000

    # Include uncached/missing towns
    python scripts/check_thin_articles.py --include-missing

    # Output report to a file
    python scripts/check_thin_articles.py --output data/thin_articles_report.md

    # Attempt to find official town websites for thin articles
    python scripts/check_thin_articles.py --find-websites
"""

import argparse
import csv
import json
import logging
import sys
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "data" / "wikipedia_cache"
TOWNS_CSV = REPO_ROOT / "data" / "towns.csv"
CONFIG_PATH = REPO_ROOT / "config.json"

DEFAULT_THRESHOLD = 2000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def sanitize_filename(name):
    """Sanitize a string for use as a filename."""
    clean = name.replace(" ", "_")
    clean = "".join(c for c in clean if c.isalnum() or c in ("_", "-"))
    return clean


def load_towns_csv():
    """Load the master towns.csv."""
    if not TOWNS_CSV.exists():
        log.error("towns.csv not found at %s", TOWNS_CSV)
        sys.exit(1)
    towns = []
    with open(TOWNS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            towns.append(row)
    return towns


def load_config():
    """Load wikipedia settings from config.json."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        return cfg.get("wikipedia", {})
    return {}


def check_articles(towns, threshold=DEFAULT_THRESHOLD, include_missing=False):
    """
    Check all towns against the character threshold.

    Parameters
    ----------
    towns : list of dict
        Rows from towns.csv.
    threshold : int
        Minimum article length in characters.
    include_missing : bool
        If True, also report towns with no cached article.

    Returns
    -------
    dict
        Results with keys: thin, missing, ok, uncached.
    """
    results = {"thin": [], "missing": [], "ok": 0, "uncached": []}

    for row in towns:
        name = row.get("town_name", "").strip()
        county = row.get("county", "").strip()
        if not name or not county:
            continue

        cache_key = sanitize_filename(f"{name}_{county}")
        cache_path = CACHE_DIR / f"{cache_key}.json"

        if not cache_path.exists():
            if include_missing:
                results["uncached"].append({"town": name, "county": county})
            continue

        with open(cache_path, encoding="utf-8") as f:
            article = json.load(f)

        if article.get("missing"):
            results["missing"].append({"town": name, "county": county})
            continue

        length = len(article.get("extract", ""))
        wiki_length = article.get("length", 0)

        if length < threshold:
            results["thin"].append({
                "town": name,
                "county": county,
                "extract_length": length,
                "wiki_length": wiki_length,
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "sections": len(article.get("sections", [])),
            })
        else:
            results["ok"] += 1

    return results


def find_town_website(town_name, county, municipality_type=""):
    """
    Attempt to find a town's official government website.

    Uses a simple Google-style search pattern to construct likely URLs.
    Does not actually scrape — just checks if common URL patterns resolve.

    Returns the URL if found, or None.
    """
    # Common patterns for NJ municipal websites
    base_name = town_name.strip().lower()
    for suffix in ("township", "borough", "city", "town", "village"):
        if base_name.endswith(f" {suffix}"):
            base_name = base_name[: -len(f" {suffix}")]
            break

    slug = base_name.replace(" ", "")
    slug_dash = base_name.replace(" ", "-")
    mtype = municipality_type.strip().lower() if municipality_type else ""

    # Candidate URLs to try
    candidates = [
        f"https://www.{slug}nj.gov",
        f"https://www.{slug}nj.org",
        f"https://{slug}nj.gov",
        f"https://www.{slug}{mtype}nj.org",
        f"https://www.{slug_dash}.org",
        f"https://www.{slug_dash}nj.com",
        f"https://{slug}{mtype}.com",
    ]

    headers = {
        "User-Agent": "EatJerseyChallenge-Tools/1.0 (municipal website check)",
    }

    for url in candidates:
        try:
            resp = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
            if resp.status_code < 400:
                return resp.url  # Return the final URL after redirects
        except (requests.RequestException, Exception):
            continue

    return None


def format_report(results, threshold, find_websites=False, towns_csv=None):
    """Format the results as a Markdown report."""
    lines = [
        f"# Thin Wikipedia Articles Report",
        f"",
        f"Threshold: {threshold:,} characters",
        f"",
        f"## Summary",
        f"",
        f"| Category | Count |",
        f"|----------|-------|",
        f"| OK (above threshold) | {results['ok']} |",
        f"| Thin (below threshold) | {len(results['thin'])} |",
        f"| Missing (no Wikipedia article) | {len(results['missing'])} |",
    ]

    if results.get("uncached"):
        lines.append(f"| Not yet fetched | {len(results['uncached'])} |")

    lines.append("")

    if results["thin"]:
        lines.append("## Thin Articles")
        lines.append("")
        lines.append("| Town | County | Extract Length | Wiki Length | Sections | URL |")
        lines.append("|------|--------|---------------|-------------|----------|-----|")

        # Sort by extract length (shortest first)
        for t in sorted(results["thin"], key=lambda x: x["extract_length"]):
            url = t.get("url", "")
            url_cell = f"[link]({url})" if url else "—"
            lines.append(
                f"| {t['town']} | {t['county']} | {t['extract_length']:,} | "
                f"{t['wiki_length']:,} | {t['sections']} | {url_cell} |"
            )
        lines.append("")

    if results["missing"]:
        lines.append("## Missing Articles")
        lines.append("")
        lines.append("These towns had no Wikipedia article found:")
        lines.append("")
        for t in sorted(results["missing"], key=lambda x: x["town"]):
            lines.append(f"- {t['town']} ({t['county']} County)")
        lines.append("")

    if results.get("uncached"):
        lines.append("## Not Yet Fetched")
        lines.append("")
        lines.append("These towns have not been fetched yet (run `fetch_wikipedia.py --all` first):")
        lines.append("")
        for t in sorted(results["uncached"], key=lambda x: x["town"]):
            lines.append(f"- {t['town']} ({t['county']} County)")
        lines.append("")

    # Website lookup for thin + missing towns
    if find_websites and (results["thin"] or results["missing"]):
        lines.append("## Official Websites (Auto-Detected)")
        lines.append("")
        lines.append("Attempted to find official municipal websites for thin/missing article towns:")
        lines.append("")

        # Build a lookup from towns.csv for municipality_type
        type_lookup = {}
        if towns_csv:
            for row in towns_csv:
                key = (row.get("town_name", "").strip(), row.get("county", "").strip())
                type_lookup[key] = row.get("municipality_type", "")

        all_flagged = [
            {"town": t["town"], "county": t["county"]}
            for t in results["thin"]
        ] + results["missing"]

        found = 0
        not_found = 0
        for t in sorted(all_flagged, key=lambda x: x["town"]):
            mtype = type_lookup.get((t["town"], t["county"]), "")
            url = find_town_website(t["town"], t["county"], mtype)
            if url:
                lines.append(f"- **{t['town']}** ({t['county']} County): [{url}]({url})")
                found += 1
            else:
                lines.append(f"- {t['town']} ({t['county']} County): *not found*")
                not_found += 1
            time.sleep(0.3)  # Rate limit website checks

        lines.append("")
        lines.append(f"Found: {found}, Not found: {not_found}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Check for thin or missing Wikipedia articles for NJ municipalities."
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_THRESHOLD,
        help=f"Minimum article length in characters (default: {DEFAULT_THRESHOLD}).",
    )
    parser.add_argument(
        "--include-missing",
        action="store_true",
        help="Include towns that haven't been fetched yet.",
    )
    parser.add_argument(
        "--find-websites",
        action="store_true",
        help="Attempt to find official municipal websites for flagged towns.",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Save report to a file (Markdown format).",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging."
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    cfg = load_config()
    threshold = args.threshold or cfg.get("thin_article_threshold", DEFAULT_THRESHOLD)

    towns = load_towns_csv()
    print(f"Checking {len(towns)} towns against {threshold:,}-character threshold...")

    results = check_articles(
        towns,
        threshold=threshold,
        include_missing=args.include_missing,
    )

    report = format_report(
        results,
        threshold,
        find_websites=args.find_websites,
        towns_csv=towns,
    )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\nReport saved to: {out_path}")
    else:
        print()
        print(report)

    # Print quick summary to stderr
    total_flagged = len(results["thin"]) + len(results["missing"])
    if total_flagged:
        print(f"\n{total_flagged} towns need manual research.", file=sys.stderr)
    else:
        print("\nAll cached articles are above the threshold.", file=sys.stderr)


if __name__ == "__main__":
    main()
