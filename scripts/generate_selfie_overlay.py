#!/usr/bin/env python3
"""
Generate selfie overlay cards with text for Instagram stories/reels.

Resizes a selfie photo to 1080x1920 (9:16), positions it below a text
header area, and adds title, town name, and #eatjerseychallenge overlays.

Usage:
    # Basic usage
    python scripts/generate_selfie_overlay.py --photo path/to/selfie.jpg \
        --town "Hoboken" --town-number 1 \
        --restaurant "Carlo's Bakery" --meal-type "Dessert"

    # Custom output
    python scripts/generate_selfie_overlay.py --photo path/to/selfie.jpg \
        --town "Hoboken" --town-number 1 \
        --restaurant "Carlo's Bakery" --meal-type "Lunch" \
        --output-dir assets/

    # Preview in browser
    python scripts/generate_selfie_overlay.py --photo path/to/selfie.jpg \
        --town "Hoboken" --town-number 1 \
        --restaurant "Carlo's Bakery" --meal-type "Lunch" --preview
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

# Header area height for text overlays above the photo
HEADER_HEIGHT = 320


def load_config():
    """Load selfie overlay settings from config.json."""
    config_path = REPO_ROOT / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            cfg = json.load(f)
        return cfg.get("selfie_overlay", {})
    return {}


def load_font(font_name, size):
    """Load a font from the fonts directory, falling back to default."""
    for ext in (".ttf", ".otf"):
        font_path = FONTS_DIR / f"{font_name}{ext}"
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size)

    font_path = Path(font_name)
    if font_path.exists():
        return ImageFont.truetype(str(font_path), size)

    print(f"  Warning: Font '{font_name}' not found, using default", file=sys.stderr)
    return ImageFont.load_default(size)


def fit_photo_below_header(img, target_w, target_h, header_h):
    """
    Resize and position photo to fill the area below the header.

    The photo is scaled to fill the available space below the header,
    center-cropped if necessary.
    """
    avail_w = target_w
    avail_h = target_h - header_h

    src_w, src_h = img.size
    src_aspect = src_w / src_h
    avail_aspect = avail_w / avail_h

    if src_aspect > avail_aspect:
        # Source wider: scale by height, crop width
        scale = avail_h / src_h
        new_w = round(src_w * scale)
        new_h = avail_h
        img = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - avail_w) // 2
        img = img.crop((left, 0, left + avail_w, avail_h))
    else:
        # Source taller: scale by width, crop height
        scale = avail_w / src_w
        new_w = avail_w
        new_h = round(src_h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        top = (new_h - avail_h) // 2
        img = img.crop((0, top, avail_w, top + avail_h))

    return img


def draw_text_with_stroke(draw, position, text, font, fill, stroke_color, stroke_width):
    """Draw text with a stroke/outline for readability."""
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


def auto_shrink_font(draw, text, font_name, start_size, max_width, min_size=24):
    """Shrink font size until text fits within max_width."""
    size = start_size
    font = load_font(font_name, size)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]

    while text_w > max_width and size > min_size:
        size -= 2
        font = load_font(font_name, size)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]

    return font, size


def generate_selfie_overlay(photo_path, town_name, town_number,
                            restaurant, meal_type, config=None):
    """
    Generate a 1080x1920 selfie overlay card.

    Parameters
    ----------
    photo_path : str or Path
        Path to the selfie photo.
    town_name : str
        Town name.
    town_number : int or str
        Town visit number.
    restaurant : str
        Restaurant name.
    meal_type : str
        Meal type (e.g., "Lunch", "Dinner", "Dessert").
    config : dict, optional
        Override settings from config.json.

    Returns
    -------
    Image
        The composited selfie overlay card.
    """
    cfg = load_config()
    if config:
        cfg.update(config)

    title_fmt = cfg.get("title_format", "NJ Town #{town_number}: {meal_type} @ {restaurant}")
    font_family = cfg.get("font_family", "Montserrat-Bold")
    font_size_title = cfg.get("font_size_title", 56)
    font_size_hashtag = cfg.get("font_size_hashtag", 36)
    text_color = cfg.get("text_color", "#FFFFFF")
    stroke_color = cfg.get("stroke_color", "#000000")
    stroke_width = cfg.get("stroke_width", 3)

    # Build the title text from template
    title_text = title_fmt.format(
        town_number=town_number,
        meal_type=meal_type,
        restaurant=restaurant,
    )

    # Create the output canvas
    canvas = Image.new("RGB", (TARGET_WIDTH, TARGET_HEIGHT), (0, 0, 0))

    # Load, resize, and paste the selfie photo below the header
    selfie = Image.open(photo_path).convert("RGB")
    selfie = fit_photo_below_header(selfie, TARGET_WIDTH, TARGET_HEIGHT, HEADER_HEIGHT)
    canvas.paste(selfie, (0, HEADER_HEIGHT))

    draw = ImageDraw.Draw(canvas)

    # Load fonts
    font_hashtag = load_font(font_family, font_size_hashtag)

    max_text_w = TARGET_WIDTH - 80  # 40px margin each side

    # --- Title: centered in header area ---
    # Auto-shrink if title is too long (long restaurant names)
    font_title, _ = auto_shrink_font(
        draw, title_text, font_family, font_size_title, max_text_w, min_size=28
    )
    title_h = get_text_height(draw, title_text, font_title)

    # If the title is still too wide even at min size, wrap to two lines
    bbox = draw.textbbox((0, 0), title_text, font=font_title)
    text_w = bbox[2] - bbox[0]

    if text_w > max_text_w:
        # Split title at a sensible break point (at ":" or "@")
        lines = _wrap_title(title_text, draw, font_title, max_text_w)
        line_y = 40
        for line in lines:
            line_h = get_text_height(draw, line, font_title)
            draw_text_with_stroke(
                draw, (TARGET_WIDTH // 2, line_y), line,
                font_title, text_color, stroke_color, stroke_width,
            )
            line_y += line_h + 8
        title_bottom = line_y
    else:
        title_y = 40
        draw_text_with_stroke(
            draw, (TARGET_WIDTH // 2, title_y), title_text,
            font_title, text_color, stroke_color, stroke_width,
        )
        title_bottom = title_y + title_h + 8

    # --- Town name: styled below title in header ---
    town_display = town_name.upper()
    font_town_size = min(font_size_title - 8, 48)
    font_town, _ = auto_shrink_font(
        draw, town_display, font_family, font_town_size, max_text_w, min_size=24
    )
    town_y = title_bottom + 10
    draw_text_with_stroke(
        draw, (TARGET_WIDTH // 2, town_y), town_display,
        font_town, text_color, stroke_color, stroke_width,
    )

    # --- Location pin icon (unicode) + town name as sticker-style element ---
    # Draw a subtle rounded-rect "sticker" behind the town name
    town_text_h = get_text_height(draw, town_display, font_town)
    bbox = draw.textbbox((TARGET_WIDTH // 2, town_y), town_display, font=font_town, anchor="mt")
    pad = 12
    sticker_rect = (bbox[0] - pad, bbox[1] - pad // 2, bbox[2] + pad, bbox[3] + pad // 2)
    # Draw semi-transparent white rectangle behind town name
    sticker = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sticker_draw = ImageDraw.Draw(sticker)
    sticker_draw.rounded_rectangle(sticker_rect, radius=10, fill=(255, 255, 255, 80))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), sticker).convert("RGB")

    # Redraw the town name on top of the sticker
    draw = ImageDraw.Draw(canvas)
    draw_text_with_stroke(
        draw, (TARGET_WIDTH // 2, town_y), town_display,
        font_town, text_color, stroke_color, stroke_width,
    )

    # --- Hashtag: near bottom ---
    hashtag = "#eatjerseychallenge"
    hashtag_y = TARGET_HEIGHT - TARGET_HEIGHT // 10
    draw_text_with_stroke(
        draw, (TARGET_WIDTH // 2, hashtag_y), hashtag,
        font_hashtag, text_color, stroke_color, stroke_width,
    )

    return canvas


def _wrap_title(text, draw, font, max_width):
    """Wrap title text into multiple lines that fit within max_width."""
    # Try splitting at known delimiters first
    for delim in (": ", " @ ", " - "):
        if delim in text:
            parts = text.split(delim, 1)
            lines = [parts[0] + delim.rstrip(), parts[1]]
            # Check if each line fits
            all_fit = all(
                draw.textbbox((0, 0), line, font=font)[2] - draw.textbbox((0, 0), line, font=font)[0] <= max_width
                for line in lines
            )
            if all_fit:
                return lines

    # Fallback: word-wrap
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def sanitize_filename(name):
    """Sanitize a town name for use as a filename/directory name."""
    clean = name.replace(" ", "_")
    clean = "".join(c for c in clean if c.isalnum() or c in ("_", "-"))
    return clean


def get_output_path(town_name, town_number=None, output_dir=None):
    """Build the output file path for a town's selfie overlay."""
    if output_dir:
        base = Path(output_dir)
    else:
        base = REPO_ROOT / "assets"

    if town_number:
        folder = f"{town_number}-{sanitize_filename(town_name)}"
    else:
        folder = sanitize_filename(town_name)

    return base / folder / "selfie_overlay.png"


