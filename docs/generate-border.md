# generate_border.py

Generates red border outlines of town boundaries on transparent PNG backgrounds from TIGER/Line shapefiles. Replaces the manual workflow of tracing Google Maps borders in Paint.NET.

## Prerequisites

- Python packages: `geopandas`, `matplotlib`, `numpy`, `shapely`
- TIGER/Line shapefile downloaded (run `python scripts/download_tiger.py` first)
- Uses the shared [nj_geodata](nj-geodata.md) utility library

## Usage

### Single town

```bash
python scripts/generate_border.py --town "Hoboken"
```

### Town with disambiguation

Some town names exist in multiple counties (e.g., there are six "Washington" entries). Use `--county` to specify which one:

```bash
python scripts/generate_border.py --town "Washington Township" --county Morris
```

### All towns (batch mode)

```bash
python scripts/generate_border.py --all
```

### With options

```bash
python scripts/generate_border.py --town "Hoboken" \
  --output-dir assets/ \
  --preview \
  --svg \
  --dpi 300 \
  --color "#FF0000" \
  --width 10 \
  --town-number "1"
```

## CLI Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--town NAME` | Yes (or `--all`) | Town name to generate the border for |
| `--all` | Yes (or `--town`) | Generate borders for all 564 towns |
| `--county NAME` | No | County name for disambiguation (e.g., `Morris`) |
| `--output-dir PATH` | No | Output base directory (default: `assets/`) |
| `--town-number N` | No | Town visit number, used in folder naming |
| `--preview` | No | Open the resulting PNG in the default browser |
| `--svg` | No | Also generate an SVG version alongside the PNG |
| `--dpi N` | No | Override output DPI (default from config: 300) |
| `--color HEX` | No | Override line color in hex (e.g., `#FF0000`) |
| `--width N` | No | Override line width in pixels |

`--town` and `--all` are mutually exclusive — specify one or the other.

## Configuration

Settings are read from the `border_outline` section of `config.json`:

| Key | Default | Description |
|-----|---------|-------------|
| `line_color` | `#FF0000` | Border line color (red) |
| `line_width_px` | `10` | Line width in pixels |
| `output_dpi` | `300` | Output image DPI |
| `crs` | `EPSG:32618` | Coordinate reference system (UTM Zone 18N) |

CLI arguments (`--dpi`, `--color`, `--width`) override these config values.

## Output

```
assets/
├── 1-Hoboken/
│   ├── border_outline.png
│   └── border_outline.svg    (if --svg)
├── 2-Jersey_City/
│   └── border_outline.png
└── ...
```

- Folder names use the format `{town_number}-{town_name}` if a town number is provided, otherwise just `{town_name}`
- Spaces in town names are replaced with underscores
- PNGs have a transparent background

## Edge Cases

- **Disambiguation required**: Towns like "Washington Township" exist in multiple counties. Without `--county`, the script raises a `ValueError` listing the matching counties. Always use `--county` for ambiguous names.
- **MultiPolygon geometries**: Some towns have non-contiguous territory (enclaves). The script renders all parts of a MultiPolygon geometry, including separate land masses.
- **Interior holes**: Polygons with interior rings (e.g., a borough surrounded by a township) render the holes correctly as separate boundary lines.
- **Shapefile must exist**: The script fails with a clear error if the TIGER/Line shapefile hasn't been downloaded. Run `python scripts/download_tiger.py` first.
- **Batch mode duration**: `--all` processes all 564 towns sequentially. Expect this to take several minutes. Progress is printed as `[N/564]` for each town.
- **Batch error handling**: In `--all` mode, if a single town fails, the error is printed and the script continues with the remaining towns. A summary of successes and failures is printed at the end.
- **Line width approximation**: The conversion from pixel width to matplotlib points is approximate (`line_width_px * 0.5`). The rendered line may not be exactly the specified pixel width.
- **Town name matching**: The script uses the flexible matching strategy from `nj_geodata.lookup_town` — see the [nj_geodata docs](nj-geodata.md) for details on how names are resolved.
