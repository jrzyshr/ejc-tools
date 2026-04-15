#!/usr/bin/env python3
"""
Generate town border outlines on transparent backgrounds.

Replaces the manual Paint.NET workflow of tracing Google Maps borders.
Uses TIGER/Line shapefiles to render municipality boundaries as a red
outline on a transparent PNG.

Usage:
    # Single town
    python scripts/generate_border.py --town "Hoboken"

    # Town with disambiguation
    python scripts/generate_border.py --town "Washington Township" --county Morris

    # All towns (batch mode)
    python scripts/generate_border.py --all

    # Custom output directory
    python scripts/generate_border.py --town "Hoboken" --output-dir assets/

    # Preview in browser instead of saving
    python scripts/generate_border.py --town "Hoboken" --preview

    # Also generate SVG
    python scripts/generate_border.py --town "Hoboken" --svg
"""

import argparse
import csv
import json
import subprocess
import sys
import webbrowser
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for PNG generation

import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np

# Add scripts/ to path for utility imports
sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils.nj_geodata import (
    load_shapefile,
    lookup_town,
    get_display_name,
    get_county_name,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_config():
    """Load border outline settings from config.json."""
    config_path = REPO_ROOT / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            cfg = json.load(f)
        return cfg.get("border_outline", {})
    return {}


def render_border(town_row, config=None, svg=False):
    """
    Render a municipality border as a red outline on transparent background.

    Parameters
    ----------
    town_row : GeoSeries
        A single row from the shapefile (from lookup_town).
    config : dict, optional
        Override settings from config.json.
    svg : bool
        If True, also return SVG data.

    Returns
    -------
    fig : matplotlib.figure.Figure
        The rendered figure (can be saved as PNG/SVG).
    """
    cfg = load_config()
    if config:
        cfg.update(config)

    line_color = cfg.get("line_color", "#FF0000")
    line_width_px = cfg.get("line_width_px", 10)
    output_dpi = cfg.get("output_dpi", 300)

    geom = town_row.geometry

    # Get bounds for figure sizing
    minx, miny, maxx, maxy = geom.bounds
    width = maxx - minx
    height = maxy - miny

    # Add padding (5% on each side)
    pad_x = width * 0.05
    pad_y = height * 0.05

    # Calculate figure size to maintain aspect ratio
    # Target: reasonable image size at the configured DPI
    max_dim_inches = 8.0
    aspect = width / height if height > 0 else 1.0

    if aspect >= 1:
        fig_w = max_dim_inches
        fig_h = max_dim_inches / aspect
    else:
        fig_h = max_dim_inches
        fig_w = max_dim_inches * aspect

    # Convert line_width from "pixels" to matplotlib points at output DPI
    # 1 point = 1/72 inch; we want line_width_px pixels at output_dpi
    line_width_pts = line_width_px * (72.0 / output_dpi) * (fig_w * output_dpi / (width + 2 * pad_x)) * (width / fig_w / output_dpi * 72)
    # Simplify: just scale so it looks ~10px wide in the final image
    line_width_pts = max(line_width_px * 0.5, 2.0)

    fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h))
    fig.patch.set_alpha(0)  # Transparent figure background
    ax.set_facecolor("none")  # Transparent axes background

    # Extract boundary coordinates and plot
    _plot_geometry_boundary(ax, geom, line_color, line_width_pts)

    # Set limits with padding
    ax.set_xlim(minx - pad_x, maxx + pad_x)
    ax.set_ylim(miny - pad_y, maxy + pad_y)

    # Remove all axes, ticks, borders
    ax.set_aspect("equal")
    ax.axis("off")
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

    return fig


def _plot_geometry_boundary(ax, geom, color, linewidth):
    """Plot the boundary of a geometry (handles MultiPolygon)."""
    if geom.geom_type == "Polygon":
        _plot_polygon_boundary(ax, geom, color, linewidth)
    elif geom.geom_type == "MultiPolygon":
        for poly in geom.geoms:
            _plot_polygon_boundary(ax, poly, color, linewidth)
    else:
        # Fallback: try to get the boundary
        boundary = geom.boundary
        if boundary.geom_type == "MultiLineString":
            for line in boundary.geoms:
                x, y = line.xy
                ax.plot(x, y, color=color, linewidth=linewidth, solid_capstyle="round")
        else:
            x, y = boundary.xy
            ax.plot(x, y, color=color, linewidth=linewidth, solid_capstyle="round")


