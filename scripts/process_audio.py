#!/usr/bin/env python3
"""
Voice recording cleanup: silence removal, loudness normalization, and
optional noise reduction.

Wraps auto-editor (silence removal) and ffmpeg (loudnorm / noise reduction)
into a single command so a raw GarageBand WAV becomes broadcast-ready audio.

Prerequisites (installed outside pip):
    brew install ffmpeg
    pip install auto-editor

Usage:
    # Basic — full pipeline, output next to input
    python scripts/process_audio.py recording.wav

    # Custom output path
    python scripts/process_audio.py recording.wav --output final_vo.wav

    # Skip noise reduction
    python scripts/process_audio.py recording.wav --no-denoise

    # Export DaVinci Resolve XML timeline (silence removal only)
    python scripts/process_audio.py recording.wav --resolve

    # Override silence threshold (louder environment)
    python scripts/process_audio.py recording.wav --threshold -24dB

    # Preview: print durations without writing files
    python scripts/process_audio.py recording.wav --dry-run
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


# ── config ──────────────────────────────────────────────────────────────────

def load_config():
    """Load voice settings from config.json."""
    config_path = REPO_ROOT / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            cfg = json.load(f)
        return cfg.get("voice", {}), cfg.get("video", {})
    return {}, {}


# ── helpers ─────────────────────────────────────────────────────────────────

def require_tool(name):
    """Abort if an external CLI tool is not on PATH."""
    if shutil.which(name) is None:
        print(f"Error: '{name}' not found on PATH. Install it first.", file=sys.stderr)
        if name == "ffmpeg":
            print("  brew install ffmpeg", file=sys.stderr)
        elif name == "auto-editor":
            print("  pip install auto-editor", file=sys.stderr)
        sys.exit(1)


def get_duration_seconds(audio_path):
    """Return duration in seconds via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Warning: ffprobe failed on {audio_path}", file=sys.stderr)
        return 0.0
    return float(result.stdout.strip())


def fmt_duration(seconds):
    """Format seconds as M:SS."""
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def run(cmd, label):
    """Run a subprocess, print the command, and abort on failure."""
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    print(f"{'─' * 60}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"Error: {label} failed (exit {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)


# ── pipeline stages ─────────────────────────────────────────────────────────

def silence_removal(input_path, output_path, threshold, margin):
    """Step 6a — remove silence with auto-editor."""
    cmd = [
        "auto-editor", str(input_path),
        "--edit", f"audio:threshold={threshold}",
        "--margin", f"{margin}sec",
        "--output", str(output_path),
    ]
    run(cmd, "Step 1/3 · Silence removal (auto-editor)")


def resolve_export(input_path, output_path, threshold, margin):
    """Export a DaVinci Resolve XML timeline for the silence edit."""
    cmd = [
        "auto-editor", str(input_path),
        "--edit", f"audio:threshold={threshold}",
        "--margin", f"{margin}sec",
        "--export", "resolve",
        "--output", str(output_path),
    ]
    run(cmd, "DaVinci Resolve XML export")


def loudness_normalization(input_path, output_path, integrated, true_peak, lra):
    """Step 6b — EBU R128 loudness normalization via ffmpeg."""
    af = f"loudnorm=I={integrated}:TP={true_peak}:LRA={lra}"
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", af,
        str(output_path),
    ]
    run(cmd, "Step 2/3 · Loudness normalization (ffmpeg loudnorm)")


def noise_reduction(input_path, output_path, nr=10, nf=-40):
    """Step 6c — light FFT-based noise reduction via ffmpeg."""
    af = f"afftdn=nr={nr}:nf={nf}"
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", af,
        str(output_path),
    ]
    run(cmd, "Step 3/3 · Noise reduction (ffmpeg afftdn)")


# ── main ────────────────────────────────────────────────────────────────────

