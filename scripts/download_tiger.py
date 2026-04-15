#!/usr/bin/env python3
"""
Download TIGER/Line shapefiles for NJ county subdivisions from the US Census Bureau.

Usage:
    python scripts/download_tiger.py
"""

import io
import sys
import zipfile
from pathlib import Path

try:
    import requests
except ImportError:
    print("Required: pip install requests")
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "data" / "tl_2025_34_cousub"

# Census TIGER/Line shapefile URLs — try multiple years in case one isn't up yet
TIGER_URLS = [
    "https://www2.census.gov/geo/tiger/TIGER2024/COUSUB/tl_2024_34_cousub.zip",
    "https://www2.census.gov/geo/tiger/TIGER2023/COUSUB/tl_2023_34_cousub.zip",
]

HEADERS = {
    "User-Agent": "EatJerseyChallenge/1.0 (NJ shapefile download; Python/requests)"
}


def download_tiger():
    """Download and extract the TIGER/Line shapefile for NJ county subdivisions."""
    if OUTPUT_DIR.exists() and any(OUTPUT_DIR.glob("*.shp")):
        print(f"Shapefile already exists at {OUTPUT_DIR}")
        shp_files = list(OUTPUT_DIR.glob("*.shp"))
        print(f"  Found: {shp_files[0].name}")
        return OUTPUT_DIR

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for url in TIGER_URLS:
        print(f"Downloading {url} ...")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=120, stream=True)
            if resp.status_code == 200:
                # Get total size for progress
                total = int(resp.headers.get("content-length", 0))
                data = bytearray()
                downloaded = 0
                for chunk in resp.iter_content(chunk_size=8192):
                    data.extend(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        print(f"\r  {downloaded:,} / {total:,} bytes ({pct:.0f}%)", end="")
                print()

                print(f"Extracting to {OUTPUT_DIR} ...")
                with zipfile.ZipFile(io.BytesIO(bytes(data))) as zf:
                    zf.extractall(OUTPUT_DIR)

                # Rename files to use consistent tl_2025_34_cousub prefix
                year = url.split("TIGER")[1].split("/")[0]
                for f in OUTPUT_DIR.iterdir():
                    if f.stem.startswith(f"tl_{year}_34_cousub"):
                        new_name = f.name.replace(f"tl_{year}", "tl_2025")
                        if new_name != f.name:
                            f.rename(OUTPUT_DIR / new_name)

                print(f"Done! Shapefile extracted to {OUTPUT_DIR}")
                shp_files = list(OUTPUT_DIR.glob("*.shp"))
                if shp_files:
                    print(f"  Main file: {shp_files[0]}")
                return OUTPUT_DIR

            else:
                print(f"  HTTP {resp.status_code}, trying next URL...")
        except requests.RequestException as e:
            print(f"  Failed: {e}, trying next URL...")

    print("ERROR: Could not download TIGER/Line shapefiles from any URL.")
    print("Manual download:")
    print("  1. Visit: https://www.census.gov/cgi-bin/geo/shapefiles/index.php")
    print("  2. Select Year: 2024, Layer Type: County Subdivisions, State: New Jersey")
    print(f"  3. Extract the zip to: {OUTPUT_DIR}")
    sys.exit(1)


if __name__ == "__main__":
    download_tiger()