def _plot_polygon_boundary(ax, polygon, color, linewidth):
    """Plot the boundary of a single Polygon, including holes."""
    # Exterior ring
    x, y = polygon.exterior.xy
    ax.plot(x, y, color=color, linewidth=linewidth, solid_capstyle="round")

    # Interior rings (holes, e.g., for towns with enclaves)
    for interior in polygon.interiors:
        x, y = interior.xy
        ax.plot(x, y, color=color, linewidth=linewidth, solid_capstyle="round")


def save_border(fig, output_path, dpi=300, svg=False):
    """Save the border figure as PNG (and optionally SVG)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save PNG with transparency
    fig.savefig(
        output_path,
        dpi=dpi,
        transparent=True,
        bbox_inches="tight",
        pad_inches=0,
    )

    # Optionally save SVG
    if svg:
        svg_path = output_path.with_suffix(".svg")
        fig.savefig(
            svg_path,
            format="svg",
            transparent=True,
            bbox_inches="tight",
            pad_inches=0,
        )
        return output_path, svg_path

    return output_path, None


def get_output_path(town_name, town_number=None, output_dir=None):
    """Build the output file path for a town's border outline."""
    if output_dir:
        base = Path(output_dir)
    else:
        base = REPO_ROOT / "assets"

    if town_number:
        folder = f"{town_number}-{sanitize_filename(town_name)}"
    else:
        folder = sanitize_filename(town_name)

    return base / folder / "border_outline.png"


def sanitize_filename(name):
    """Sanitize a town name for use as a filename/directory name."""
    # Replace spaces with underscores, remove special characters
    clean = name.replace(" ", "_")
    clean = "".join(c for c in clean if c.isalnum() or c in ("_", "-"))
    return clean


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


def generate_single(town_name, county=None, output_dir=None, town_number=None,
                    preview=False, svg=False, config=None):
    """Generate border outline for a single town."""
    gdf = load_shapefile()
    town = lookup_town(town_name, county=county, gdf=gdf)

    display_name = get_display_name(town)
    town_county = get_county_name(town.get("COUNTYFP", ""))

    print(f"  Generating border: {display_name} ({town_county} County)")

    fig = render_border(town, config=config)

    cfg = load_config()
    if config:
        cfg.update(config)
    dpi = cfg.get("output_dpi", 300)

    output_path = get_output_path(display_name, town_number, output_dir)
    png_path, svg_path = save_border(fig, output_path, dpi=dpi, svg=svg)

    plt.close(fig)

    print(f"  Saved: {png_path}")
    if svg_path:
        print(f"  Saved: {svg_path}")

    if preview:
        webbrowser.open(f"file://{png_path.resolve()}")

    return png_path


def generate_all(output_dir=None, svg=False, config=None):
    """Generate border outlines for all 564 towns."""
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
            fig = render_border(town_row, config=config)

            cfg = load_config()
            if config:
                cfg.update(config)
            dpi = cfg.get("output_dpi", 300)

            output_path = get_output_path(display_name, town_num, output_dir)
            save_border(fig, output_path, dpi=dpi, svg=svg)
            plt.close(fig)

            print(f"  {display_name} ({town_county}) -> {output_path}")
            success += 1
        except Exception as e:
            print(f"  FAILED: {display_name} ({town_county}): {e}")
            failed += 1

    print(f"\nDone! Generated: {success}, Failed: {failed}")
    return success, failed


def main():
    parser = argparse.ArgumentParser(
        description="Generate town border outlines on transparent backgrounds"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--town", help="Town name to generate border for")
    group.add_argument("--all", action="store_true", help="Generate for all 564 towns")

    parser.add_argument("--county", help="County name for disambiguation")
    parser.add_argument("--output-dir", help="Output directory (default: assets/)")
    parser.add_argument("--preview", action="store_true", help="Open result in browser")
    parser.add_argument("--svg", action="store_true", help="Also generate SVG output")
    parser.add_argument("--dpi", type=int, help="Override output DPI")
    parser.add_argument("--color", help="Override line color (hex, e.g., #FF0000)")
    parser.add_argument("--width", type=float, help="Override line width in pixels")
    parser.add_argument("--town-number", help="Town visit number (for folder naming)")

    args = parser.parse_args()

    # Build config overrides from CLI args
    config = {}
    if args.dpi:
        config["output_dpi"] = args.dpi
    if args.color:
        config["line_color"] = args.color
    if args.width:
        config["line_width_px"] = args.width

    if args.all:
        generate_all(
            output_dir=args.output_dir,
            svg=args.svg,
            config=config or None,
        )
    else:
        generate_single(
            town_name=args.town,
            county=args.county,
            output_dir=args.output_dir,
            town_number=args.town_number,
            preview=args.preview,
            svg=args.svg,
            config=config or None,
        )


if __name__ == "__main__":
    main()
