#!/usr/bin/env python3
"""
Generate Instagram Reel cover photos with text overlays.

Resizes/crops a base photo to 1080x1920 (9:16) and adds town name,
town number, and #eatjerseychallenge text overlays. Replaces the
Instagram story editor round-trip for cover photo creation.

Usage:
    # Basic usage
    python scripts/generate_cover_photo.py --photo path/to/photo.jpg \
        --town "Hoboken" --town-number 1

    # Custom output directory
    python scripts/generate_cover_photo.py --photo path/to/photo.jpg \
        --town "Hoboken" --town-number 1 --output-dir assets/

    # Override font sizes
    python scripts/generate_cover_photo.py --photo path/to/photo.jpg \
        --town "Hoboken" --town-number 1 \
        --font-size-town 80 --font-size-number 48

    # Preview in browser
    python scripts/generate_cover_photo.py --photo path/to/photo.jpg \
        --town "Hoboken" --town-number 1 --preview
"""

import argparse
import json
import sys
import webbrowser
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
FONTS_DIR = Path(__file__).resolve().parent / "utils" / "fonts"

# Target dimensions: 9:16 Instagram Reel cover
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920


def load_config():
    """Load cover photo settings from config.json."""
    config_path = REPO_ROOT / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            cfg = json.load(f)
        return cfg.get("cover_photo", {})
    return {}


def load_font(font_name, size):
    """Load a font from the fonts directory, falling back to default."""
    # Try exact filename first (e.g., "Montserrat-Bold")
    for ext in (".ttf", ".otf"):
        font_path = FONTS_DIR / f"{font_name}{ext}"
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size)

    # Try as-is (might be a full path)
    font_path = Path(font_name)
    if font_path.exists():
        return ImageFont.truetype(str(font_path), size)

    print(f"  Warning: Font '{font_name}' not found, using default", file=sys.stderr)
    return ImageFont.load_default(size)


