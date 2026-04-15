#!/usr/bin/env python3
"""
Generate towns.csv master list from Wikipedia's list of NJ municipalities.
Run once to create the initial data file.

Usage:
    python scripts/generate_towns_csv.py
"""

import csv
import re
import sys
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Required packages: requests, beautifulsoup4")
    print("Install with: pip install requests beautifulsoup4")
    sys.exit(1)

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "towns.csv"
WIKI_URL = "https://en.wikipedia.org/wiki/List_of_municipalities_in_New_Jersey"


def fetch_municipalities():
    """Fetch and parse the municipality table from Wikipedia."""
    print(f"Fetching {WIKI_URL} ...")
    headers = {
        "User-Agent": "EatJerseyChallenge/1.0 (NJ municipality data; Python/requests)"
    }
    resp = requests.get(WIKI_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Find the main sortable table with municipality data
    table = soup.find("table", {"class": "wikitable sortable"})
    if not table:
        print("ERROR: Could not find the municipality table on the Wikipedia page.")
        sys.exit(1)

    rows = table.find_all("tr")
    municipalities = []

    for row in rows[1:]:  # skip header
        cells = row.find_all(["td", "th"])
        if len(cells) < 4:
            continue

        # Extract text, stripping footnote references
        name_raw = cells[0].get_text(strip=True)
        muni_type = cells[1].get_text(strip=True)
        county = cells[2].get_text(strip=True)

        # Clean up name — remove footnote markers like [note 1]
        name_clean = re.sub(r"\[.*?\]", "", name_raw).strip()

        # Normalize type
        type_map = {
            "Borough": "Borough",
            "City": "City",
            "Town": "Town",
            "Township": "Township",
            "Village": "Village",
        }
        muni_type_clean = type_map.get(muni_type, muni_type)

        if name_clean and county and muni_type_clean:
            municipalities.append({
                "town_name": name_clean,
                "municipality_type": muni_type_clean,
                "county": county,
            })

    return municipalities


def write_csv(municipalities):
    """Write the municipalities to a CSV file."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "town_number",
        "town_name",
        "municipality_type",
        "county",
        "status",
        "restaurant",
        "meal_type",
        "visit_date",
        "instagram_url",
        "notes",
    ]

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for muni in municipalities:
            writer.writerow({
                "town_number": "",
                "town_name": muni["town_name"],
                "municipality_type": muni["municipality_type"],
                "county": muni["county"],
                "status": "not_visited",
                "restaurant": "",
                "meal_type": "",
                "visit_date": "",
                "instagram_url": "",
                "notes": "",
            })

    print(f"Wrote {len(municipalities)} municipalities to {OUTPUT_PATH}")


def main():
    municipalities = fetch_municipalities()

    if len(municipalities) < 500:
        print(f"WARNING: Only found {len(municipalities)} municipalities (expected ~564)")
        print("The Wikipedia page format may have changed. Review output carefully.")

    write_csv(municipalities)

    # Print summary by county
    counties = {}
    for m in municipalities:
        counties[m["county"]] = counties.get(m["county"], 0) + 1
    print(f"\nSummary: {len(municipalities)} municipalities across {len(counties)} counties")
    for county in sorted(counties):
        print(f"  {county}: {counties[county]}")


if __name__ == "__main__":
    main()
