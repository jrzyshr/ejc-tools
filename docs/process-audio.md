# process_audio.py — Voice Recording Cleanup

Automates silence removal, loudness normalization, and noise reduction for
GarageBand voice recordings. Replaces the manual pause-trimming workflow
(~15 min saved per video).

## Prerequisites

**External tools** (not Python packages):

```bash
brew install ffmpeg        # Audio processing + loudness normalization
pip install auto-editor    # Silence removal
```

Verify both are available:

```bash
which ffmpeg auto-editor
```

## Quick Start

```bash
# Full pipeline — silence removal → loudnorm → noise reduction
python scripts/process_audio.py recording.wav

# Custom output path
python scripts/process_audio.py recording.wav --output final_vo.wav

# Skip noise reduction (cleaner source recordings)
python scripts/process_audio.py recording.wav --no-denoise

# Preview durations without writing files
python scripts/process_audio.py recording.wav --dry-run

# Also export DaVinci Resolve FCPXML timeline
python scripts/process_audio.py recording.wav --resolve
```

## Pipeline Stages

### Stage 1 — Silence Removal (auto-editor)

Removes pauses and breaths, producing tight radio-style audio.

```
auto-editor recording.wav --edit audio:threshold=-19dB --margin 0.05sec --output cleaned.wav
```

- `--threshold` controls what counts as silence (default `-19dB` from config)
- `--margin` keeps tiny natural gaps so speech doesn't sound robotic (default `0.05s`)
- Tune threshold to your mic's noise floor — test with a few recordings

### Stage 2 — Loudness Normalization (ffmpeg)

EBU R128 loudness normalization for consistent volume across all videos.

```
ffmpeg -i cleaned.wav -af loudnorm=I=-16:TP=-1.5:LRA=11 normalized.wav
```

- `I=-16` integrated loudness (LUFS)
- `TP=-1.5` true peak ceiling (dBTP)
- `LRA=11` loudness range

### Stage 3 — Noise Reduction (ffmpeg, optional)

Light FFT-based denoising to clean up background hum/hiss.

```
ffmpeg -i normalized.wav -af afftdn=nr=10:nf=-40 final_vo.wav
```

Skip with `--no-denoise` if the source recording is already clean.

## Options

| Flag | Description |
|------|-------------|
| `--output`, `-o` | Output file path (default: `<input>_processed.wav`) |
| `--threshold`, `-t` | Silence threshold (e.g. `-24dB` for noisier rooms) |
| `--margin`, `-m` | Margin in seconds around speech (default: `0.05`) |
| `--no-denoise` | Skip the noise reduction step |
| `--resolve` | Export a DaVinci Resolve FCPXML timeline alongside the audio |
| `--dry-run` | Print duration and word count without processing |

## Configuration

All defaults are read from the `voice` section of `config.json`:

```json
"voice": {
    "speaking_pace_wpm": 150,
    "silence_threshold_db": -19,
    "silence_margin_sec": 0.05,
    "loudnorm_integrated": -16,
    "loudnorm_true_peak": -1.5,
    "loudnorm_lra": 11
}
```

The `video.max_duration_seconds` value (default `90`) is used to flag
recordings that are too long.

## Output Summary

After processing, the script prints a summary:

```
══════════════════════════════════════════════════════════════
  Output:     /path/to/recording_processed.wav
  Original:   2:45  (165.3s)
  Final:      1:22  (82.1s)
  Trimmed:    83.2s removed
  Est. words: ~205 (at 150 WPM)
══════════════════════════════════════════════════════════════
```

- **Est. words** is calculated from final duration at the configured speaking pace
- A warning appears if the final duration exceeds `max_duration_seconds`

## Tuning Tips

- **Threshold too aggressive** (clipping words): raise toward `-24dB` or `-30dB`
- **Threshold too loose** (pauses remain): lower toward `-15dB`
- **Margin**: `0.05s` is a good starting point; try `0.1s` if edits sound choppy
- **Noise reduction**: the defaults (`nr=10`, `nf=-40`) are conservative; increase
  `nr` for noisier environments, but higher values can introduce artifacts

## Verification

1. Process 3 GarageBand recordings of different lengths
2. Compare auto-editor output to your manual trim
3. Confirm no words are clipped and pauses feel natural
4. Check loudness is consistent across outputs (`ffmpeg -i file.wav -af loudnorm=print_format=summary -f null -`)
5. Test the DaVinci Resolve XML export imports correctly (`--resolve` flag)
