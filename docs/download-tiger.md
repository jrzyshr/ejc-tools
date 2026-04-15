# download_tiger.py

Downloads US Census TIGER/Line shapefiles for NJ county subdivisions. This is a prerequisite for all map-based generation scripts (`generate_border.py`, etc.).

## Prerequisites

- Python packages: `requests`

## Usage

```bash
python scripts/download_tiger.py
```

No arguments are required. The script handles everything automatically.

## What It Does

1. Checks if the shapefile already exists at `data/tl_2025_34_cousub/` — skips download if found
2. Attempts to download from the Census Bureau, trying multiple years (2024, 2023) in case a URL isn't available yet
3. Displays a progress bar during download
4. Extracts the ZIP contents to `data/tl_2025_34_cousub/`
5. Renames files to use a consistent `tl_2025_34_cousub` prefix regardless of which year was downloaded

## Output

```
data/tl_2025_34_cousub/
├── tl_2025_34_cousub.cpg
├── tl_2025_34_cousub.dbf
├── tl_2025_34_cousub.prj
├── tl_2025_34_cousub.shp
├── tl_2025_34_cousub.shx
└── ... (metadata XML files)
```

The `data/tl_2025_34_cousub/` directory is gitignored. Each developer must run this script once after cloning.

## Edge Cases

- **Large download**: The ZIP file is roughly 50–100 MB. On a slow connection this may take a while; the progress bar shows download status.
- **Census Bureau unavailability**: If all TIGER URLs fail (e.g., the Census website is down), the script prints manual download instructions with direct links. Follow them to download and extract the file yourself.
- **No checksum verification**: The script does not verify file integrity after download. If a download is interrupted or corrupted, delete the `data/tl_2025_34_cousub/` directory and re-run the script.
- **Idempotent**: Running the script again after a successful download is safe — it detects the existing `.shp` file and exits early.
- **Timeout**: HTTP requests have a 120-second timeout. If this is too short for your connection, you may need to download manually.
