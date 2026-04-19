#!/usr/bin/env python3
"""
Generate Google Earth-style fly-in videos for NJ municipalities.

Renders a 3D globe fly-in animation using Cesium.js in a headless browser
(Playwright), zooming from a world view down to the town's border. The red
border polygon fades in at the end of the animation. Outputs a 1080x1920
(9:16) MP4 video ready for Instagram Reels.

Usage:
    # Single town
    python scripts/generate_flyin.py --town "Hoboken" --town-number 1

    # Town with disambiguation
    python scripts/generate_flyin.py --town "Lawrence" --county Mercer

    # Custom duration (default 9 seconds)
    python scripts/generate_flyin.py --town "Hoboken" --duration 7

    # Without border overlay
    python scripts/generate_flyin.py --town "Hoboken" --no-border

    # All towns (batch mode)
    python scripts/generate_flyin.py --all

    # Preview in default player
    python scripts/generate_flyin.py --town "Hoboken" --preview
"""

import argparse
import csv
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils.nj_geodata import (
    load_shapefile,
    lookup_town,
    get_display_name,
    get_county_name,
    to_geojson,
    get_bounds_wgs84,
    get_centroid_wgs84,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = REPO_ROOT / "templates" / "flyin.html"


def load_config():
    """Load fly-in settings from config.json."""
    config_path = REPO_ROOT / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            cfg = json.load(f)
        return cfg.get("flyin", {})
    return {}


def _load_dotenv():
    """Load .env file from repo root if it exists."""
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value


def get_cesium_token(cfg):
    """Get Cesium Ion access token from environment or .env file."""
    _load_dotenv()
    env_var = cfg.get("cesium_ion_token_env", "CESIUM_ION_TOKEN")
    token = os.environ.get(env_var, "")
    if not token:
        print(
            f"ERROR: Cesium Ion access token not found.\n"
            f"  1. Sign up at https://ion.cesium.com/ (free)\n"
            f"  2. Create an access token at https://ion.cesium.com/tokens\n"
            f"  3. Add to .env file: {env_var}=your-token-here\n"
            f"     Or set: export {env_var}='your-token-here'\n",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


def get_output_path(town_name, town_number=None, output_dir=None, cfg=None):
    """Build the output file path for a town's fly-in video."""
    if output_dir:
        base = Path(output_dir)
    else:
        base = REPO_ROOT / "assets"

    if town_number:
        folder = f"{town_number}-{sanitize_filename(town_name)}"
    else:
        folder = sanitize_filename(town_name)

    filename = (cfg or {}).get("output_filename", "flyin.mp4")
    return base / folder / filename


def sanitize_filename(name):
    """Sanitize a town name for use as a filename/directory name."""
    clean = name.replace(" ", "_")
    clean = "".join(c for c in clean if c.isalnum() or c in ("_", "-"))
    return clean


def load_towns_csv():
    """Load the towns.csv master list for batch processing."""
    csv_path = REPO_ROOT / "data" / "towns.csv"
    if not csv_path.exists():
        return None

    towns = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            towns.append(row)
    return towns


def check_ffmpeg():
    """Verify ffmpeg is available."""
    if shutil.which("ffmpeg") is None:
        print(
            "ERROR: ffmpeg not found. Install with: brew install ffmpeg",
            file=sys.stderr,
        )
        sys.exit(1)


def build_flyin_config(town_row, cfg, token, duration=None, show_border=True):
    """Build the JavaScript config object to inject into the Cesium page."""
    centroid_lng, centroid_lat = get_centroid_wgs84(town_row)
    west, south, east, north = get_bounds_wgs84(town_row)

    geojson = to_geojson(town_row) if show_border else None

    dur = duration or cfg.get("duration_seconds", 9)

    return {
        "token": token,
        "centroidLng": centroid_lng,
        "centroidLat": centroid_lat,
        "boundsWest": west,
        "boundsSouth": south,
        "boundsEast": east,
        "boundsNorth": north,
        "geojson": geojson,
        "durationSeconds": dur,
        "phasesPct": cfg.get("phases_pct", {
            "globe_hold": [0, 11],
            "globe_to_state": [11, 44],
            "state_to_town": [44, 72],
            "border_fade_in": [72, 89],
            "final_hold": [89, 100],
        }),
        "cameraStartAltitude": cfg.get("camera_start_altitude_m", 20000000),
        "cameraEndAltitudeOffset": cfg.get("camera_end_altitude_offset_m", 5000),
        "cameraPitchDeg": cfg.get("camera_pitch_degrees", -30),
        "borderColor": cfg.get("border_color", "#FF0000"),
        "borderOpacity": cfg.get("border_opacity", 0.8),
        "showBorder": show_border,
    }


def render_flyin(flyin_config, output_path, cfg):
    """
    Render the fly-in animation using Playwright and Cesium.js.

    Launches a headless Chromium browser, loads the Cesium viewer template,
    injects the town configuration, records the animation, and re-encodes
    with ffmpeg.
    """
    from playwright.sync_api import sync_playwright

    duration_sec = flyin_config["durationSeconds"]
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Serve the template via HTTP to avoid file:// restrictions
    # that block Cesium tile requests in headless Chrome
    template_dir = str(TEMPLATE_PATH.parent)
    handler_cls = http.server.SimpleHTTPRequestHandler
    httpd = http.server.HTTPServer(
        ("127.0.0.1", 0),
        lambda *a, **k: handler_cls(*a, directory=template_dir, **k),
    )
    port = httpd.server_address[1]
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    try:
      with tempfile.TemporaryDirectory(prefix="ejc_flyin_") as tmpdir:
        tmpdir = Path(tmpdir)
        frames_dir = tmpdir / "frames"
        frames_dir.mkdir()

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=[
                    "--headless=new",
                    "--use-gl=angle",
                    "--enable-webgl",
                    "--ignore-gpu-blocklist",
                    "--enable-gpu-rasterization",
                ],
            )

            context = browser.new_context(
                viewport={"width": 1080, "height": 1920},
            )

            page = context.new_page()

            # Capture console messages for debugging
            console_messages = []
            page.on("console", lambda msg: console_messages.append(
                f"[{msg.type}] {msg.text}"
            ))

            # Navigate to the template via HTTP
            page.goto(
                f"http://127.0.0.1:{port}/flyin.html",
                wait_until="networkidle",
            )

            # Wait for the page to signal readiness
            page.wait_for_function("window._viewerReady === true", timeout=30000)

            # Inject the town-specific configuration
            page.evaluate(f"FLYIN_CONFIG = {json.dumps(flyin_config)}")

            # Initialize the viewer with the injected config
            page.evaluate("initViewer()")

            # Wait for initial globe tiles to load
            page.wait_for_timeout(5000)

            # Capture frames one at a time
            fps = 30
            total_frames = int(duration_sec * fps)
            print(f"  Capturing {total_frames} frames at {fps}fps...")

            for i in range(total_frames):
                elapsed_ms = (i / fps) * 1000
                # Position camera + wait for tiles at this frame
                page.evaluate(f"setAnimationTime({elapsed_ms})")
                # Capture the frame
                frame_path = frames_dir / f"frame_{i:05d}.png"
                page.screenshot(path=str(frame_path))

                # Progress every 3 seconds of video
                if (i + 1) % (fps * 3) == 0 or i == total_frames - 1:
                    pct = int((i + 1) / total_frames * 100)
                    print(f"    {pct}% ({i + 1}/{total_frames} frames)")

            # Print console errors if any
            errors = [m for m in console_messages if m.startswith("[error]")]
            if errors:
                print(f"  Browser errors ({len(errors)}):")
                for err in errors[:5]:
                    print(f"    {err[:200]}")

            page.close()
            context.close()
            browser.close()

        # Assemble frames into MP4 with ffmpeg
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-framerate", str(fps),
            "-i", str(frames_dir / "frame_%05d.png"),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-an",
            "-movflags", "+faststart",
            str(output_path),
        ]

        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  ffmpeg error: {result.stderr[:500]}", file=sys.stderr)
            raise RuntimeError("ffmpeg encoding failed")
    finally:
        httpd.shutdown()

    return output_path


