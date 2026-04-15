#!/usr/bin/env python3
"""
Generate labeled municipality maps showing a target town and its neighbors.

Replaces the manual Paint.NET map creation workflow. The target town is filled
in red/orange, neighbors in light blue, and optional extra highlighted towns in
yellow. Labels are placed at polygon centroids with white stroke for
readability, using adjustText to prevent overlaps.

Usage:
    # Single town
    python scripts/generate_labeled_map.py --town "Hoboken"

    # Town with disambiguation
    python scripts/generate_labeled_map.py --town "Lawrence" --county Mercer

    # Highlight additional towns
    python scripts/generate_labeled_map.py --town "Hoboken" --highlight "Jersey City" "Weehawken"

    # All towns (batch mode)
    python scripts/generate_labeled_map.py --all

    # Custom output directory
    python scripts/generate_labeled_map.py --town "Hoboken" --output-dir assets/

    # Preview in browser instead of saving
    python scripts/generate_labeled_map.py --town "Hoboken" --preview
"""

import argparse
import csv
import json
import sys
import webbrowser
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from adjustText import adjust_text

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils.nj_geodata import (
    load_shapefile,
    lookup_town,
    get_neighbors,
    get_display_name,
    get_county_name,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_config():
    """Load labeled map settings from config.json."""
    config_path = REPO_ROOT / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            cfg = json.load(f)
        return cfg.get("labeled_map", {})
    return {}


def sanitize_filename(name):
    """Sanitize a town name for use as a filename/directory name."""
    clean = name.replace(" ", "_")
    clean = "".join(c for c in clean if c.isalnum() or c in ("_", "-"))
    return clean


def get_output_path(town_name, town_number=None, output_dir=None):
    """Build the output file path for a town's labeled map."""
    if output_dir:
        base = Path(output_dir)
    else:
        base = REPO_ROOT / "assets"

    if town_number:
        folder = f"{town_number}-{sanitize_filename(town_name)}"
    else:
        folder = sanitize_filename(town_name)

    return base / folder / "labeled_map.png"


def load_towns_csv():
    """Load the towns.csv master list for batch processing."""
    csv_path = REPO_ROOT / "data" / "towns.csv"
    if not csv_path.exists():
        return None

    towns = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            towns.append(row)
    return towns


def render_labeled_map(town_row, gdf, highlight_towns=None, config=None):
    """
    Render a labeled map showing the target town and its neighbors.

    Parameters
    ----------
    town_row : GeoSeries
        The target town row from the shapefile.
    gdf : GeoDataFrame
        Full NJ shapefile (already reprojected to UTM).
    highlight_towns : list of GeoSeries, optional
        Additional towns to highlight in yellow.
    config : dict, optional
        Override settings from config.json.

    Returns
    -------
    fig : matplotlib.figure.Figure
    """
    cfg = load_config()
    if config:
        cfg.update(config)

    target_color = cfg.get("target_fill_color", "#FF6B35")
    neighbor_color = cfg.get("neighbor_fill_color", "#A8D8EA")
    highlight_color = cfg.get("highlight_fill_color", "#FFD166")
    default_color = cfg.get("default_fill_color", "#E8E8E8")
    label_font_size = cfg.get("label_font_size", 9)

    # Get neighbors
    neighbors = get_neighbors(town_row, gdf=gdf)

    # Collect GEOIDs for classification
    target_geoid = town_row.get("GEOID", "")
    neighbor_geoids = set(neighbors["GEOID"].tolist()) if "GEOID" in neighbors.columns else set()

    highlight_geoids = set()
    if highlight_towns:
        for ht in highlight_towns:
            hg = ht.get("GEOID", "")
            if hg:
                highlight_geoids.add(hg)

    # Build the set of all towns to display: target + neighbors + highlights
    display_geoids = {target_geoid} | neighbor_geoids | highlight_geoids
    display_gdf = gdf[gdf["GEOID"].isin(display_geoids)].copy()

    # Assign colors
    def classify(geoid):
        if geoid == target_geoid:
            return target_color
        if geoid in highlight_geoids:
            return highlight_color
        if geoid in neighbor_geoids:
            return neighbor_color
        return default_color

    display_gdf["fill_color"] = display_gdf["GEOID"].apply(classify)

    # Compute bounds for the display area with padding
    total_bounds = display_gdf.total_bounds  # minx, miny, maxx, maxy
    minx, miny, maxx, maxy = total_bounds
    width = maxx - minx
    height = maxy - miny
    pad_x = width * 0.08
    pad_y = height * 0.08

    # Figure sizing
    max_dim_inches = 10.0
    aspect = width / height if height > 0 else 1.0
    if aspect >= 1:
        fig_w = max_dim_inches
        fig_h = max_dim_inches / aspect
    else:
        fig_h = max_dim_inches
        fig_w = max_dim_inches * aspect

    # Enforce minimum dimensions
    fig_w = max(fig_w, 6.0)
    fig_h = max(fig_h, 6.0)

    fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    # Plot each polygon
    for _, row in display_gdf.iterrows():
        geom = row.geometry
        color = row["fill_color"]
        if geom.geom_type == "Polygon":
            _plot_filled_polygon(ax, geom, color)
        elif geom.geom_type == "MultiPolygon":
            for poly in geom.geoms:
                _plot_filled_polygon(ax, poly, color)

    # Set view limits
    ax.set_xlim(minx - pad_x, maxx + pad_x)
    ax.set_ylim(miny - pad_y, maxy + pad_y)
    ax.set_aspect("equal")
    ax.axis("off")

    # Add labels at centroids using adjustText
    texts = []
    for _, row in display_gdf.iterrows():
        centroid = row.geometry.centroid
        name = get_display_name(row)
        txt = ax.text(
            centroid.x,
            centroid.y,
            name,
            fontsize=label_font_size,
            ha="center",
            va="center",
            fontweight="bold",
            color="black",
            path_effects=[
                pe.withStroke(linewidth=3, foreground="white"),
            ],
        )
        texts.append(txt)

    # Prevent overlapping labels
    adjust_text(
        texts,
        ax=ax,
        expand=(1.2, 1.4),
        force_text=(0.5, 0.8),
        force_points=(0.3, 0.5),
        arrowprops=dict(arrowstyle="-", color="gray", lw=0.5),
    )

    plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)

    return fig


