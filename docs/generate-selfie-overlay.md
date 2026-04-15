# generate_selfie_overlay.py

Generates 1080x1920 (9:16) selfie overlay cards with a title header, town name sticker, and #eatjerseychallenge hashtag. Used for Instagram story/reel selfie cards showing the restaurant visit.

## Prerequisites

- Python packages: `Pillow`
- Montserrat font files in `scripts/utils/fonts/` (included in the repo)

## Usage

### Basic usage

```bash
python scripts/generate_selfie_overlay.py --photo path/to/selfie.jpg \
    --town "Hoboken" --town-number 1 \
    --restaurant "Carlo's Bakery" --meal-type "Dessert"
```

### Custom output directory

```bash
python scripts/generate_selfie_overlay.py --photo path/to/selfie.jpg \
    --town "Hoboken" --town-number 1 \
    --restaurant "Carlo's Bakery" --meal-type "Lunch" \
    --output-dir assets/
```

### Preview in browser

```bash
python scripts/generate_selfie_overlay.py --photo path/to/selfie.jpg \
    --town "Hoboken" --town-number 1 \
    --restaurant "Carlo's Bakery" --meal-type "Lunch" --preview
```

### Exact output path

```bash
python scripts/generate_selfie_overlay.py --photo path/to/selfie.jpg \
    --town "Hoboken" --town-number 1 \
    --restaurant "Carlo's Bakery" --meal-type "Lunch" \
    --output-file ~/Desktop/hoboken_selfie.png
```

## CLI Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--photo PATH` | Yes | Path to the selfie photo |
| `--town NAME` | Yes | Town name |
| `--town-number N` | Yes | Town visit number |
| `--restaurant NAME` | Yes | Restaurant name |
| `--meal-type TYPE` | Yes | Meal type (e.g., Lunch, Dinner, Dessert) |
| `--output-dir PATH` | No | Output base directory (default: `assets/`) |
| `--output-file PATH` | No | Exact output file path (overrides default naming) |
| `--preview` | No | Open the resulting PNG in the default browser |
| `--font-size-title N` | No | Override title font size (default: 56) |
| `--font-size-hashtag N` | No | Override hashtag font size (default: 36) |
| `--font-family NAME` | No | Override font family (default: Montserrat-Bold) |
| `--stroke-width N` | No | Override text stroke width (default: 3) |

## Configuration

Settings are read from the `selfie_overlay` section of `config.json`:

| Key | Default | Description |
|-----|---------|-------------|
| `title_format` | `NJ Town #{town_number}: {meal_type} @ {restaurant}` | Title text template |
| `font_family` | `Montserrat-Bold` | Font family name |
| `font_size_title` | `56` | Title font size in points |
| `font_size_hashtag` | `36` | Hashtag font size in points |
| `text_color` | `#FFFFFF` | Text fill color (white) |
| `stroke_color` | `#000000` | Text stroke/outline color (black) |
| `stroke_width` | `3` | Text stroke width in pixels |

The `title_format` supports these placeholders: `{town_number}`, `{meal_type}`, `{restaurant}`.

CLI arguments override config values.

## Output

```
assets/
├── 1-Hoboken/
│   └── selfie_overlay.png
├── 2-Jersey_City/
│   └── selfie_overlay.png
└── ...
```

- Folder names use the format `{town_number}-{town_name}`
- Spaces in town names are replaced with underscores
- Output is always 1080x1920 PNG (9:16 aspect ratio)

## Layout

The selfie overlay has a distinct layout:

```
┌──────────────────────┐
│  NJ Town #1:         │ ← Title (auto-wraps)
│  Dessert @ Carlo's   │
│    ┌──────────┐      │
│    │ HOBOKEN  │      │ ← Town sticker (rounded rect)
│    └──────────┘      │
├──────────────────────┤ ← ~320px header boundary
│                      │
│                      │
│    [selfie photo]    │ ← Photo fills remaining space
│                      │
│                      │
│ #eatjerseychallenge  │ ← Hashtag near bottom
│                      │
└──────────────────────┘
```

- **Header area** (top 320px): black background with title and town sticker
- **Photo area**: selfie scaled to fill the remaining 1080x1600 space
- **Town sticker**: semi-transparent white rounded rectangle behind the town name, styled like an Instagram location sticker
- **Hashtag**: overlaid near the bottom of the photo

## Text Wrapping

Long titles (e.g., "NJ Town #42: Dinner @ The Original Holsten's Ice Cream") are handled:

1. Font is auto-shrunk from 56pt down to 28pt minimum
2. If still too wide, the title wraps at natural break points (`:`, `@`, `-`)
3. As a final fallback, word-wrap splits at spaces

## Edge Cases

- **Long restaurant names**: Titles with long restaurant names auto-shrink and wrap. The `@` symbol is a natural line-break point.
- **Long town names**: Town names are displayed in uppercase and auto-shrunk to fit within the image width.
- **Small source photos**: Upscaled to fill the photo area. Use source photos at least 1080px wide for best quality.
- **Non-RGB photos**: Converted to RGB automatically.
- **Font not found**: Falls back to Pillow's default font with a warning.
- **Title format customization**: The `title_format` in `config.json` can be changed to any template using the available placeholders.

## Fonts

See the [generate_cover_photo](generate-cover-photo.md) docs for font details. Both scripts share the same `scripts/utils/fonts/` directory.
