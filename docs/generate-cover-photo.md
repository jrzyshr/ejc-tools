# generate_cover_photo.py

Generates 1080x1920 (9:16) Instagram Reel cover photos with town name, town number, and #eatjerseychallenge text overlays. Replaces the Instagram story editor round-trip for cover photo creation.

## Prerequisites

- Python packages: `Pillow`
- Montserrat font files in `scripts/utils/fonts/` (included in the repo)

## Usage

### Basic usage

```bash
python scripts/generate_cover_photo.py --photo path/to/photo.jpg \
    --town "Hoboken" --town-number 1
```

### Custom output directory

```bash
python scripts/generate_cover_photo.py --photo path/to/photo.jpg \
    --town "Hoboken" --town-number 1 --output-dir assets/
```

### Override font sizes

```bash
python scripts/generate_cover_photo.py --photo path/to/photo.jpg \
    --town "Hoboken" --town-number 1 \
    --font-size-town 80 --font-size-number 48
```

### Preview in browser

```bash
python scripts/generate_cover_photo.py --photo path/to/photo.jpg \
    --town "Hoboken" --town-number 1 --preview
```

### Exact output path

```bash
python scripts/generate_cover_photo.py --photo path/to/photo.jpg \
    --town "Hoboken" --town-number 1 \
    --output-file ~/Desktop/hoboken_cover.png
```

## CLI Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--photo PATH` | Yes | Path to the base photo |
| `--town NAME` | Yes | Town name to display |
| `--town-number N` | Yes | Town visit number |
| `--output-dir PATH` | No | Output base directory (default: `assets/`) |
| `--output-file PATH` | No | Exact output file path (overrides default naming) |
| `--preview` | No | Open the resulting PNG in the default browser |
| `--font-size-town N` | No | Override town name font size (default: 80) |
| `--font-size-number N` | No | Override town number font size (default: 48) |
| `--font-size-hashtag N` | No | Override hashtag font size (default: 36) |
| `--font-family NAME` | No | Override font family (default: Montserrat-Bold) |
| `--stroke-width N` | No | Override text stroke width (default: 3) |

## Configuration

Settings are read from the `cover_photo` section of `config.json`:

| Key | Default | Description |
|-----|---------|-------------|
| `font_family` | `Montserrat-Bold` | Font family name (matches filename in `scripts/utils/fonts/`) |
| `font_size_town_name` | `80` | Town name font size in points |
| `font_size_town_number` | `48` | Town number font size in points |
| `font_size_hashtag` | `36` | Hashtag font size in points |
| `text_color` | `#FFFFFF` | Text fill color (white) |
| `stroke_color` | `#000000` | Text stroke/outline color (black) |
| `stroke_width` | `3` | Text stroke width in pixels |

CLI arguments override these config values.

## Output

```
assets/
├── 1-Hoboken/
│   └── cover_photo.png
├── 2-Jersey_City/
│   └── cover_photo.png
└── ...
```

- Folder names use the format `{town_number}-{town_name}`
- Spaces in town names are replaced with underscores
- Output is always 1080x1920 PNG (9:16 aspect ratio)

## Text Layout

The cover photo arranges text in three zones:

1. **Town name** — upper third, centered, bold, auto-shrinks for long names
2. **Town number** — just below the town name (e.g., "Town #42")
3. **Hashtag** — near the bottom eighth of the image

All text has a white fill with black stroke for readability over both light and dark photos.

## Smart Crop & Resize

Input photos of any aspect ratio are handled:

- The photo is scaled to **fill** the 1080x1920 frame (no letterboxing)
- If wider than 9:16, the sides are center-cropped
- If taller than 9:16, the top/bottom are center-cropped
- Uses LANCZOS resampling for quality

## Edge Cases

- **Long town names**: Names like "Upper Saddle River" or "Washington Township" are automatically scaled down (minimum 30pt) to fit within the image width with 40px margins on each side.
- **Small source photos**: The script will upscale small photos to fill the 1080x1920 frame. For best quality, use source photos at least 1080px wide.
- **Non-RGB photos**: RGBA, grayscale, and other color modes are converted to RGB automatically.
- **Font not found**: If the configured font isn't in `scripts/utils/fonts/`, a warning is printed and Pillow's default font is used.

## Fonts

Montserrat Bold and Regular are stored in `scripts/utils/fonts/`:

- `Montserrat-Bold.ttf` — used for all text overlays by default
- `Montserrat-Regular.ttf` — available via `--font-family Montserrat-Regular`

To add other fonts, place `.ttf` or `.otf` files in `scripts/utils/fonts/` and reference them by filename (without extension) via `--font-family` or `config.json`.
