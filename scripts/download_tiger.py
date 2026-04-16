#!/usr/bin/env python3
"""
Download TIGER/Line shapefiles from the US Census Bureau.

Supports two datasets:
  - County subdivisions (NJ municipalities) — default
  - ZCTA (ZIP Code Tabulation Areas) — national file, used for zip code overlays

Usage:
    # Download NJ county subdivisions (default)
    python scripts/download_tiger.py

    # Download ZCTA shapefile (~800MB national file)
    python scripts/download_tiger.py --zcta

    # Download both
    python scripts/download_tiger.py --all
"""

import argparse
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

COUSUB_OUTPUT_DIR = REPO_ROOT / "data" / "tl_2025_34_cousub"
ZCTA_OUTPUT_DIR = REPO_ROOT / "data" / "tl_2025_us_zcta520"

# Census TIGER/Line shapefile URLs — try multiple years in case one isn't up yet
COUSUB_URLS = [
    "https://www2.census.gov/geo/tiger/TIGER2024/COUSUB/tl_2024_34_cousub.zip",
    "https://www2.census.gov/geo/tiger/TIGER2023/COUSUB/tl_2023_34_cousub.zip",
]

# ZCTA is national-only (no per-state files available)
ZCTA_URLS = [
    "https://www2.census.gov/geo/tiger/TIGER2024/ZCTA520/tl_2024_us_zcta520.zip",
    "https://www2.census.gov/geo/tiger/TIGER2023/ZCTA520/tl_2023_us_zcta520.zip",
    "https://www2.census.gov/geo/tiger/TIGER2020/ZCTA520/tl_2020_us_zcta520.zip",
]

HEADERS = {
    "User-Agent": "EatJerseyChallenge/1.0 (NJ shapefile download; Python/requests)"
}


def _download_and_extract(urls, output_dir, file_prefix, label, timeout=600):
    """
    Download a TIGER/Line shapefile zip from the first working URL and extract it.

    Parameters
    ----------
    urls : list of str
        URLs to try in order.
    output_dir : Path
        Directory to extract files into.
    file_prefix : str
        Expected file prefix for renaming (e.g. "tl_2024_34_cousub").
    label : str
        Human-readable label for log messages.
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    Path or None
        The output directory on success, None on failure.
    """
    if output_dir.exists() and any(output_dir.glob("*.shp")):
        print(f"{label} shapefile already exists at {output_dir}")
        shp_files = list(output_dir.glob("*.shp"))
        print(f"  Found: {shp_files[0].name}")
        return output_dir

    output_dir.mkdir(parents=True, exist_ok=True)

    for url in urls:
        print(f"Downloading {label}: {url} ...")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout, stream=True)
            if resp.status_code == 200:
                total = int(resp.headers.get("content-length", 0))
                data = bytearray()
                downloaded = 0
                for chunk in resp.iter_content(chunk_size=8192):
                    data.extend(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        mb = downloaded / 1_048_576
                        total_mb = total / 1_048_576
                        print(
                            f"\r  {mb:.1f} / {total_mb:.1f} MB ({pct:.0f}%)",
                            end="",
                        )
                print()

                print(f"Extracting to {output_dir} ...")
                with zipfile.ZipFile(io.BytesIO(bytes(data))) as zf:
                    zf.extractall(output_dir)

                # Rename files to use consistent tl_2025 prefix
                year = url.split("TIGER")[1].split("/")[0]
                for f in output_dir.iterdir():
                    if f.name.startswith(f"tl_{year}"):
                        new_name = f.name.replace(f"tl_{year}", "tl_2025")
                        if new_name != f.name:
                            f.rename(output_dir / new_name)

                print(f"Done! {label} shapefile extracted to {output_dir}")
                shp_files = list(output_dir.glob("*.shp"))
                if shp_files:
                    print(f"  Main file: {shp_files[0]}")
                return output_dir

            else:
                print(f"  HTTP {resp.status_code}, trying next URL...")
        except requests.RequestException as e:
            print(f"  Failed: {e}, trying next URL...")

    return None


def download_cousub():
    """Download NJ county subdivision shapefile."""
    result = _download_and_extract(
        COUSUB_URLS, COUSUB_OUTPUT_DIR,
        "tl_2024_34_cousub", "County Subdivisions (NJ)",
    )
    if result is None:
        print("ERROR: Could not download county subdivision shapefiles.")
        print("Manual download:")
        print("  1. Visit: https://www.census.gov/cgi-bin/geo/shapefiles/index.php")
        print("  2. Select Year: 2024, Layer Type: County Subdivisions, State: New Jersey")
        print(f"  3. Extract the zip to: {COUSUB_OUTPUT_DIR}")
        return False
    return True


def download_zcta():
    """Download national ZCTA (ZIP Code Tabulation Area) shapefile."""
    print("Note: ZCTA is a national file (~800MB). This may take a few minutes.")
    result = _download_and_extract(
        ZCTA_URLS, ZCTA_OUTPUT_DIR,
        "tl_2024_us_zcta520", "ZCTA (ZIP Code Tabulation Areas)",
        timeout=600,
    )
    if result is None:
        print("ERROR: Could not download ZCTA shapefiles.")
        print("Manual download:")
        print("  1. Visit: https://www.census.gov/cgi-bin/geo/shapefiles/index.php")
        print("  2. Select Year: 2024, Layer Type: ZIP Code Tabulation Areas")
        print("  3. Download the national file")
        print(f"  4. Extract the zip to: {ZCTA_OUTPUT_DIR}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Download TIGER/Line shapefiles from the US Census Bureau"
    )
    parser.add_argument(
        "--zcta", action="store_true",
        help="Download ZCTA (ZIP Code Tabulation Area) national shapefile (~800MB)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Download both county subdivisions and ZCTA shapefiles",
    )
    args = parser.parse_args()

    if args.all:
        ok1 = download_cousub()
        ok2 = download_zcta()
        if not (ok1 and ok2):
            sys.exit(1)
    elif args.zcta:
        if not download_zcta():
            sys.exit(1)
    else:
        if not download_cousub():
            sys.exit(1)


if __name__ == "__main__":
    main()
