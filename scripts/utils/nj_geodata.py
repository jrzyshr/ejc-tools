"""
Shared NJ geographic data utilities.

Loads US Census TIGER/Line shapefiles for NJ county subdivisions and provides
helpers for town lookup, neighbor queries, centroid/bounds, and reprojection.
Also loads ZCTA (ZIP Code Tabulation Area) data for zip code overlays.

Used by: generate_border.py, generate_labeled_map.py, generate_zipcode_overlay.py
"""

import json
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

# Default paths (relative to repo root)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_CONFIG = _REPO_ROOT / "config.json"


def _load_config():
    """Load config.json from the repo root."""
    if _DEFAULT_CONFIG.exists():
        with open(_DEFAULT_CONFIG) as f:
            return json.load(f)
    return {}


@lru_cache(maxsize=1)
def load_shapefile(shapefile_path=None, target_crs="EPSG:32618"):
    """
    Load the TIGER/Line county subdivision shapefile for NJ.

    Parameters
    ----------
    shapefile_path : str or Path, optional
        Path to the .shp file. Defaults to config.json paths.tiger_shapefile.
    target_crs : str
        Target CRS for reprojection. Default EPSG:32618 (UTM Zone 18N)
        gives proper proportions for NJ.

    Returns
    -------
    geopandas.GeoDataFrame
        All NJ county subdivisions, reprojected to target_crs.
    """
    if shapefile_path is None:
        cfg = _load_config()
        shapefile_path = _REPO_ROOT / cfg.get("paths", {}).get(
            "tiger_shapefile", "data/tl_2025_34_cousub/tl_2025_34_cousub.shp"
        )
    shapefile_path = Path(shapefile_path)

    if not shapefile_path.exists():
        raise FileNotFoundError(
            f"Shapefile not found: {shapefile_path}\n"
            f"Download from: https://www.census.gov/cgi-bin/geo/shapefiles/index.php\n"
            f"Select: Year=2024, Layer Type=County Subdivisions, State=New Jersey\n"
            f"Extract the zip to: {shapefile_path.parent}"
        )

    gdf = gpd.read_file(shapefile_path)

    # The TIGER file for state FIPS 34 (NJ) should only contain NJ,
    # but filter just in case a combined file is used
    if "STATEFP" in gdf.columns:
        gdf = gdf[gdf["STATEFP"] == "34"].copy()

    # Reproject to UTM for proper proportions
    if target_crs:
        gdf = gdf.to_crs(target_crs)

    # Normalize the NAME column for easier matching
    if "NAME" in gdf.columns:
        gdf["name_clean"] = gdf["NAME"].str.strip()
    if "NAMELSAD" in gdf.columns:
        gdf["namelsad_clean"] = gdf["NAMELSAD"].str.strip()

    return gdf


def _county_fips_to_name():
    """Map NJ county FIPS codes to county names."""
    return {
        "001": "Atlantic",
        "003": "Bergen",
        "005": "Burlington",
        "007": "Camden",
        "009": "Cape May",
        "011": "Cumberland",
        "013": "Essex",
        "015": "Gloucester",
        "017": "Hudson",
        "019": "Hunterdon",
        "021": "Mercer",
        "023": "Middlesex",
        "025": "Monmouth",
        "027": "Morris",
        "029": "Ocean",
        "031": "Passaic",
        "033": "Salem",
        "035": "Somerset",
        "037": "Sussex",
        "039": "Union",
        "041": "Warren",
    }


def _county_name_to_fips():
    """Map county names to FIPS codes."""
    return {v: k for k, v in _county_fips_to_name().items()}


def get_county_name(county_fips):
    """Convert a county FIPS code to the county name."""
    return _county_fips_to_name().get(county_fips, county_fips)