def generate_single(town_name, county=None, output_dir=None, town_number=None,
                    preview=False, duration=None, no_border=False, config=None):
    """Generate fly-in video for a single town."""
    cfg = load_config()
    if config:
        cfg.update(config)

    token = get_cesium_token(cfg)
    check_ffmpeg()

    gdf = load_shapefile()
    town = lookup_town(town_name, county=county, gdf=gdf)

    display_name = get_display_name(town)
    town_county = get_county_name(town.get("COUNTYFP", ""))

    dur = duration or cfg.get("duration_seconds", 9)
    print(f"  Generating fly-in: {display_name} ({town_county} County) [{dur}s]")

    flyin_config = build_flyin_config(
        town, cfg, token,
        duration=duration,
        show_border=not no_border,
    )

    output_path = get_output_path(display_name, town_number, output_dir, cfg)

    render_flyin(flyin_config, output_path, cfg)

    print(f"  Saved: {output_path}")

    if preview:
        subprocess.run(["open", str(output_path)], check=False)

    return output_path


def generate_all(output_dir=None, duration=None, no_border=False, config=None):
    """Generate fly-in videos for all 564 towns."""
    cfg = load_config()
    if config:
        cfg.update(config)

    token = get_cesium_token(cfg)
    check_ffmpeg()

    gdf = load_shapefile()
    towns_csv = load_towns_csv()

    # Build a lookup from town name to town number
    town_numbers = {}
    if towns_csv:
        for row in towns_csv:
            key = row["town_name"].strip().lower()
            if row.get("town_number"):
                town_numbers[key] = row["town_number"]

    total = len(gdf)
    success = 0
    failed = 0

    for idx, (_, town_row) in enumerate(gdf.iterrows(), 1):
        display_name = get_display_name(town_row)
        town_county = get_county_name(town_row.get("COUNTYFP", ""))
        town_num = town_numbers.get(display_name.lower())

        print(f"[{idx}/{total}]", end=" ")

        try:
            flyin_config = build_flyin_config(
                town_row, cfg, token,
                duration=duration,
                show_border=not no_border,
            )

            output_path = get_output_path(display_name, town_num, output_dir, cfg)

            render_flyin(flyin_config, output_path, cfg)

            print(f"  {display_name} ({town_county}) -> {output_path}")
            success += 1
        except Exception as e:
            print(f"  FAILED: {display_name} ({town_county}): {e}")
            failed += 1

    print(f"\nDone! Generated: {success}, Failed: {failed}")
    return success, failed


def main():
    parser = argparse.ArgumentParser(
        description="Generate Google Earth-style fly-in videos for NJ municipalities"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--town", help="Town name to generate fly-in for")
    group.add_argument("--all", action="store_true", help="Generate for all 564 towns")

    parser.add_argument("--county", help="County name for disambiguation")
    parser.add_argument("--output-dir", help="Output directory (default: assets/)")
    parser.add_argument("--preview", action="store_true", help="Open result in player")
    parser.add_argument("--town-number", help="Town visit number (for folder naming)")
    parser.add_argument(
        "--duration", type=float,
        help="Animation duration in seconds (default: from config, 9s). "
             "All animation phases scale proportionally.",
    )
    parser.add_argument(
        "--no-border", action="store_true",
        help="Skip the red border overlay",
    )

    args = parser.parse_args()

    if args.all:
        generate_all(
            output_dir=args.output_dir,
            duration=args.duration,
            no_border=args.no_border,
        )
    else:
        generate_single(
            town_name=args.town,
            county=args.county,
            output_dir=args.output_dir,
            town_number=args.town_number,
            preview=args.preview,
            duration=args.duration,
            no_border=args.no_border,
        )


if __name__ == "__main__":
    main()
