# EatJerseyChallenge Tools

Automation tools for the **EatJerseyChallenge** — eating a meal in all 564 municipalities in New Jersey and producing a 60-90 second Instagram Reel for each town.

**Progress**: 286 towns visited · 42 videos published · 244 awaiting production

## Repo Structure

```
ejc-tools/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   └── new-town.yml          # Structured issue form for new town visits
│   └── workflows/                 # GitHub Actions (future)
├── scripts/
│   ├── seed_issues.py             # Bulk-create GitHub Issues from towns.csv
│   ├── generate_border.py         # Town border outline (transparent PNG)
│   ├── generate_labeled_map.py    # Labeled municipality map with neighbors
│   ├── generate_cover_photo.py    # 9:16 cover photo with text overlays
│   ├── generate_selfie_overlay.py # Selfie card with title/hashtag overlays
│   ├── fetch_wikipedia.py         # Batch-fetch Wikipedia articles
│   ├── extract_research.py        # LLM-powered research brief extraction
│   ├── index_clips.py             # Vision AI video clip cataloging
│   ├── draft_script.py            # LLM script drafting from research + index
│   ├── process_audio.py           # Voice cleanup: silence removal + normalization
│   ├── generate_captions.py       # Whisper-powered SRT caption generation
│   ├── generate_earth_kml.py      # KML files for Google Earth Studio fly-ins
│   └── utils/
│       ├── nj_geodata.py          # TIGER/Line shapefile helpers
│       └── fonts/                 # Montserrat, etc.
├── docs/                          # Tool documentation (linked from README)
├── data/
│   ├── towns.csv                  # Master list of 564 NJ municipalities
│   ├── tl_2025_34_cousub/         # TIGER/Line shapefiles (gitignored)
│   └── wikipedia_cache/           # Cached Wikipedia data (gitignored)
├── assets/                        # Generated assets per town (gitignored)
│   └── {number}-{town_name}/
├── config.json                    # Shared configuration
├── requirements.txt               # Python dependencies
└── README.md
```

## Quick Start

```bash
# Clone and set up
git clone https://github.com/YOUR_USER/ejc-tools.git
cd ejc-tools
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Download TIGER/Line shapefiles (one-time)
# Visit: https://www.census.gov/cgi-bin/geo/shapefiles/index.php
# Select Year: 2024, Layer: County Subdivisions, State: New Jersey
# Extract to data/tl_2025_34_cousub/

# Populate GitHub Issues from master CSV
python scripts/seed_issues.py --csv data/towns.csv --repo YOUR_USER/ejc-tools

# Generate border outlines for all towns
python scripts/generate_border.py --all

# Generate labeled maps for all towns
python scripts/generate_labeled_map.py --all
```

## Documentation

Detailed usage guides and edge cases for each tool:

| Tool | Description |
|------|-------------|
| [download_tiger.py](docs/download-tiger.md) | Download Census TIGER/Line shapefiles for NJ |
| [generate_towns_csv.py](docs/generate-towns-csv.md) | Generate the master `towns.csv` from Wikipedia |
| [generate_border.py](docs/generate-border.md) | Generate red town border outlines on transparent PNGs |
| [generate_labeled_map.py](docs/generate-labeled-map.md) | Generate labeled municipality maps with neighbors |
| [seed_issues.py](docs/seed-issues.md) | Bulk-create GitHub Issues from `towns.csv` |
| [fetch_wikipedia.py](docs/fetch-wikipedia.md) | Batch-fetch Wikipedia articles for all NJ municipalities |
| [extract_research.py](docs/extract-research.md) | LLM-powered research brief extraction from Wikipedia |
| [check_thin_articles.py](docs/check-thin-articles.md) | Flag thin/missing Wikipedia articles for manual research |
| [nj_geodata.py](docs/nj-geodata.md) | Shared geographic data utility library |

> Documentation for future tools will be added to the [`docs/`](docs/) folder and linked here.

## Pipeline Stages (GitHub Project Board)

Each town issue moves through these stages:

| Stage | Description |
|-------|-------------|
| **Raw Footage** | Photos/videos gathered on NAS, not yet indexed |
| **Indexed** | Clips cataloged with descriptions |
| **Researched** | Wikipedia + town history reviewed, research brief generated |
| **Scripted** | Script drafted, reviewed, and finalized |
| **VO Recorded** | Voiceover recorded, cleaned, and under 90 seconds |
| **Edited** | Video edited in DaVinci Resolve, captions applied |
| **Published** | Reel published to Instagram + cross-posted |

## Automation Sections

### Section 1: GitHub Projects Pipeline
Replace OneNote tracking with GitHub Issues + Projects board. Each town is an issue with structured fields, checklist, and stage labels.

### Section 2: Town Border Outlines
Auto-generate red border outlines on transparent background from TIGER/Line shapefiles. Replaces manual Paint.NET tracing.

### Section 3: Labeled Municipality Maps
Generate maps showing target town (highlighted) with labeled neighbors. Replaces manual Paint.NET map creation.

### Section 4: Wikipedia Research + LLM Extraction
Batch-fetch Wikipedia articles, extract interesting facts via LLM, flag thin articles for manual research.

### Section 5: Cover Photo & Selfie Overlays
Pillow-based text overlay generation for Instagram cover photos and selfie cards.

### Section 6: Voice Recording Cleanup
Auto-editor silence removal + ffmpeg loudness normalization. Replaces manual pause trimming in GarageBand.

### Section 7: Whisper Auto-Captioning
Generate timed SRT captions from voiceover audio. Replaces the most tedious manual step (phrase-by-phrase captioning).

### Section 8: DaVinci Resolve Template + Scripting
Standardized 9:16 project template with Ken Burns presets. Python scripting API for automated project setup and asset import.

### Section 9: Video Clip Indexing (Vision AI)
Auto-describe video clips using vision LLMs. Replaces manual clip-by-clip cataloging.

### Section 10: Script Drafting Pipeline
LLM-powered first-draft script from research brief + clip index + menu items.

### Section 11: Google Earth Studio Fly-ins
Generate KML files from TIGER data for repeatable map fly-in animations.

## External Tool Dependencies

| Tool | Purpose | Platform | Install |
|------|---------|----------|---------|
| [DaVinci Resolve Free](https://www.blackmagicdesign.com/products/davinciresolve) | Video editing | Mac | Download |
| [auto-editor](https://auto-editor.com/) | Silence removal | Mac | `pip install auto-editor` |
| [whisper.cpp](https://github.com/ggerganov/whisper.cpp) | Speech-to-text | Mac | `brew install whisper-cpp` |
| [ffmpeg](https://ffmpeg.org/) | Audio processing | Mac | `brew install ffmpeg` |
| [Google Earth Studio](https://earth.google.com/studio/) | Map fly-in videos | Web | Free (Chrome) |
| [gh CLI](https://cli.github.com/) | GitHub API access | Mac | `brew install gh` |

## License

See [LICENSE](LICENSE).