def process_audio(input_path, output_path=None, threshold=None, margin=None,
                  denoise=True, resolve=False, dry_run=False):
    """Run the full audio cleanup pipeline and print a summary."""
    voice_cfg, video_cfg = load_config()

    # Defaults from config.json → voice section
    threshold = threshold or f"{voice_cfg.get('silence_threshold_db', -19)}dB"
    margin = margin if margin is not None else voice_cfg.get("silence_margin_sec", 0.05)
    integrated = voice_cfg.get("loudnorm_integrated", -16)
    true_peak = voice_cfg.get("loudnorm_true_peak", -1.5)
    lra = voice_cfg.get("loudnorm_lra", 11)
    pace_wpm = voice_cfg.get("speaking_pace_wpm", 150)
    max_duration = video_cfg.get("max_duration_seconds", 90)

    input_path = Path(input_path).resolve()
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Default output: <input_stem>_processed.wav next to input
    if output_path is None:
        output_path = input_path.with_name(f"{input_path.stem}_processed.wav")
    else:
        output_path = Path(output_path).resolve()

    # ── Pre-flight info ─────────────────────────────────────────────
    original_dur = get_duration_seconds(input_path)
    print(f"\nInput:      {input_path.name}")
    print(f"Duration:   {fmt_duration(original_dur)}  ({original_dur:.1f}s)")

    if dry_run:
        est_words = int(original_dur / 60 * pace_wpm)
        print(f"Est. words: ~{est_words} (at {pace_wpm} WPM)")
        if original_dur > max_duration:
            print(f"⚠  Recording exceeds {max_duration}s — script may need trimming")
        print("\n(dry-run: no files written)")
        return

    # ── Pipeline ────────────────────────────────────────────────────
    tmpdir = Path(tempfile.mkdtemp(prefix="ejc_audio_"))

    try:
        # Stage 1: silence removal
        cleaned = tmpdir / "cleaned.wav"
        silence_removal(input_path, cleaned, threshold, margin)

        # Stage 2: loudness normalization
        normalized = tmpdir / "normalized.wav"
        loudness_normalization(cleaned, normalized, integrated, true_peak, lra)

        # Stage 3: optional noise reduction
        if denoise:
            final_tmp = tmpdir / "denoised.wav"
            noise_reduction(normalized, final_tmp)
        else:
            final_tmp = normalized

        # Move result to output path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(final_tmp, output_path)

        # Optional DaVinci Resolve XML
        if resolve:
            xml_path = output_path.with_suffix(".fcpxml")
            resolve_export(input_path, xml_path, threshold, margin)
            print(f"\nResolve:    {xml_path}")

    finally:
        # Clean up temp directory
        shutil.rmtree(tmpdir, ignore_errors=True)

    # ── Summary ─────────────────────────────────────────────────────
    final_dur = get_duration_seconds(output_path)
    saved = original_dur - final_dur
    est_words = int(final_dur / 60 * pace_wpm)

    print(f"\n{'═' * 60}")
    print(f"  Output:     {output_path}")
    print(f"  Original:   {fmt_duration(original_dur)}  ({original_dur:.1f}s)")
    print(f"  Final:      {fmt_duration(final_dur)}  ({final_dur:.1f}s)")
    print(f"  Trimmed:    {saved:.1f}s removed")
    print(f"  Est. words: ~{est_words} (at {pace_wpm} WPM)")
    if final_dur > max_duration:
        print(f"  ⚠  Exceeds {max_duration}s — script needs trimming")
    print(f"{'═' * 60}")


def main():
    parser = argparse.ArgumentParser(
        description="Voice recording cleanup: silence removal → loudness normalization → noise reduction",
    )
    parser.add_argument(
        "input", type=str,
        help="Path to the input audio file (WAV, M4A, etc.)",
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Output file path (default: <input>_processed.wav)",
    )
    parser.add_argument(
        "--threshold", "-t", type=str, default=None,
        help="Silence detection threshold (default: from config, e.g. -19dB)",
    )
    parser.add_argument(
        "--margin", "-m", type=float, default=None,
        help="Margin in seconds kept around speech (default: from config, e.g. 0.05)",
    )
    parser.add_argument(
        "--no-denoise", action="store_true",
        help="Skip the noise reduction step",
    )
    parser.add_argument(
        "--resolve", action="store_true",
        help="Also export a DaVinci Resolve FCPXML timeline",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print duration/word-count info without processing",
    )
    args = parser.parse_args()

    # Pre-flight: check external tools are installed
    if not args.dry_run:
        require_tool("auto-editor")
        require_tool("ffmpeg")
    require_tool("ffprobe")

    process_audio(
        input_path=args.input,
        output_path=args.output,
        threshold=args.threshold,
        margin=args.margin,
        denoise=not args.no_denoise,
        resolve=args.resolve,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
