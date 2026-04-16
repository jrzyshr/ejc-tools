#!/usr/bin/env python3
"""
Generate zip code overlay maps for NJ municipalities.

Renders the municipality shape with ZCTA (ZIP Code Tabulation Area) boundaries
overlaid, each zip zone filled in a distinct color. Optionally shows full zip
code extents beyond the municipality boundary with muted colors.

Usage:
    # Single town (clipped to municipality boundary)
    python scripts/generate_zipcode_overlay.py --town "Hoboken"

    # Show full zip code extents beyond the municipality
    python scripts/generate_zipcode_overlay.py --town "Hoboken" --show-full-zips

    # Use a matplotlib colormap instead of the default palette
    python scripts/generate_zipcode_overlay.py --town "Hoboken" --colormap Pastel1

    # Town with disambiguation
    python scripts/generate_zipcode_overlay.py --town "Lawrence" --county Mercer

    # All towns (batch mode)
    python scripts/generate_zipcode_overlay.py --all

    # Preview in browser
    python scripts/generate_zipcode_overlay.py --town "Hoboken" --preview
"""

import argparse
import colorsys
import csv
import json
import sys
import webbrowser
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.patches import Polygon as MplPolygon
from adjustText import adjust_text

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils.nj_geodata import (
    load_shapefile,
    load_zcta_shapefile,
    lookup_town,
    get_display_name,
    get_county_name,
    get_overlapping_zctas,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_config():
    """Load zipcode overlay settings from config.json."""
    config_path = REPO_ROOT / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            cfg = json.load(f)
        return cfg.get("zipcode_overlay", {})
    return {}


def sanitize_filename(name):
    """Sanitize a town name for use as a filename/directory name."""
    clean = name.replace(" ", "_")
    clean = "".join(c for c in clean if c.isalnum() or c in ("_", "-"))
    return clean


def get_output_path(town_name, town_number=None, output_dir=None):
    """Build the output file path for a town's zip code overlay."""
    if output_dir:
        base = Path(output_dir)
    else:
        base = REPO_ROOT / "assets"

    if town_number:
        folder = f"{town_number}-{sanitize_filename(town_name)}"
    else:
        folder = sanitize_filename(town_name)

    return base / folder / "zipcode_overlay.png"


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


def _hex_to_rgb(hex_color):
    """Convert hex color string to (r, g, b) floats in [0, 1]."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))


def _rgb_to_hex(r, g, b):
    """Convert (r, g, b) floats in [0, 1] to hex string."""
    return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))


def mute_color(hex_color, saturation_factor=0.6):
    """
    Reduce the saturation of a hex color to create a muted variant.

    Parameters
    ----------
    hex_color : str
        Hex color like "#4E79A7".
    saturation_factor : float
        Multiply saturation by this factor (0.0 = grayscale, 1.0 = unchanged).

    Returns
    -------
    str
        Muted hex color.
    """
    r, g, b = _hex_to_rgb(hex_color)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    s *= saturation_factor
    # Also lighten slightly for better visual distinction
    l = min(1.0, l + (1.0 - l) * 0.3)
    r2, g2, b2 = colorsys.hls_to_rgb(h, l, s)
    return _rgb_to_hex(r2, g2, b2)


def get_zip_colors(n_zips, palette=None, colormap_name=None):
    """
    Generate a list of colors for N zip code zones.

    Parameters
    ----------
    n_zips : int
        Number of zip code zones to color.
    palette : list of str, optional
        List of hex colors to cycle through.
    colormap_name : str, optional
        Matplotlib colormap name (overrides palette if provided).

    Returns
    -------
    list of str
        Hex color strings.
    """
    if colormap_name:
        cmap = plt.get_cmap(colormap_name)
        colors = []
        for i in range(n_zips):
            rgba = cmap(i / max(n_zips - 1, 1))
            colors.append(_rgb_to_hex(rgba[0], rgba[1], rgba[2]))
        return colors

    if palette is None:
        palette = [
            "#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
            "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC",
        ]

    return [palette[i % len(palette)] for i in range(n_zips)]


def _plot_polygon(ax, polygon, facecolor, edgecolor, linewidth, alpha=1.0):
    """Plot a single filled polygon."""
    exterior_coords = list(polygon.exterior.coords)
    patch = MplPolygon(
        exterior_coords,
        closed=True,
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=linewidth,
        alpha=alpha,
    )
    ax.add_patch(patch)

    for interior in polygon.interiors:
        hole_coords = list(interior.coords)
        hole_patch = MplPolygon(
            hole_coords,
            closed=True,
            facecolor="white",
            edgecolor=edgecolor,
            linewidth=linewidth * 0.5,
            alpha=alpha,
        )
        ax.add_patch(hole_patch)


def _plot_geometry(ax, geom, facecolor, edgecolor, linewidth, alpha=1.0):
    """Plot a geometry (handles Polygon and MultiPolygon)."""
    if geom.is_empty:
        return
    if geom.geom_type == "Polygon":
        _plot_polygon(ax, geom, facecolor, edgecolor, linewidth, alpha)
    elif geom.geom_type == "MultiPolygon":
        for poly in geom.geoms:
            _plot_polygon(ax, poly, facecolor, edgecolor, linewidth, alpha)
    elif geom.geom_type == "GeometryCollection":
        for g in geom.geoms:
            if g.geom_type in ("Polygon", "MultiPolygon"):
                _plot_geometry(ax, g, facecolor, edgecolor, linewidth, alpha)


def _plot_boundary(ax, geom, color, linewidth):
    """Plot just the boundary of a geometry as a line."""
    if geom.geom_type == "Polygon":
        x, y = geom.exterior.xy
        ax.plot(x, y, color=color, linewidth=linewidth, solid_capstyle="round")
        for interior in geom.interiors:
            x, y = interior.xy
            ax.plot(x, y, color=color, linewidth=linewidth, solid_capstyle="round")
    elif geom.geom_type == "MultiPolygon":
        for poly in geom.geoms:
            _plot_boundary(ax, poly, color, linewidth)


def render_zipcode_overlay(town_row, gdf, zcta_gdf, show_full_zips=False,
                           colormap_name=None, config=None):
    """
    Render a zip code overlay map for a municipality.

    Parameters
    ----------
    town_row : GeoSeries
        The target town row from the municipality shapefile.
    gdf : GeoDataFrame
        Full NJ municipality shapefile.
    zcta_gdf : GeoDataFrame
        NJ-area ZCTA shapefile.
    show_full_zips : bool
        If True, show full ZCTA extents beyond the municipality boundary.
    colormap_name : str, optional
        Matplotlib colormap name to override the default palette.
    config : dict, optional
        Override settings from config.json.

    Returns
    -------
    fig : matplotlib.figure.Figure
    """
    cfg = load_config()
    if config:
        cfg.update(config)

    palette = cfg.get("palette")
    outside_sat = cfg.get("outside_saturation", 0.6)
    outside_alpha = cfg.get("outside_alpha", 0.4)
    boundary_color = cfg.get("boundary_color", "#222222")
    boundary_width = cfg.get("boundary_width", 1.5)
    muni_boundary_color = cfg.get("municipality_boundary_color", "#000000")
    muni_boundary_width = cfg.get("municipality_boundary_width", 2.5)
    label_font_size = cfg.get("label_font_size", 10)

    town_geom = town_row.geometry

    # Find overlapping ZCTAs
    overlapping = get_overlapping_zctas(town_row, zcta_gdf=zcta_gdf)

    if len(overlapping) == 0:
        print("    Warning: no ZCTAs found overlapping this municipality")

    # Assign colors
    colors = get_zip_colors(
        len(overlapping), palette=palette, colormap_name=colormap_name,
    )

    # Determine zip code column name
    zcta_col = "ZCTA5CE20"
    if zcta_col not in overlapping.columns:
        # Fallback: try other common column names
        for col in ("ZCTA5CE10", "GEOID20", "GEOID10", "GEOID"):
            if col in overlapping.columns:
                zcta_col = col
                break

    # Compute view bounds
    if show_full_zips and len(overlapping) > 0:
        all_geoms = list(overlapping.geometry) + [town_geom]
        from shapely.ops import unary_union
        combined = unary_union(all_geoms)
        minx, miny, maxx, maxy = combined.bounds
    else:
        minx, miny, maxx, maxy = town_geom.bounds

    width = maxx - minx
    height = maxy - miny
    pad_x = width * 0.10
    pad_y = height * 0.10

    # Figure sizing
    max_dim_inches = 10.0
    aspect = width / height if height > 0 else 1.0
    if aspect >= 1:
        fig_w = max_dim_inches
        fig_h = max_dim_inches / aspect
    else:
        fig_h = max_dim_inches
        fig_w = max_dim_inches * aspect
    fig_w = max(fig_w, 6.0)
    fig_h = max(fig_h, 6.0)

    fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    # Draw zip code zones
    texts = []
    for i, (_, zcta_row) in enumerate(overlapping.iterrows()):
        zcta_geom = zcta_row.geometry
        color = colors[i]
        zip_code = str(zcta_row.get(zcta_col, ""))

        # Clipped portion (inside municipality)
        clipped = zcta_geom.intersection(town_geom)

        if show_full_zips:
            # Outside portion (beyond municipality)
            outside = zcta_geom.difference(town_geom)
            muted = mute_color(color, outside_sat)
            _plot_geometry(ax, outside, muted, boundary_color, boundary_width * 0.5,
                           alpha=outside_alpha)

        # Inside portion at full color
        _plot_geometry(ax, clipped, color, boundary_color, boundary_width)

        # Label at centroid of clipped geometry (always inside the town)
        if not clipped.is_empty:
            label_point = clipped.centroid
            # If centroid falls outside the clipped geometry, use representative_point
            if not clipped.contains(label_point):
                label_point = clipped.representative_point()
            txt = ax.text(
                label_point.x,
                label_point.y,
                zip_code,
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

    # Draw municipality boundary on top
    _plot_boundary(ax, town_geom, muni_boundary_color, muni_boundary_width)

    # Set view limits
    ax.set_xlim(minx - pad_x, maxx + pad_x)
    ax.set_ylim(miny - pad_y, maxy + pad_y)
    ax.set_aspect("equal")
    ax.axis("off")

    # Prevent overlapping labels
    if texts:
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


def generate_single(town_name, county=None, output_dir=None, town_number=None,
                    show_full_zips=False, colormap_name=None, preview=False,
                    config=None):
    """Generate a zip code overlay map for a single town."""
    gdf = load_shapefile()
    zcta_gdf = load_zcta_shapefile()
    town = lookup_town(town_name, county=county, gdf=gdf)

    display_name = get_display_name(town)
    town_county = get_county_name(town.get("COUNTYFP", ""))

    print(f"  Generating zipcode overlay: {display_name} ({town_county} County)")

    fig = render_zipcode_overlay(
        town, gdf, zcta_gdf,
        show_full_zips=show_full_zips,
        colormap_name=colormap_name,
        config=config,
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


def generate_all(output_dir=None, show_full_zips=False, colormap_name=None,
                 config=None):
    """Generate zip code overlay maps for all 564 towns."""
    gdf = load_shapefile()
    zcta_gdf = load_zcta_shapefile()
    towns_csv = load_towns_csv()

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
            fig = render_zipcode_overlay(
                town_row, gdf, zcta_gdf,
                show_full_zips=show_full_zips,
                colormap_name=colormap_name,
                config=config,
            )

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
        description="Generate zip code overlay maps for NJ municipalities"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--town", help="Town name to generate map for")
    group.add_argument("--all", action="store_true", help="Generate for all 564 towns")

    parser.add_argument("--county", help="County name for disambiguation")
    parser.add_argument("--output-dir", help="Output directory (default: assets/)")
    parser.add_argument("--preview", action="store_true", help="Open result in browser")
    parser.add_argument(
        "--show-full-zips", action="store_true",
        help="Show full zip code extents beyond the municipality boundary",
    )
    parser.add_argument(
        "--colormap",
        help="Matplotlib colormap name (e.g., Pastel1, tab20, Set3) to override palette",
    )
    parser.add_argument("--dpi", type=int, help="Override output DPI")
    parser.add_argument("--town-number", help="Town visit number (for folder naming)")

    args = parser.parse_args()

    config = {}
    if args.dpi:
        config["output_dpi"] = args.dpi

    if args.all:
        generate_all(
            output_dir=args.output_dir,
            show_full_zips=args.show_full_zips,
            colormap_name=args.colormap,
            config=config or None,
        )
    else:
        generate_single(
            town_name=args.town,
            county=args.county,
            output_dir=args.output_dir,
            town_number=args.town_number,
            show_full_zips=args.show_full_zips,
            colormap_name=args.colormap,
            preview=args.preview,
            config=config or None,
        )


if __name__ == "__main__":
    main()
