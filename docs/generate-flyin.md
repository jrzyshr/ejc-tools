# generate_flyin.py

Generates Google Earth-style fly-in videos for NJ municipalities. Renders a 3D globe fly-in animation using Cesium.js in a headless browser (Playwright), zooming from a world view down to the town's border. The red border overlay is visible throughout the animation, zooming in naturally with the camera.

Replaces the manual workflow of screen-recording a Google Earth search on an iPhone, which required manually dismissing info cards, cropping out UI elements, and syncing files via OneDrive.

## Prerequisites

- Python packages: `playwright`, `geopandas`, `shapely`
- Playwright browser: `playwright install chromium` (one-time)
- `ffmpeg` installed: `brew install ffmpeg`
- TIGER/Line shapefile downloaded: `python scripts/download_tiger.py`
- Cesium Ion access token (free): see [Setup](#cesium-ion-setup) below
- Uses the shared [nj_geodata](nj-geodata.md) utility library

## Cesium Ion Setup

1. Sign up for a free account at [cesium.com/ion](https://ion.cesium.com/)
2. Create an access token at [ion.cesium.com/tokens](https://ion.cesium.com/tokens)
3. Set the environment variable:

```bash
export CESIUM_ION_TOKEN='your-token-here'
```

The free tier includes 5 million tile accesses per month, which is more than sufficient for all 564 towns.

## Usage

### Single town

```bash
python scripts/generate_flyin.py --town "Hoboken"
```

### Town with disambiguation

```bash
python scripts/generate_flyin.py --town "Washington Township" --county Morris
```

### Custom duration

The default animation is 9 seconds. All four animation phases scale proportionally:

```bash
python scripts/generate_flyin.py --town "Hoboken" --duration 6
```

### Without border overlay

```bash
python scripts/generate_flyin.py --town "Hoboken" --no-border
```

### All towns (batch mode)

```bash
python scripts/generate_flyin.py --all
```

### With options

```bash
python scripts/generate_flyin.py --town "Hoboken" \
  --town-number 1 \
  --output-dir assets/ \
  --duration 9 \
  --preview
```

### With alias name

```bash
python scripts/generate_flyin.py --town "Hoboken" \
  --town-number 1 \
  --alias-name "Mile Square City"
```

## CLI Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--town NAME` | Yes (or `--all`) | Town name to generate the fly-in for |
| `--all` | Yes (or `--town`) | Generate fly-ins for all 564 towns |
| `--county NAME` | No | County name for disambiguation (e.g., `Mercer`) |
| `--output-dir PATH` | No | Output base directory (default: `assets/`) |
| `--town-number N` | No | Town visit number, used in folder naming and "New Jersey Town #N" overlay |
| `--alias-name NAME` | No | Alternate name shown as "(aka NAME)" in the town name overlay |
| `--duration SECONDS` | No | Animation duration (default from config: 9s). All phases scale proportionally. |
| `--preview` | No | Open the resulting video in the default player |
| `--no-border` | No | Skip the red border polygon overlay |

`--town` and `--all` are mutually exclusive — specify one or the other.

## Animation Phases

The animation consists of four phases, each defined as a percentage of the total duration. The border overlay is visible throughout all phases — it starts as a tiny speck at globe altitude and grows naturally as the camera zooms in. Changing `--duration` scales all phases proportionally:

| Phase | Description | Default % | At 9s | At 6s | At 12s |
|-------|-------------|-----------|-------|-------|--------|
| Globe hold | Slow drift centering on eastern US | 0–11% | 0–1.0s | 0–0.7s | 0–1.3s |
| Globe → state | Zoom from globe to NJ state level | 11–44% | 1.0–4.0s | 0.7–2.6s | 1.3–5.3s |
| State → town | Zoom from state to town level | 44–72% | 4.0–6.5s | 2.6–4.3s | 5.3–8.6s |
| Final hold | Hold framed view with border | 72–100% | 6.5–9.0s | 4.3–6.0s | 8.6–12.0s |

Phase percentages are configurable in `config.json` under `flyin.phases_pct`.

## Configuration

Settings are read from the `flyin` section of `config.json`:

### General

| Key | Default | Description |
|-----|---------|-------------|
| `duration_seconds` | `9` | Default animation duration |
| `camera_start_altitude_m` | `20000000` | Starting altitude (globe view) in meters |
| `camera_end_altitude_offset_m` | `5000` | Extra altitude above auto-calculated town framing |
| `camera_pitch_degrees` | `-30` | Camera pitch at town level (-90 = straight down) |
| `phases_pct` | See above | Phase timing as percentage ranges |
| `border_color` | `#FF0000` | Border polygon color (hex) |
| `border_opacity` | `0.8` | Border polygon opacity (0–1) |
| `cesium_ion_token_env` | `CESIUM_ION_TOKEN` | Environment variable name for the token |
| `output_filename` | `flyin.mp4` | Output filename within the town's asset folder |

The `--duration` CLI argument overrides `duration_seconds`.

### Overlay: Town Number (`overlay.town_number`)

Controls the "New Jersey Town #N" text overlay.

| Key | Default | Description |
|-----|---------|-------------|
| `font_family` | `Source Sans 3` | Google Fonts family name |
| `font_size_px` | `160` | Maximum font size (auto-shrinks to fit) |
| `font_weight` | `900` | CSS font weight (100–900) |
| `font_style` | `normal` | CSS font style (`normal`, `italic`, `oblique`) |
| `font_color` | `#FFFFFF` | Text color (hex) |
| `outline_color` | `#000000` | Text outline color (hex) |
| `outline_size_px` | `8` | Text outline width in pixels |
| `top_pct` | `25` | Vertical position as % from top of video |
| `shadow_blur_px` | `0` | Drop shadow blur radius in pixels |
| `shadow_distance_px` | `10` | Drop shadow offset distance in pixels |
| `shadow_angle_deg` | `135` | Drop shadow direction in degrees (0=right, 90=down, 135=bottom-left) |

### Overlay: Town Name (`overlay.town_name`)

Controls the town name text that appears when the zoom completes.

| Key | Default | Description |
|-----|---------|-------------|
| `font_family` | `Source Sans 3` | Google Fonts family name |
| `font_size_max_px` | `250` | Maximum font size (auto-shrinks for long names) |
| `font_size_min_px` | `100` | Minimum font size floor |
| `font_weight` | `900` | CSS font weight (100–900) |
| `font_style` | `normal` | CSS font style (`normal`, `italic`, `oblique`) |
| `font_color` | `#FFFFFF` | Text color (hex) |
| `outline_color` | `#000000` | Text outline color (hex) |
| `outline_size_px` | `8` | Text outline width in pixels |
| `bottom_pct` | `25` | Vertical position as % from bottom of video |
| `shadow_blur_px` | `0` | Drop shadow blur radius in pixels |
| `shadow_distance_px` | `10` | Drop shadow offset distance in pixels |
| `shadow_angle_deg` | `135` | Drop shadow direction in degrees |

#### County sub-element (`overlay.town_name.county`)

Controls the county name line shown for disambiguation. Each setting inherits its value from the parent `overlay.town_name` by default, but can be overridden by setting it directly in this section.

| Key | Default | Description |
|-----|---------|-------------|
| `font_family` | *(inherits)* | Google Fonts family name |
| `font_size_ratio` | `0.65` | Font size as ratio of the computed town name size |
| `font_weight` | *(inherits)* | CSS font weight |
| `font_style` | *(inherits)* | CSS font style (`normal`, `italic`, `oblique`) |
| `font_color` | *(inherits)* | Text color (hex) |
| `outline_color` | *(inherits)* | Text outline color (hex) |
| `outline_size_ratio` | `0.75` | Outline width as ratio of the parent outline size |
| `shadow_blur_px` | *(inherits)* | Drop shadow blur radius |
| `shadow_distance_px` | *(inherits)* | Drop shadow offset distance |
| `shadow_angle_deg` | *(inherits)* | Drop shadow direction in degrees |

#### Alias sub-element (`overlay.town_name.alias`)

Controls the "(aka …)" line. Each setting inherits its value from the parent `overlay.town_name` by default, but can be overridden by setting it directly in this section.

| Key | Default | Description |
|-----|---------|-------------|
| `font_family` | *(inherits)* | Google Fonts family name |
| `font_size_ratio` | `0.65` | Font size as ratio of the computed town name size |
| `font_weight` | *(inherits)* | CSS font weight |
| `font_style` | *(inherits)* | CSS font style (`normal`, `italic`, `oblique`) |
| `font_color` | *(inherits)* | Text color (hex) |
| `outline_color` | *(inherits)* | Text outline color (hex) |
| `outline_size_ratio` | `0.75` | Outline width as ratio of the parent outline size |
| `shadow_blur_px` | *(inherits)* | Drop shadow blur radius |
| `shadow_distance_px` | *(inherits)* | Drop shadow offset distance |
| `shadow_angle_deg` | *(inherits)* | Drop shadow direction in degrees |

### Overlay: Logo

| Key | Default | Description |
|-----|---------|-------------|
| `overlay.logo_size_px` | `600` | EJC logo dimensions in pixels (square) |
| `overlay.logo_bottom_px` | `40` | Logo margin from bottom edge |
| `overlay.logo_right_px` | `40` | Logo margin from right edge |

## Text Overlays

The fly-in video includes text overlays and a logo that appear over the map animation:

### Overlay 1: Town Number

- **Text**: "New Jersey Town #N" (only shown when `--town-number` is provided)
- **Position**: Centered horizontally, configurable vertical position via `top_pct` (default: 25% from top)
- **Timing**: Visible for the entire duration of the video
- **Font**: Configurable via `overlay.town_number.*` — defaults to Source Sans 3, weight 900, 160px, white with black outline
- **Shadow**: Configurable directional drop shadow (see below)

### Overlay 2: Town Name

- **Position**: Centered horizontally, configurable vertical position via `bottom_pct` (default: 25% from bottom)
- **Timing**: Appears at the instant the zoom animation completes (75% mark)
- **Font**: Configurable via `overlay.town_name.*` — defaults to Source Sans 3, weight 900, dynamically sized 100–250px based on text length
- **Disambiguation rules** (applied independently):
  - **Type suffix**: If the same town name exists with different types in the same county (e.g., Freehold Borough & Freehold Township in Monmouth), the type is appended to the name
  - **County line**: If the same town name exists in multiple counties statewide (e.g., Washington, Franklin), the county name appears on a second line. Font settings configurable independently via `overlay.town_name.county.*` (inherits from parent `town_name` by default)
  - **Font size ratio**: County text defaults to 65% of the computed town name font size
- **Alias**: If `--alias-name` is provided, "(aka <name>)" appears as an additional line. Font settings configurable independently via `overlay.town_name.alias.*` (inherits from parent `town_name` by default)

### Drop Shadow

Each text overlay has configurable directional drop shadow properties:

- **`shadow_blur_px`** — Gaussian blur radius (default: `0` = sharp shadow)
- **`shadow_distance_px`** — Offset distance from the text (default: `10`)
- **`shadow_angle_deg`** — Direction angle in degrees where 0°=right, 90°=down, 135°=bottom-left (default: `135`)

Shadow is set independently for the town number and town name overlays. County and alias sub-elements inherit shadow settings from their parent `town_name` unless explicitly overridden.

### EJC Logo

- **Image**: `images/ejclogo-transparent.png`
- **Position**: Bottom-right corner, configurable margins
- **Timing**: Visible from the start of the video, disappears at the same instant Overlay 2 appears

## Output

```
assets/
├── 1-Hoboken/
│   └── flyin.mp4          ← 1080x1920 (9:16) MP4 video
├── Cherry_Hill/
│   └── flyin.mp4
└── ...
```

Videos are encoded with H.264 (libx264), CRF 18, no audio, with `faststart` for web compatibility.

## How It Works

1. Looks up the town in the TIGER/Line shapefile via `nj_geodata.lookup_town()`
2. Reprojects the town's centroid, bounds, and boundary polygon to WGS84 (EPSG:4326) for Cesium
3. Launches a headless Chromium browser via Playwright at 1080x1920
4. Loads the Cesium.js viewer (3D globe with satellite imagery and terrain)
5. Injects the town configuration and starts the scripted camera animation
6. Playwright records the browser viewport as the animation plays
7. On completion, the raw recording is re-encoded with ffmpeg as an optimized MP4
