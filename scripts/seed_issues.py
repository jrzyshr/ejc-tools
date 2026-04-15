#!/usr/bin/env python3
"""
Seed GitHub Issues from towns.csv for the EatJerseyChallenge project.

Creates one issue per town with structured body, labels, and checklist.
Requires the GitHub CLI (`gh`) to be installed and authenticated.

Usage:
    # Create issues for all towns
    python scripts/seed_issues.py --csv data/towns.csv --repo OWNER/ejc-tools

    # Dry run — preview without creating
    python scripts/seed_issues.py --csv data/towns.csv --repo OWNER/ejc-tools --dry-run

    # Create issues only for towns with a specific status
    python scripts/seed_issues.py --csv data/towns.csv --repo OWNER/ejc-tools --status visited

    # Create a single test issue
    python scripts/seed_issues.py --csv data/towns.csv --repo OWNER/ejc-tools --town "Hoboken"
"""

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

# Map CSV status values to GitHub Project board columns
STATUS_TO_STAGE = {
    "not_visited": None,  # No issue created unless --include-unvisited
    "visited": "Raw Footage",
    "indexed": "Indexed",
    "researched": "Researched",
    "scripted": "Scripted",
    "vo_recorded": "VO Recorded",
    "edited": "Edited",
    "published": "Published",
}

# County label colors (one per NJ county)
COUNTY_COLORS = {
    "Atlantic": "0E8A16",
    "Bergen": "1D76DB",
    "Burlington": "5319E7",
    "Camden": "D93F0B",
    "Cape May": "0075CA",
    "Cumberland": "E4E669",
    "Essex": "D876E3",
    "Gloucester": "FBCA04",
    "Hudson": "B60205",
    "Hunterdon": "006B75",
    "Mercer": "C2E0C6",
    "Middlesex": "BFD4F2",
    "Monmouth": "D4C5F9",
    "Morris": "F9D0C4",
    "Ocean": "0052CC",
    "Passaic": "E99695",
    "Salem": "BFDADC",
    "Somerset": "C5DEF5",
    "Sussex": "FEF2C0",
    "Union": "EDEDED",
    "Warren": "7057FF",
}

# Stage labels
STAGE_LABELS = {
    "stage:raw-footage": "FBCA04",
    "stage:indexed": "FEF2C0",
    "stage:researched": "C2E0C6",
    "stage:scripted": "0E8A16",
    "stage:vo-recorded": "BFD4F2",
    "stage:edited": "0075CA",
    "stage:published": "5319E7",
}


