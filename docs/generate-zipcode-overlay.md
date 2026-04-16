# Generate Zip Code Overlay

Generate maps showing a municipality's shape with ZIP code (ZCTA) zone boundaries overlaid. Each zip code area gets a distinct color. Optionally shows full zip code extents beyond the municipality boundary with muted colors.

## Prerequisites

- TIGER/Line county subdivision shapefile downloaded (see [download-tiger.md](download-tiger.md))
- ZCTA shapefile downloaded: `python scripts/download_tiger.py --zcta`
- Python dependencies installed: `geopandas`, `matplotlib`, `shapely`, `adjustText`

## Usage

### Single town

```bash
python scripts/generate_zipcode_overlay.py --town "Hoboken"
```

### Disambiguation (multiple towns with same name)

```bash
python scripts/generate_zipcode_overlay.py --town "Lawrence" --county Mercer
```

### Show full zip code extents beyond municipality

```bash
python scripts/generate_zipcode_overlay.py --town "Hoboken" --show-full-zips
```

Inside portions render at full color; outside portions are desaturated and translucent so the municipality boundary remains clear.

### Use a matplotlib colormap

```bash
python scripts/generate_zipcode_overlay.py --town "Hoboken" --colormap Pastel1
```

Any [matplotlib colormap name](https://matplotlib.org/stable/gallery/color/colormap_reference.html) works (e.g., `Set3`, `tab20`, `Paired`). Overrides the default palette for that run.

### Batch mode (all 564 towns)

```bash
python scripts/generate_zipcode_overlay.py --all
```

### Preview in browser

```bash
python scripts/generate_zipcode_overlay.py --town "Hoboken" --preview
```

### Custom output directory and DPI

```bash
python scripts/generate_zipcode_overlay.py --town "Hoboken" --output-dir assets/ --dpi 300
```

## Output

Maps are saved to `assets/{town_name}/zipcode_overlay.png` (or `assets/{town_number}-{town_name}/zipcode_overlay.png` when a town number is provided).

## Color scheme

Configured in `config.json` under `zipcode_overlay`:

| Setting | Default | Description |
|---------|---------|-------------|
| `palette` | 10-color Tableau-like | List of hex colors cycled for zip zones |
| `outside_saturation` | `0.6` | Saturation multiplier for outside-boundary portions |
| `outside_alpha` | `0.4` | Opacity for outside-boundary portions |
| `boundary_color` | `#222222` | Zip code zone boundary line color |
| `boundary_width` | `1.5` | Zip code zone boundary line width |
| `municipality_boundary_color` | `#000000` | Municipality outline color |
| `municipality_boundary_width` | `2.5` | Municipality outline width |
| `label_font_size` | `10` | Zip code label font size |
| `output_dpi` | `200` | Output image DPI |

## How it works

1. Loads NJ municipality shapefile and national ZCTA shapefile (both reprojected to UTM Zone 18N)
2. ZCTA data is filtered to NJ area via bounding box on load (cached after first load)
3. Finds ZCTAs overlapping the target municipality via `intersects()`, filters out negligible overlaps (<0.1% of town area)
4. Assigns each ZCTA a color from the palette (cycles if more zips than colors) or from the `--colormap`
5. **Default mode**: clips each ZCTA to the municipality boundary via `intersection()`, draws clipped polygons
6. **`--show-full-zips` mode**: draws full ZCTA polygons — inside at full color, outside desaturated via HSL manipulation + alpha
7. Draws municipality boundary on top with thick black outline
8. Labels each zip code at the centroid of its clipped geometry (always inside the town), black text with white stroke
9. Uses `adjustText` to prevent overlapping labels
10. Saves as PNG

## Data source

Uses Census Bureau **ZCTA** (ZIP Code Tabulation Areas) — generalized polygon approximations of USPS ZIP Code service areas built from 2020 Census tabulation blocks. ZCTAs approximate but don't perfectly match USPS delivery routes. The national file (~500MB) is required because no per-state ZCTA files are available.