def main():
    parser = argparse.ArgumentParser(
        description="Generate selfie overlay cards with text for Instagram"
    )
    parser.add_argument("--photo", required=True, help="Path to the selfie photo")
    parser.add_argument("--town", required=True, help="Town name")
    parser.add_argument("--town-number", required=True, help="Town visit number")
    parser.add_argument("--restaurant", required=True, help="Restaurant name")
    parser.add_argument("--meal-type", required=True,
                        help="Meal type (e.g., Lunch, Dinner, Dessert)")
    parser.add_argument("--output-dir", help="Output directory (default: assets/)")
    parser.add_argument("--output-file", help="Exact output file path (overrides default)")
    parser.add_argument("--preview", action="store_true", help="Open result in browser")
    parser.add_argument("--font-size-title", type=int, help="Override title font size")
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
    if args.font_size_title:
        config["font_size_title"] = args.font_size_title
    if args.font_size_hashtag:
        config["font_size_hashtag"] = args.font_size_hashtag
    if args.font_family:
        config["font_family"] = args.font_family
    if args.stroke_width:
        config["stroke_width"] = args.stroke_width

    print(f"Generating selfie overlay for {args.town} (Town #{args.town_number})")
    print(f"  {args.meal_type} @ {args.restaurant}")

    img = generate_selfie_overlay(
        photo_path=photo_path,
        town_name=args.town,
        town_number=args.town_number,
        restaurant=args.restaurant,
        meal_type=args.meal_type,
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