def lookup_town(town_name, county=None, gdf=None):
    """
    Find a municipality in the shapefile by name.

    Handles disambiguation for towns with the same name (e.g., five
    "Washington Township" entries) by requiring the county parameter.

    Parameters
    ----------
    town_name : str
        Municipality name. Matches against both NAME (short name, e.g.
        "Hoboken") and NAMELSAD (long name, e.g. "Hoboken city").
    county : str, optional
        County name for disambiguation (e.g., "Hudson").
    gdf : GeoDataFrame, optional
        Pre-loaded shapefile. Loaded automatically if not provided.

    Returns
    -------
    geopandas.GeoSeries
        Single row from the GeoDataFrame.

    Raises
    ------
    ValueError
        If no match found or if multiple matches found without county.
    """
    if gdf is None:
        gdf = load_shapefile()

    name_lower = town_name.strip().lower()

    # Try exact match on NAME first, then NAMELSAD
    mask = gdf["name_clean"].str.lower() == name_lower
    if mask.sum() == 0:
        mask = gdf["namelsad_clean"].str.lower() == name_lower
    if mask.sum() == 0:
        # Try partial match: "Hoboken" matches "Hoboken city"
        mask = gdf["namelsad_clean"].str.lower().str.startswith(name_lower)
    if mask.sum() == 0:
        # Try contains for names like "Cherry Hill" matching "Cherry Hill township"
        mask = gdf["namelsad_clean"].str.lower().str.contains(
            name_lower, regex=False
        )

    matches = gdf[mask]

    if len(matches) == 0:
        available = sorted(gdf["name_clean"].unique())
        raise ValueError(
            f"Town not found: '{town_name}'. "
            f"Available names ({len(available)} total): {available[:10]}..."
        )

    # Filter by county if provided
    if county and len(matches) > 1:
        county_fips = _county_name_to_fips().get(county)
        if county_fips and "COUNTYFP" in matches.columns:
            county_mask = matches["COUNTYFP"] == county_fips
            if county_mask.sum() > 0:
                matches = matches[county_mask]

    if len(matches) > 1:
        counties = [
            get_county_name(row.get("COUNTYFP", "?"))
            for _, row in matches.iterrows()
        ]
        raise ValueError(
            f"Multiple matches for '{town_name}' in counties: {counties}. "
            f"Specify --county to disambiguate."
        )

    return matches.iloc[0]


def get_neighbors(town_row, gdf=None):
    """
    Find all municipalities that share a border with the given town.

    Parameters
    ----------
    town_row : geopandas.GeoSeries
        A single row from the shapefile (as returned by lookup_town).
    gdf : GeoDataFrame, optional
        Pre-loaded shapefile. Loaded automatically if not provided.

    Returns
    -------
    geopandas.GeoDataFrame
        Neighboring municipalities.
    """
    if gdf is None:
        gdf = load_shapefile()

    geom = town_row.geometry
    # touches() finds polygons sharing a boundary; we also include
    # intersects() to catch overlapping/adjacent cases
    neighbor_mask = gdf.geometry.touches(geom) | (
        gdf.geometry.intersects(geom)
        & (gdf.index != town_row.name if hasattr(town_row, "name") else True)
    )

    neighbors = gdf[neighbor_mask]

    # Exclude the town itself
    if "GEOID" in gdf.columns and "GEOID" in town_row.index:
        neighbors = neighbors[neighbors["GEOID"] != town_row["GEOID"]]

    return neighbors


def get_centroid(town_row):
    """Get the centroid point of a municipality geometry."""
    return town_row.geometry.centroid


def get_bounds(town_row):
    """Get the bounding box (minx, miny, maxx, maxy) of a municipality."""
    return town_row.geometry.bounds


def get_display_name(town_row):
    """
    Get a clean display name for a municipality.

    Uses the short NAME (e.g., "Hoboken") rather than the full NAMELSAD
    (e.g., "Hoboken city").
    """
    return town_row.get("name_clean", town_row.get("NAME", "Unknown"))