def run_gh(args, check=True):
    """Run a GitHub CLI command and return the result."""
    cmd = ["gh"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        print(f"ERROR: gh {' '.join(args)}")
        print(f"  stderr: {result.stderr.strip()}")
        return None
    return result


def ensure_labels(repo, dry_run=False):
    """Create county and stage labels if they don't exist."""
    print("Ensuring labels exist...")

    # Get existing labels
    result = run_gh(["label", "list", "--repo", repo, "--json", "name", "--limit", "100"])
    if result is None:
        if dry_run:
            print("  (Could not connect to repo, skipping label check for dry run)")
            return
        print("ERROR: Could not list labels. Is `gh` authenticated?")
        sys.exit(1)

    try:
        existing = {l["name"] for l in json.loads(result.stdout)}
    except json.JSONDecodeError:
        if dry_run:
            print("  (Could not connect to repo, skipping label check for dry run)")
            existing = set()
        else:
            print("ERROR: Could not parse label list from GitHub.")
            sys.exit(1)

    # Create county labels
    for county, color in COUNTY_COLORS.items():
        label_name = f"county:{county.lower().replace(' ', '-')}"
        if label_name not in existing:
            if dry_run:
                print(f"  [DRY RUN] Would create label: {label_name}")
            else:
                run_gh([
                    "label", "create", label_name,
                    "--repo", repo,
                    "--color", color,
                    "--description", f"{county} County, NJ",
                ], check=False)
                print(f"  Created label: {label_name}")

    # Create stage labels
    for label_name, color in STAGE_LABELS.items():
        if label_name not in existing:
            if dry_run:
                print(f"  [DRY RUN] Would create label: {label_name}")
            else:
                run_gh([
                    "label", "create", label_name,
                    "--repo", repo,
                    "--color", color,
                    "--description", f"Pipeline stage: {label_name.split(':')[1]}",
                ], check=False)
                print(f"  Created label: {label_name}")


def build_issue_body(town):
    """Build the markdown body for a town issue."""
    town_number = town.get("town_number", "TBD")
    town_name = town["town_name"]
    county = town["county"]
    muni_type = town.get("municipality_type", "")
    restaurant = town.get("restaurant", "")
    meal_type = town.get("meal_type", "")
    visit_date = town.get("visit_date", "")
    notes = town.get("notes", "")

    body = f"""## Town Info
- **Town**: {town_name}
- **Municipality Type**: {muni_type}
- **County**: {county}
- **Town Number**: {town_number}
- **Restaurant**: {restaurant}
- **Meal**: {meal_type}
- **Visit Date**: {visit_date}
- **Notes**: {notes}

## Research
<!-- Populated by fetch_wikipedia.py / extract_research.py -->

## Video/Photo Index
<!-- Populated by index_clips.py or filled manually -->

## Script
<!-- Draft and final script text -->

## Checklist
- [ ] Assets gathered on NAS
- [ ] Video/photo index complete
- [ ] Menu items documented
- [ ] Town research reviewed
- [ ] Script drafted
- [ ] Script finalized
- [ ] Voice recorded
- [ ] Voice cleaned (auto-editor)
- [ ] Captions generated (Whisper)
- [ ] Map fly-in created
- [ ] Border outline generated
- [ ] Cover photo generated
- [ ] Selfie overlay generated
- [ ] Video edited in DaVinci Resolve
- [ ] Published to Instagram
- [ ] Cross-posted (TikTok/YouTube Shorts)
"""
    return body


def get_stage_label(status):
    """Convert CSV status to a stage label name."""
    stage_map = {
        "visited": "stage:raw-footage",
        "indexed": "stage:indexed",
        "researched": "stage:researched",
        "scripted": "stage:scripted",
        "vo_recorded": "stage:vo-recorded",
        "edited": "stage:edited",
        "published": "stage:published",
    }
    return stage_map.get(status)


def create_issue(repo, town, dry_run=False):
    """Create a single GitHub issue for a town."""
    town_number = town.get("town_number", "")
    town_name = town["town_name"]
    county = town["county"]
    status = town.get("status", "not_visited")

    # Build title
    if town_number:
        title = f"Town #{town_number}: {town_name}"
    else:
        title = f"{town_name}"

    # Build labels
    labels = []
    county_label = f"county:{county.lower().replace(' ', '-')}"
    labels.append(county_label)

    stage_label = get_stage_label(status)
    if stage_label:
        labels.append(stage_label)

    # Build body
    body = build_issue_body(town)

    if dry_run:
        print(f"  [DRY RUN] Would create: {title} | Labels: {', '.join(labels)}")
        return True

    args = [
        "issue", "create",
        "--repo", repo,
        "--title", title,
        "--body", body,
    ]
    for label in labels:
        args.extend(["--label", label])

    result = run_gh(args, check=False)
    if result and result.returncode == 0:
        issue_url = result.stdout.strip()
        print(f"  Created: {title} -> {issue_url}")
        return True
    else:
        print(f"  FAILED: {title}")
        if result:
            print(f"    {result.stderr.strip()}")
        return False


def load_csv(csv_path):
    """Load towns from CSV file."""
    towns = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            towns.append(row)
    return towns


def main():
    parser = argparse.ArgumentParser(
        description="Seed GitHub Issues from towns.csv"
    )
    parser.add_argument("--csv", required=True, help="Path to towns.csv")
    parser.add_argument("--repo", required=True, help="GitHub repo (OWNER/REPO)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating")
    parser.add_argument("--status", help="Only create issues for towns with this status")
    parser.add_argument("--town", help="Only create issue for this specific town name")
    parser.add_argument(
        "--include-unvisited", action="store_true",
        help="Also create issues for not_visited towns"
    )
    parser.add_argument(
        "--delay", type=float, default=1.0,
        help="Seconds between API calls to avoid rate limiting (default: 1.0)"
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"ERROR: CSV file not found: {csv_path}")
        print("Run `python scripts/generate_towns_csv.py` first to create it.")
        sys.exit(1)

    towns = load_csv(csv_path)
    print(f"Loaded {len(towns)} towns from {csv_path}")

    # Filter
    if args.town:
        towns = [t for t in towns if t["town_name"].lower() == args.town.lower()]
        if not towns:
            print(f"ERROR: Town '{args.town}' not found in CSV")
            sys.exit(1)
    elif args.status:
        towns = [t for t in towns if t.get("status") == args.status]
    elif not args.include_unvisited:
        towns = [t for t in towns if t.get("status") != "not_visited"]

    if not towns:
        print("No towns to process. Use --include-unvisited to create issues for all towns,")
        print("or update the 'status' column in towns.csv for visited towns.")
        sys.exit(0)

    print(f"Will create {len(towns)} issues in {args.repo}")

    # Ensure labels exist
    ensure_labels(args.repo, dry_run=args.dry_run)

    # Create issues
    created = 0
    failed = 0
    for i, town in enumerate(towns, 1):
        print(f"[{i}/{len(towns)}]", end=" ")
        if create_issue(args.repo, town, dry_run=args.dry_run):
            created += 1
        else:
            failed += 1

        # Rate limiting
        if not args.dry_run and i < len(towns):
            time.sleep(args.delay)

    print(f"\nDone! Created: {created}, Failed: {failed}")


if __name__ == "__main__":
    main()
