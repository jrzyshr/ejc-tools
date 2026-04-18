# generate_flyin.py

Generates Google Earth-style fly-in videos for NJ municipalities. Renders a 3D globe fly-in animation using Cesium.js in a headless browser (Playwright), zooming from a world view down to the town's border with a red border overlay fading in at the end.

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

The default animation is 9 seconds. All five animation phases scale proportionally:

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

## CLI Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--town NAME` | Yes (or `--all`) | Town name to generate the fly-in for |
| `--all` | Yes (or `--town`) | Generate fly-ins for all 564 towns |
| `--county NAME` | No | County name for disambiguation (e.g., `Mercer`) |
| `--output-dir PATH` | No | Output base directory (default: `assets/`) |
| `--town-number N` | No | Town visit number, used in folder naming |
| `--duration SECONDS` | No | Animation duration (default from config: 9s). All phases scale proportionally. |
| `--preview` | No | Open the resulting video in the default player |
| `--no-border` | No | Skip the red border polygon overlay |

`--town` and `--all` are mutually exclusive — specify one or the other.

## Animation Phases

The animation consists of five phases, each defined as a percentage of the total duration. Changing `--duration` scales all phases proportionally:

| Phase | Description | Default % | At 9s | At 6s | At 12s |
|-------|-------------|-----------|-------|-------|--------|
| Globe hold | Slow drift centering on eastern US | 0–11% | 0–1.0s | 0–0.7s | 0–1.3s |
| Globe → state | Zoom from globe to NJ state level | 11–44% | 1.0–4.0s | 0.7–2.6s | 1.3–5.3s |
| State → town | Zoom from state to town level | 44–72% | 4.0–6.5s | 2.6–4.3s | 5.3–8.6s |
| Border fade-in | Red border polygon fades in | 72–89% | 6.5–8.0s | 4.3–5.3s | 8.6–10.7s |
| Final hold | Hold framed view with border | 89–100% | 8.0–9.0s | 5.3–6.0s | 10.7–12.0s |

Phase percentages are configurable in `config.json` under `flyin.phases_pct`.

## Configuration

Settings are read from the `flyin` section of `config.json`:

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