def smart_crop_resize(img, target_w, target_h):
    """
    Resize and crop an image to target dimensions with smart centering.

    Strategy: scale to fill the target, then center-crop.
    """
    src_w, src_h = img.size
    src_aspect = src_w / src_h
    target_aspect = target_w / target_h

    if src_aspect > target_aspect:
        # Source is wider: scale by height, crop width
        scale = target_h / src_h
        new_w = round(src_w * scale)
        new_h = target_h
        img = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        img = img.crop((left, 0, left + target_w, target_h))
    else:
        # Source is taller: scale by width, crop height
        scale = target_w / src_w
        new_w = target_w
        new_h = round(src_h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        top = (new_h - target_h) // 2
        img = img.crop((0, top, target_w, top + target_h))

    return img


def draw_text_with_stroke(draw, position, text, font, fill, stroke_color, stroke_width):
    """Draw text with a stroke/outline for readability over any background."""
    x, y = position
    draw.text(
        (x, y), text, font=font, fill=fill,
        stroke_width=stroke_width, stroke_fill=stroke_color,
        anchor="mt",  # middle-top anchor for centered text
    )


def get_text_height(draw, text, font):
    """Get the height of rendered text."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def generate_cover_photo(photo_path, town_name, town_number, config=None):
    """
    Generate a 1080x1920 cover photo with text overlays.

    Parameters
    ----------
    photo_path : str or Path
        Path to the base photo.
    town_name : str
        Town name to display.
    town_number : int or str
        Town visit number.
    config : dict, optional
        Override settings from config.json.

    Returns
    -------
    Image
        The composited cover photo.
    """
    cfg = load_config()
    if config:
        cfg.update(config)

    font_family = cfg.get("font_family", "Montserrat-Bold")
    font_size_town = cfg.get("font_size_town_name", 80)
    font_size_number = cfg.get("font_size_town_number", 48)
    font_size_hashtag = cfg.get("font_size_hashtag", 36)
    text_color = cfg.get("text_color", "#FFFFFF")
    stroke_color = cfg.get("stroke_color", "#000000")
    stroke_width = cfg.get("stroke_width", 3)

    # Load and crop base photo
    img = Image.open(photo_path).convert("RGB")
    img = smart_crop_resize(img, TARGET_WIDTH, TARGET_HEIGHT)

    draw = ImageDraw.Draw(img)

    # Load fonts
    font_town = load_font(font_family, font_size_town)
    font_number = load_font(font_family, font_size_number)
    font_hashtag = load_font(font_family, font_size_hashtag)

    # --- Town name: centered in upper third ---
    town_display = town_name.upper()
    town_text_h = get_text_height(draw, town_display, font_town)
    town_y = TARGET_HEIGHT // 6  # Upper third center point

    # Auto-shrink if text is wider than the image (long names like "Upper Saddle River")
    effective_font_town = font_town
    effective_size = font_size_town
    bbox = draw.textbbox((0, 0), town_display, font=effective_font_town)
    text_w = bbox[2] - bbox[0]
    max_text_w = TARGET_WIDTH - 80  # 40px margin on each side

    while text_w > max_text_w and effective_size > 30:
        effective_size -= 2
        effective_font_town = load_font(font_family, effective_size)
        bbox = draw.textbbox((0, 0), town_display, font=effective_font_town)
        text_w = bbox[2] - bbox[0]

    town_text_h = get_text_height(draw, town_display, effective_font_town)

    draw_text_with_stroke(
        draw, (TARGET_WIDTH // 2, town_y), town_display,
        effective_font_town, text_color, stroke_color, stroke_width,
    )

    # --- Town number: below town name ---
    number_text = f"Town #{town_number}"
    number_y = town_y + town_text_h + 20
    draw_text_with_stroke(
        draw, (TARGET_WIDTH // 2, number_y), number_text,
        font_number, text_color, stroke_color, stroke_width,
    )

    # --- Hashtag: near bottom ---
    hashtag = "#eatjerseychallenge"
    hashtag_y = TARGET_HEIGHT - TARGET_HEIGHT // 8
    draw_text_with_stroke(
        draw, (TARGET_WIDTH // 2, hashtag_y), hashtag,
        font_hashtag, text_color, stroke_color, stroke_width,
    )

    return img


def sanitize_filename(name):
    """Sanitize a town name for use as a filename/directory name."""
    clean = name.replace(" ", "_")
    clean = "".join(c for c in clean if c.isalnum() or c in ("_", "-"))
    return clean


def get_output_path(town_name, town_number=None, output_dir=None):
    """Build the output file path for a town's cover photo."""
    if output_dir:
        base = Path(output_dir)
    else:
        base = REPO_ROOT / "assets"

    if town_number:
        folder = f"{town_number}-{sanitize_filename(town_name)}"
    else:
        folder = sanitize_filename(town_name)

    return base / folder / "cover_photo.png"


def main():
    parser = argparse.ArgumentParser(
        description="Generate Instagram Reel cover photos with text overlays"
    )
    parser.add_argument("--photo", required=True, help="Path to the base photo")
    parser.add_argument("--town", required=True, help="Town name")
    parser.add_argument("--town-number", required=True, help="Town visit number")
    parser.add_argument("--output-dir", help="Output directory (default: assets/)")
    parser.add_argument("--output-file", help="Exact output file path (overrides default)")
    parser.add_argument("--preview", action="store_true", help="Open result in browser")
    parser.add_argument("--font-size-town", type=int, help="Override town name font size")
    parser.add_argument("--font-size-number", type=int, help="Override town number font size")
    parser.add_argument("--font-size-hashtag", type=int, help="Override hashtag font size")
    parser.add_argument("--font-family", help="Override font family name")
    parser.add_argument("--stroke-width", type=int, help="Override text stroke width")

    args = parser.parse_args()

    photo_path = Path(args.photo)
    if not photo_path.exists():
        print(f"Error: Photo not found: {photo_path}", file=sys.stderr)
        sys.exit(1)

    # Build config overrides from CLI args
    config = {}
    if args.font_size_town:
        config["font_size_town_name"] = args.font_size_town
    if args.font_size_number:
        config["font_size_town_number"] = args.font_size_number
    if args.font_size_hashtag:
        config["font_size_hashtag"] = args.font_size_hashtag
    if args.font_family:
        config["font_family"] = args.font_family
    if args.stroke_width:
        config["stroke_width"] = args.stroke_width

    print(f"Generating cover photo for {args.town} (Town #{args.town_number})")

    img = generate_cover_photo(
        photo_path=photo_path,
        town_name=args.town,
        town_number=args.town_number,
        config=config or None,
    )

    if args.output_file:
        output_path = Path(args.output_file)
    else:
        output_path = get_output_path(args.town, args.town_number, args.output_dir)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    print(f"  Saved: {output_path}")

    if args.preview:
        webbrowser.open(f"file://{output_path.resolve()}")


if __name__ == "__main__":
    main()
