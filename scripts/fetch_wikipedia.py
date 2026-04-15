#!/usr/bin/env python3
"""
Batch-fetch Wikipedia articles for all 564 NJ municipalities.

Fetches full article text, summaries, sections, coordinates, and infobox data
using the Wikipedia API. Caches results to data/wikipedia_cache/ as JSON files.
Handles disambiguation for towns with the same name (e.g., six "Washington
Township" entries) by appending the county name.

Rate-limits API calls to stay within Wikipedia's guidelines (200 ms between
requests by default).

Usage:
    # Fetch all towns from towns.csv
    python scripts/fetch_wikipedia.py --all

    # Fetch a single town
    python scripts/fetch_wikipedia.py --town "Hoboken"

    # Town with disambiguation
    python scripts/fetch_wikipedia.py --town "Lawrence" --county Mercer

    # Override cache (re-fetch even if cached)
    python scripts/fetch_wikipedia.py --all --force

    # Custom rate limit (milliseconds between requests)
    python scripts/fetch_wikipedia.py --all --rate-limit 300

    # Dry run — show what would be fetched
    python scripts/fetch_wikipedia.py --all --dry-run
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

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
DEFAULT_RATE_LIMIT_MS = 200

# Municipality types and their common Wikipedia title patterns
# Only Township and Borough are true suffixes in NJ naming conventions.
# "City", "Town", "Village" are part of a municipality's proper name
# (e.g., "Jersey City", "Union City") and should NOT be stripped.
STRIPPABLE_SUFFIXES = ("Township", "Borough")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def load_config():
    """Load wikipedia settings from config.json."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        return cfg.get("wikipedia", {})
    return {}


