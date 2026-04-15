# nj_geodata.py (Utility Library)

Shared geographic data utilities for all map-based scripts. Provides wrappers around TIGER/Line shapefiles for town lookup, neighbor queries, centroid/bounds calculations, and CRS reprojection.

This is not a CLI tool — it is a Python library imported by other scripts.

## Prerequisites

- Python packages: `geopandas`, `shapely`
- TIGER/Line shapefile downloaded (run `python scripts/download_tiger.py` first)

## Usage

```python
from utils.nj_geodata import load_shapefile, lookup_town, get_neighbors, get_display_name

# Load the shapefile (cached after first call)
gdf = load_shapefile()

# Look up a single town
town = lookup_town("Hoboken", gdf=gdf)

# Get neighboring municipalities
neighbors = get_neighbors(town, gdf=gdf)

# Get the display name
name = get_display_name(town)  # "Hoboken"
```

## Functions

### `load_shapefile(shapefile_path=None, target_crs="EPSG:32618")`

Loads the TIGER/Line county subdivision shapefile for NJ and reprojects it to UTM Zone 18N.

- **Returns**: `GeoDataFrame` with all NJ county subdivisions
- **Caching**: Results are cached with `@lru_cache(maxsize=1)`. The shapefile is loaded from disk only once per Python process.
- **Default path**: Reads `paths.tiger_shapefile` from `config.json`, falling back to `data/tl_2025_34_cousub/tl_2025_34_cousub.shp`
- **Raises**: `FileNotFoundError` with download instructions if the shapefile is missing

### `lookup_town(town_name, county=None, gdf=None)`

Finds a municipality in the shapefile by name. Uses a multi-step matching strategy:

1. **Exact match on NAME** — e.g., `"Hoboken"` matches the NAME column
2. **Exact match on NAMELSAD** — e.g., `"Hoboken city"` matches the long name
3. **Prefix match on NAMELSAD** — e.g., `"Hoboken"` matches `"Hoboken city"`
4. **Substring match on NAMELSAD** — e.g., `"Cherry Hill"` matches `"Cherry Hill township"`

- **Returns**: Single `GeoSeries` row
- **Disambiguation**: If multiple matches are found and `county` is provided, filters by county FIPS code
- **Raises**: `ValueError` if no match found (lists first 10 available names) or if multiple matches found without a county specified

### `get_neighbors(town_row, gdf=None)`

Finds all municipalities sharing a border with the given town using shapely `touches()` and `intersects()`.

- **Returns**: `GeoDataFrame` of neighboring municipalities (excludes the town itself)

### `get_centroid(town_row)`

Returns the centroid `Point` of a municipality's geometry.

### `get_bounds(town_row)`

Returns the bounding box as `(minx, miny, maxx, maxy)`.

### `get_display_name(town_row)`

Returns the short name (e.g., `"Hoboken"`) rather than the full NAMELSAD (e.g., `"Hoboken city"`).

### `get_county_name(county_fips)`

Converts a county FIPS code to a county name (e.g., `"017"` → `"Hudson"`). Uses a hardcoded mapping for all 21 NJ counties.

### `get_all_towns(gdf=None)`

Returns a sorted list of all municipalities as dicts with keys: `name`, `namelsad`, `county`, `county_fips`, `geoid`. Sorted by county then name.

## Edge Cases

- **Shapefile caching**: Because `load_shapefile()` is decorated with `@lru_cache`, changes to the shapefile on disk are not reflected until the Python process is restarted.
- **UTM projection**: The default CRS (`EPSG:32618`, UTM Zone 18N) is optimized for New Jersey. Using this library for other states would require a different CRS.
- **Hardcoded FIPS mappings**: County FIPS-to-name mappings are hardcoded for NJ's 21 counties. These are stable (FIPS codes rarely change) but must be kept in sync with Census Bureau data.
- **Ambiguous town names**: Six municipalities share the name "Washington" (five townships and one borough across different counties). The `lookup_town` function requires `--county` for disambiguation, or it raises a `ValueError` listing the matching counties.
- **Prefix/substring matching**: The flexible matching strategy can match unintended towns if the search string is too short or generic. Be as specific as possible with town names.
