# Generate Labeled Map

Auto-generate labeled municipality maps showing a target town (highlighted) and its neighbors. Replaces the manual Paint.NET map creation workflow.

## Prerequisites

- TIGER/Line shapefile downloaded (see [download-tiger.md](download-tiger.md))
- Python dependencies installed: `geopandas`, `matplotlib`, `shapely`, `adjustText`

## Usage

### Single town

```bash
python scripts/generate_labeled_map.py --town "Hoboken"
```

### Disambiguation (multiple towns with same name)

```bash
python scripts/generate_labeled_map.py --town "Lawrence" --county Mercer
```

### Highlight additional towns

```bash
python scripts/generate_labeled_map.py --town "Hoboken" --highlight "Jersey City" "Weehawken"
```

### Batch mode (all 564 towns)

```bash
python scripts/generate_labeled_map.py --all
```

### Preview in browser

```bash
python scripts/generate_labeled_map.py --town "Hoboken" --preview
```

### Custom output directory and DPI

```bash
python scripts/generate_labeled_map.py --town "Hoboken" --output-dir assets/ --dpi 300
```

## Output

Maps are saved to `assets/{town_name}/labeled_map.png` (or `assets/{town_number}-{town_name}/labeled_map.png` when a town number is provided).

## Color scheme

Configured in `config.json` under `labeled_map`:

| Element | Color | Config key |
|---------|-------|------------|
| Target town | Orange (#FF6B35) | `target_fill_color` |
| Neighbors | Light blue (#A8D8EA) | `neighbor_fill_color` |
| Highlighted towns | Yellow (#FFD166) | `highlight_fill_color` |
| Other | Light gray (#E8E8E8) | `default_fill_color` |

## How it works

1. Loads NJ TIGER/Line shapefile (reprojected to UTM Zone 18N)
2. Finds the target town and all adjacent municipalities via `touches()` spatial query
3. Fills polygons with role-based colors (target, neighbor, highlight)
4. Labels each polygon at its centroid with white stroke text
5. Uses `adjustText` to prevent overlapping labels
6. Saves as PNG