def load_towns_csv():
    """Load the master towns.csv and return rows as dicts."""
    if not TOWNS_CSV.exists():
        log.error("towns.csv not found at %s", TOWNS_CSV)
        sys.exit(1)
    towns = []
    with open(TOWNS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            towns.append(row)
    return towns


def sanitize_filename(name):
    """Sanitize a string for use as a filename."""
    clean = name.replace(" ", "_")
    clean = "".join(c for c in clean if c.isalnum() or c in ("_", "-"))
    return clean


def build_wikipedia_title(town_name, municipality_type, county):
    """
    Build the most likely Wikipedia article title for a NJ municipality.

    Wikipedia conventions vary — common patterns:
      - "Hoboken, New Jersey"
      - "Cherry Hill, New Jersey"  (for Cherry Hill Township)
      - "Washington Township, Mercer County, New Jersey"
      - "Lawrence Township, Mercer County, New Jersey"

    For towns with common names (Washington, Franklin, etc.), the county is
    always included to disambiguate.
    """
    # Strip trailing " Township" / " Borough" from the CSV name if present.
    # Do NOT strip "City", "Town", "Village" — these are part of proper names
    # (e.g., "Jersey City", "Union City", "Atlantic City").
    base_name = town_name.strip()
    for suffix in STRIPPABLE_SUFFIXES:
        if base_name.endswith(f" {suffix}"):
            base_name = base_name[: -len(f" {suffix}")]
            break

    mtype = municipality_type.strip() if municipality_type else ""

    # Always include municipality type for Township/Borough since many share names
    if mtype in ("Township", "Borough"):
        title = f"{base_name} {mtype.lower()}, {county} County, New Jersey"
    else:
        title = f"{base_name}, New Jersey"

    return title


def build_title_variants(town_name, municipality_type, county):
    """
    Build a ranked list of possible Wikipedia titles to try.

    Returns the most specific first, falling back to less specific forms.
    """
    base_name = town_name.strip()
    for suffix in STRIPPABLE_SUFFIXES:
        if base_name.endswith(f" {suffix}"):
            base_name = base_name[: -len(f" {suffix}")]
            break

    mtype = municipality_type.strip() if municipality_type else ""
    variants = []

    if mtype in ("Township", "Borough"):
        # Most specific: "X township, County County, New Jersey"
        variants.append(
            f"{base_name} {mtype.lower()}, {county} County, New Jersey"
        )
        # Capitalized type: "X Township, County County, New Jersey"
        variants.append(
            f"{base_name} {mtype}, {county} County, New Jersey"
        )

    # "Name, County County, New Jersey" (for cities that need disambiguation)
    variants.append(f"{base_name}, {county} County, New Jersey")

    # Simple: "Name, New Jersey"
    variants.append(f"{base_name}, New Jersey")

    # Just the name (rare but possible)
    variants.append(f"{base_name}")

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for v in variants:
        vl = v.lower()
        if vl not in seen:
            seen.add(vl)
            unique.append(v)

    return unique


def _wiki_api_get(params, session):
    """Make a GET request to the Wikipedia API with standard headers."""
    params.setdefault("format", "json")
    params.setdefault("formatversion", "2")

    headers = {
        "User-Agent": "EatJerseyChallenge-Tools/1.0 (NJ municipality research; Python requests)",
    }

    resp = session.get(WIKIPEDIA_API_URL, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_article_text(title, session):
    """
    Fetch the full wikitext extracts (plain text) for a Wikipedia article.

    Returns dict with: title, extract (full text), summary, length, pageid,
    coordinates, categories, sections.
    Returns None if the page doesn't exist.
    """
    # Step 1: Get full text extract + page info
    data = _wiki_api_get(
        {
            "action": "query",
            "titles": title,
            "prop": "extracts|info|coordinates|categories|revisions",
            "exlimit": "1",
            "explaintext": "1",
            "exsectionformat": "plain",
            "inprop": "url",
            "colimit": "1",
            "cllimit": "50",
            "clshow": "!hidden",
            "rvprop": "size",
            "redirects": "1",
        },
        session,
    )

    pages = data.get("query", {}).get("pages", [])
    if not pages:
        return None

    page = pages[0]

    # Check for missing page
    if page.get("missing", False):
        return None

    result = {
        "pageid": page.get("pageid"),
        "title": page.get("title", title),
        "url": page.get("fullurl", ""),
        "length": page.get("revisions", [{}])[0].get("size", 0)
        if page.get("revisions")
        else 0,
        "extract": page.get("extract", ""),
        "coordinates": page.get("coordinates", []),
        "categories": [
            c.get("title", "").replace("Category:", "")
            for c in page.get("categories", [])
        ],
    }

    # Step 2: Get the article summary via the REST API for a cleaner summary
    result["summary"] = _fetch_summary(result["title"], session)

    # Step 3: Get section table of contents via parse API
    result["sections"] = _fetch_sections(result["title"], session)

    # Step 4: Try to get infobox data via parsed wikitext
    result["infobox"] = _fetch_infobox(result["title"], session)

    return result


def _fetch_summary(title, session):
    """Fetch the article summary via the Wikipedia REST API."""
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(title)}"
    headers = {
        "User-Agent": "EatJerseyChallenge-Tools/1.0 (NJ municipality research; Python requests)",
    }
    try:
        resp = session.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("extract", "")
    except Exception:
        pass
    return ""


def _parse_sections(full_text):
    """Parse section headings and content from plain-text extract (fallback)."""
    if not full_text:
        return []

    sections = []
    current_heading = "Introduction"
    current_lines = []

    for line in full_text.split("\n"):
        stripped = line.strip()
        # Wikipedia plain-text extracts use "== Heading ==" style
        if stripped.startswith("==") and stripped.endswith("=="):
            # Save previous section
            if current_lines or current_heading == "Introduction":
                sections.append(
                    {
                        "heading": current_heading,
                        "text": "\n".join(current_lines).strip(),
                    }
                )
            current_heading = stripped.strip("= ").strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Don't forget the last section
    if current_lines:
        sections.append(
            {"heading": current_heading, "text": "\n".join(current_lines).strip()}
        )

    return sections


def _fetch_sections(title, session):
    """
    Fetch the section table of contents via the parse API.

    Returns a list of {heading, level, index} dicts.
    """
    try:
        data = _wiki_api_get(
            {
                "action": "parse",
                "page": title,
                "prop": "sections",
                "redirects": "1",
            },
            session,
        )

        raw_sections = data.get("parse", {}).get("sections", [])
        sections = [{"heading": "Introduction", "level": 1, "index": 0}]
        for s in raw_sections:
            sections.append({
                "heading": s.get("line", ""),
                "level": int(s.get("level", 2)),
                "index": int(s.get("index", 0)),
            })
        return sections
    except Exception:
        return [{"heading": "Introduction", "level": 1, "index": 0}]


def _fetch_infobox(title, session):
    """
    Attempt to extract infobox key-value pairs from the wikitext.

    Uses the parse API to get raw wikitext and extracts fields from the
    first {{Infobox ...}} template.
    """
    data = _wiki_api_get(
        {
            "action": "parse",
            "page": title,
            "prop": "wikitext",
            "section": "0",
            "redirects": "1",
        },
        session,
    )

    wikitext = data.get("parse", {}).get("wikitext", "")
    if not wikitext:
        return {}

    return _parse_infobox_wikitext(wikitext)


def _parse_infobox_wikitext(wikitext):
    """Extract key-value pairs from an Infobox template in wikitext."""
    infobox = {}

    # Find the start of {{Infobox
    lower = wikitext.lower()
    idx = lower.find("{{infobox")
    if idx == -1:
        return infobox

    # Track brace depth to find the matching }}
    depth = 0
    start = idx
    end = len(wikitext)
    i = start
    while i < len(wikitext) - 1:
        if wikitext[i : i + 2] == "{{":
            depth += 1
            i += 2
        elif wikitext[i : i + 2] == "}}":
            depth -= 1
            if depth == 0:
                end = i + 2
                break
            i += 2
        else:
            i += 1

    box_text = wikitext[start:end]

    # Extract | key = value lines
    for line in box_text.split("\n"):
        line = line.strip()
        if line.startswith("|") and "=" in line:
            key_val = line[1:].split("=", 1)
            if len(key_val) == 2:
                key = key_val[0].strip().lower()
                val = key_val[1].strip()
                # Clean up wiki markup
                val = _clean_wiki_markup(val)
                if key and val:
                    infobox[key] = val

    return infobox


def _clean_wiki_markup(text):
    """Remove common wiki markup from a string."""
    import re

    # Remove [[link|display]] -> display, [[link]] -> link
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    # Remove {{convert|...}} -> keep first number and unit
    text = re.sub(r"\{\{convert\|([^|]+)\|([^|]+)(?:\|[^}]*)?\}\}", r"\1 \2", text)
    # Remove remaining {{ ... }}
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Remove ref tags and their content
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)
    text = re.sub(r"<ref[^>]*/>", "", text)
    # Clean up whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_town(town_name, municipality_type, county, session, force=False):
    """
    Fetch Wikipedia data for a single town and cache the result.

    Tries multiple title variants to handle disambiguation.

    Parameters
    ----------
    town_name : str
        Town name from towns.csv.
    municipality_type : str
        "Township", "Borough", "City", etc.
    county : str
        County name.
    session : requests.Session
        Reusable HTTP session.
    force : bool
        If True, re-fetch even if cached.

    Returns
    -------
    dict or None
        Article data, or None if no article found.
    """
    cache_key = sanitize_filename(f"{town_name}_{county}")
    cache_path = CACHE_DIR / f"{cache_key}.json"

    if cache_path.exists() and not force:
        log.debug("  Cache hit: %s", cache_path.name)
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    variants = build_title_variants(town_name, municipality_type, county)

    article = None
    tried = []
    for title in variants:
        tried.append(title)
        log.debug("  Trying title: %s", title)
        article = fetch_article_text(title, session)
        if article is not None:
            article["search_title"] = title
            article["town_name"] = town_name
            article["municipality_type"] = municipality_type
            article["county"] = county
            break

    if article is None:
        log.warning("  No Wikipedia article found for %s (%s County)", town_name, county)
        log.warning("  Tried: %s", tried)
        # Cache a stub so we don't retry every run
        article = {
            "town_name": town_name,
            "municipality_type": municipality_type,
            "county": county,
            "missing": True,
            "tried_titles": tried,
            "extract": "",
            "summary": "",
            "length": 0,
            "sections": [],
            "infobox": {},
            "categories": [],
            "coordinates": [],
        }

    # Cache the result
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(article, f, indent=2, ensure_ascii=False)

    return article