def _plot_filled_polygon(ax, polygon, fill_color, edge_color="#444444",
                         edge_width=0.8):
    """Plot a filled polygon with an outline."""
    from matplotlib.patches import Polygon as MplPolygon

    exterior_coords = list(polygon.exterior.coords)
    patch = MplPolygon(
        exterior_coords,
        closed=True,
        facecolor=fill_color,
        edgecolor=edge_color,
        linewidth=edge_width,
    )
    ax.add_patch(patch)

    # Draw holes
    for interior in polygon.interiors:
        hole_coords = list(interior.coords)
        hole_patch = MplPolygon(
            hole_coords,
            closed=True,
            facecolor="white",
            edgecolor=edge_color,
            linewidth=edge_width,
        )
        ax.add_patch(hole_patch)


def generate_single(town_name, county=None, output_dir=None, town_number=None,
                    highlight_names=None, preview=False, config=None):
    """Generate a labeled map for a single town."""
    gdf = load_shapefile()
    town = lookup_town(town_name, county=county, gdf=gdf)

    display_name = get_display_name(town)
    town_county = get_county_name(town.get("COUNTYFP", ""))

    print(f"  Generating labeled map: {display_name} ({town_county} County)")

    # Resolve additional highlighted towns
    highlight_towns = []
    if highlight_names:
        for hn in highlight_names:
            try:
                ht = lookup_town(hn, gdf=gdf)
                highlight_towns.append(ht)
            except ValueError as e:
                print(f"  Warning: skipping highlight '{hn}': {e}")

    fig = render_labeled_map(
        town, gdf, highlight_towns=highlight_towns or None, config=config,
    )

    cfg = load_config()
    if config:
        cfg.update(config)
    dpi = cfg.get("output_dpi", 200)

    output_path = get_output_path(display_name, town_number, output_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)

    print(f"  Saved: {output_path}")

    if preview:
        webbrowser.open(f"file://{output_path.resolve()}")

    return output_path


def generate_all(output_dir=None, config=None):
    """Generate labeled maps for all 564 towns."""
    gdf = load_shapefile()
    towns_csv = load_towns_csv()

    # Build a lookup from town name to town number
    town_numbers = {}
    if towns_csv:
        for row in towns_csv:
            key = row["town_name"].strip().lower()
            if row.get("town_number"):
                town_numbers[key] = row["town_number"]

    total = len(gdf)
    success = 0
    failed = 0

    for idx, (_, town_row) in enumerate(gdf.iterrows(), 1):
        display_name = get_display_name(town_row)
        town_county = get_county_name(town_row.get("COUNTYFP", ""))
        town_num = town_numbers.get(display_name.lower())

        print(f"[{idx}/{total}]", end=" ")

        try:
            fig = render_labeled_map(town_row, gdf, config=config)

            cfg = load_config()
            if config:
                cfg.update(config)
            dpi = cfg.get("output_dpi", 200)

            output_path = get_output_path(display_name, town_num, output_dir)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(output_path, dpi=dpi, bbox_inches="tight", pad_inches=0.1)
            plt.close(fig)

            print(f"  {display_name} ({town_county}) -> {output_path}")
            success += 1
        except Exception as e:
            plt.close("all")
            print(f"  FAILED: {display_name} ({town_county}): {e}")
            failed += 1

    print(f"\nDone! Generated: {success}, Failed: {failed}")
    return success, failed


def main():
    parser = argparse.ArgumentParser(
        description="Generate labeled municipality maps showing a target town and neighbors"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--town", help="Town name to generate map for")
    group.add_argument("--all", action="store_true", help="Generate for all 564 towns")

    parser.add_argument("--county", help="County name for disambiguation")
    parser.add_argument("--output-dir", help="Output directory (default: assets/)")
    parser.add_argument("--preview", action="store_true", help="Open result in browser")
    parser.add_argument("--highlight", nargs="+", help="Additional towns to highlight in yellow")
    parser.add_argument("--dpi", type=int, help="Override output DPI")
    parser.add_argument("--town-number", help="Town visit number (for folder naming)")

    args = parser.parse_args()

    config = {}
    if args.dpi:
        config["output_dpi"] = args.dpi

    if args.all:
        generate_all(output_dir=args.output_dir, config=config or None)
    else:
        generate_single(
            town_name=args.town,
            county=args.county,
            output_dir=args.output_dir,
            town_number=args.town_number,
            highlight_names=args.highlight,
            preview=args.preview,
            config=config or None,
        )


if __name__ == "__main__":
    main()