def get_all_towns(gdf=None):
    """
    Get a sorted list of all municipality names with their counties.

    Returns
    -------
    list of dict
        Each dict has keys: name, namelsad, county, county_fips, geoid
    """
    if gdf is None:
        gdf = load_shapefile()

    towns = []
    for _, row in gdf.iterrows():
        towns.append({
            "name": row.get("name_clean", row.get("NAME", "")),
            "namelsad": row.get("namelsad_clean", row.get("NAMELSAD", "")),
            "county": get_county_name(row.get("COUNTYFP", "")),
            "county_fips": row.get("COUNTYFP", ""),
            "geoid": row.get("GEOID", ""),
        })

    return sorted(towns, key=lambda t: (t["county"], t["name"]))


@lru_cache(maxsize=1)
def load_zcta_shapefile(shapefile_path=None, target_crs="EPSG:32618"):
    """
    Load the ZCTA (ZIP Code Tabulation Area) shapefile, filtered to NJ area.

    The ZCTA file is a national dataset. This function filters to ZCTAs that
    intersect the bounding box of NJ (derived from the municipality shapefile)
    to avoid keeping all ~33k US ZCTAs in memory.

    Parameters
    ----------
    shapefile_path : str or Path, optional
        Path to the ZCTA .shp file. Defaults to config.json paths.zcta_shapefile.
    target_crs : str
        Target CRS for reprojection. Default EPSG:32618 (UTM Zone 18N).

    Returns
    -------
    geopandas.GeoDataFrame
        NJ-area ZCTAs, reprojected to target_crs.
    """
    if shapefile_path is None:
        cfg = _load_config()
        shapefile_path = _REPO_ROOT / cfg.get("paths", {}).get(
            "zcta_shapefile",
            "data/tl_2025_us_zcta520/tl_2025_us_zcta520.shp",
        )
    shapefile_path = Path(shapefile_path)

    if not shapefile_path.exists():
        raise FileNotFoundError(
            f"ZCTA shapefile not found: {shapefile_path}\n"
            f"Download with: python scripts/download_tiger.py --zcta\n"
            f"Or manually from: https://www.census.gov/cgi-bin/geo/shapefiles/index.php\n"
            f"  Select Year: 2024, Layer Type: ZIP Code Tabulation Areas\n"
            f"  Download the national file and extract to: {shapefile_path.parent}"
        )

    # Load NJ municipality bounds to create a spatial filter
    muni_gdf = load_shapefile(target_crs=None)  # keep in original CRS for bbox
    nj_bounds = muni_gdf.total_bounds  # minx, miny, maxx, maxy
    # Add generous padding to catch ZCTAs that straddle the NJ border
    pad = 0.1  # ~0.1 degrees ≈ 11km
    nj_bbox = box(
        nj_bounds[0] - pad, nj_bounds[1] - pad,
        nj_bounds[2] + pad, nj_bounds[3] + pad,
    )

    # Read with bounding box filter for performance
    zcta_gdf = gpd.read_file(shapefile_path, bbox=nj_bbox)

    if target_crs:
        zcta_gdf = zcta_gdf.to_crs(target_crs)

    return zcta_gdf


def get_overlapping_zctas(town_row, zcta_gdf=None):
    """
    Find all ZCTAs that overlap with the given municipality.

    Parameters
    ----------
    town_row : geopandas.GeoSeries
        A single row from the municipality shapefile.
    zcta_gdf : GeoDataFrame, optional
        Pre-loaded ZCTA shapefile. Loaded automatically if not provided.

    Returns
    -------
    geopandas.GeoDataFrame
        ZCTAs that intersect the municipality polygon.
    """
    if zcta_gdf is None:
        zcta_gdf = load_zcta_shapefile()

    geom = town_row.geometry
    mask = zcta_gdf.geometry.intersects(geom)
    overlapping = zcta_gdf[mask].copy()

    # Filter out ZCTAs with negligible overlap (< 0.1% of town area)
    town_area = geom.area
    if town_area > 0:
        overlapping["_overlap_area"] = overlapping.geometry.intersection(geom).area
        overlapping = overlapping[
            overlapping["_overlap_area"] > town_area * 0.001
        ].copy()
        overlapping = overlapping.drop(columns=["_overlap_area"])

    return overlapping