def fetch_all(towns, force=False, rate_limit_ms=DEFAULT_RATE_LIMIT_MS, dry_run=False):
    """
    Fetch Wikipedia articles for all towns.

    Parameters
    ----------
    towns : list of dict
        Rows from towns.csv.
    force : bool
        Re-fetch even if cached.
    rate_limit_ms : int
        Milliseconds between API requests.
    dry_run : bool
        If True, print what would be fetched without making requests.

    Returns
    -------
    dict
        Summary stats: fetched, cached, missing, errors.
    """
    stats = {"fetched": 0, "cached": 0, "missing": 0, "errors": 0, "thin": []}

    if dry_run:
        for row in towns:
            name = row.get("town_name", "").strip()
            county = row.get("county", "").strip()
            mtype = row.get("municipality_type", "").strip()
            cache_key = sanitize_filename(f"{name}_{county}")
            cache_path = CACHE_DIR / f"{cache_key}.json"
            cached = cache_path.exists() and not force
            variants = build_title_variants(name, mtype, county)
            status = "CACHED" if cached else "FETCH"
            print(f"  [{status}] {name} ({county} County) -> {variants[0]}")
        return stats

    session = requests.Session()
    total = len(towns)

    for i, row in enumerate(towns, 1):
        name = row.get("town_name", "").strip()
        county = row.get("county", "").strip()
        mtype = row.get("municipality_type", "").strip()

        if not name or not county:
            log.warning("  Skipping row %d: missing town_name or county", i)
            continue

        cache_key = sanitize_filename(f"{name}_{county}")
        cache_path = CACHE_DIR / f"{cache_key}.json"

        # Check cache
        if cache_path.exists() and not force:
            stats["cached"] += 1
            if i % 50 == 0:
                log.info("  Progress: %d/%d (cached: %d)", i, total, stats["cached"])
            continue

        log.info("  [%d/%d] Fetching: %s (%s County)", i, total, name, county)

        try:
            article = fetch_town(name, mtype, county, session, force=force)
            if article and not article.get("missing"):
                stats["fetched"] += 1
                length = article.get("length", 0)
                if length < 2000:
                    stats["thin"].append(
                        {"town": name, "county": county, "length": length}
                    )
            else:
                stats["missing"] += 1
        except Exception as e:
            log.error("  Error fetching %s: %s", name, e)
            stats["errors"] += 1

        # Rate limiting
        time.sleep(rate_limit_ms / 1000.0)

    session.close()
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Wikipedia articles for NJ municipalities."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--town", type=str, help="Single town name to fetch.")
    group.add_argument("--all", action="store_true", help="Fetch all towns from towns.csv.")

    parser.add_argument("--county", type=str, help="County for disambiguation.")
    parser.add_argument(
        "--force", action="store_true", help="Re-fetch even if cached."
    )
    parser.add_argument(
        "--rate-limit",
        type=int,
        default=DEFAULT_RATE_LIMIT_MS,
        help=f"Milliseconds between API requests (default: {DEFAULT_RATE_LIMIT_MS}).",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print what would be fetched."
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging."
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    cfg = load_config()
    rate_limit = args.rate_limit or cfg.get("rate_limit_ms", DEFAULT_RATE_LIMIT_MS)

    if args.all:
        towns = load_towns_csv()
        print(f"Fetching Wikipedia articles for {len(towns)} towns...")
        print(f"  Cache dir: {CACHE_DIR}")
        print(f"  Rate limit: {rate_limit} ms between requests")
        print()

        stats = fetch_all(
            towns,
            force=args.force,
            rate_limit_ms=rate_limit,
            dry_run=args.dry_run,
        )

        if not args.dry_run:
            print()
            print(f"Done. Fetched: {stats['fetched']}, "
                  f"Cached: {stats['cached']}, "
                  f"Missing: {stats['missing']}, "
                  f"Errors: {stats['errors']}")

            if stats["thin"]:
                print(f"\nThin articles (<2000 chars): {len(stats['thin'])}")
                for t in stats["thin"]:
                    print(f"  - {t['town']} ({t['county']} County): {t['length']} chars")
    else:
        # Single town
        town_name = args.town
        county = args.county

        # If no county, try to find it in towns.csv
        if not county:
            towns = load_towns_csv()
            matches = [
                t for t in towns
                if t.get("town_name", "").strip().lower() == town_name.strip().lower()
            ]
            if len(matches) == 1:
                county = matches[0].get("county", "")
                mtype = matches[0].get("municipality_type", "")
            elif len(matches) > 1:
                counties = [m.get("county", "") for m in matches]
                print(
                    f"Multiple towns named '{town_name}' in counties: {counties}. "
                    f"Use --county to disambiguate."
                )
                sys.exit(1)
            else:
                mtype = ""
        else:
            towns = load_towns_csv()
            matches = [
                t for t in towns
                if t.get("town_name", "").strip().lower() == town_name.strip().lower()
                and t.get("county", "").strip().lower() == county.strip().lower()
            ]
            mtype = matches[0].get("municipality_type", "") if matches else ""

        print(f"Fetching Wikipedia article for: {town_name}"
              + (f" ({county} County)" if county else ""))

        session = requests.Session()
        article = fetch_town(
            town_name, mtype, county or "", session, force=args.force
        )
        session.close()

        if article and not article.get("missing"):
            print(f"  Title:  {article.get('title', 'N/A')}")
            print(f"  URL:    {article.get('url', 'N/A')}")
            print(f"  Length: {article.get('length', 0):,} bytes")
            print(f"  Sections: {len(article.get('sections', []))}")
            print(f"  Categories: {len(article.get('categories', []))}")
            summary = article.get("summary", "")
            if summary:
                print(f"  Summary: {summary[:200]}...")
            cache_key = sanitize_filename(f"{town_name}_{county or ''}")
            print(f"  Cached to: data/wikipedia_cache/{cache_key}.json")
        else:
            print(f"  No Wikipedia article found.")
            sys.exit(1)


if __name__ == "__main__":
    main()
