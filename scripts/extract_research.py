#!/usr/bin/env python3
"""
Extract structured research briefs from cached Wikipedia articles using an LLM.

Reads cached Wikipedia data (from fetch_wikipedia.py) for a town and sends the
article text to an LLM with a structured prompt. Supports local LLM via
llama.cpp (Apple Silicon Metal) or cloud APIs (OpenAI, Anthropic).

Outputs research briefs as Markdown files to data/research/{town_name}.md.
Optionally posts the brief as a comment on the town's GitHub Issue.

Usage:
    # Single town (uses default LLM backend from config.json)
    python scripts/extract_research.py --town "Hoboken"

    # Town with disambiguation
    python scripts/extract_research.py --town "Lawrence" --county Mercer

    # All cached towns
    python scripts/extract_research.py --all

    # Specify LLM backend
    python scripts/extract_research.py --town "Hoboken" --backend openai
    python scripts/extract_research.py --town "Hoboken" --backend anthropic
    python scripts/extract_research.py --town "Hoboken" --backend llamacpp

    # Specify model
    python scripts/extract_research.py --town "Hoboken" --backend openai --model gpt-4o

    # Post research brief as GitHub Issue comment
    python scripts/extract_research.py --town "Hoboken" --post-comment

    # Override output directory
    python scripts/extract_research.py --town "Hoboken" --output-dir data/research

    # Force re-extraction (overwrite existing briefs)
    python scripts/extract_research.py --all --force

    # Dry run — show what would be processed
    python scripts/extract_research.py --all --dry-run
"""

import argparse
import csv
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "data" / "wikipedia_cache"
RESEARCH_DIR = REPO_ROOT / "data" / "research"
TOWNS_CSV = REPO_ROOT / "data" / "towns.csv"
CONFIG_PATH = REPO_ROOT / "config.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Maximum article text to send to the LLM (characters).
# Longer articles get truncated to stay within context windows.
MAX_ARTICLE_LENGTH = 30000

RESEARCH_PROMPT_TEMPLATE = """\
You are a research assistant for a video production project about New Jersey \
municipalities. Extract interesting facts from this Wikipedia article about \
{town_name}, {county} County, New Jersey.

Produce a structured research brief with these sections:

1. **Founding & Name Origin** — When was it founded/incorporated? Where does \
the name come from?
2. **Most Interesting Historical Facts** — 3-5 unusual, surprising, or \
notable historical facts. Prioritize things that would surprise a general \
audience.
3. **Pop Culture & Notable People** — Any movies, TV shows, music, or \
celebrities connected to this town? Major events?
4. **Notable Landmarks & Places** — Parks, buildings, historic sites, or \
unique local spots worth mentioning.
5. **Surprising Statistics** — Population quirks, geographic oddities, record-\
setting facts, or anything numerically interesting.

Rank facts by how likely they are to surprise or engage a general audience \
watching a 60-90 second Instagram Reel.

Format the output as a clean Markdown research card. Be concise — aim for \
300-500 words total. Cite specific years and names where possible.

If the article is sparse, note what's missing and suggest what to research \
manually.

---

WIKIPEDIA ARTICLE TEXT:

{article_text}
"""


def load_config():
    """Load research/LLM settings from config.json."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        return cfg.get("research", {})
    return {}


def sanitize_filename(name):
    """Sanitize a string for use as a filename."""
    clean = name.replace(" ", "_")
    clean = "".join(c for c in clean if c.isalnum() or c in ("_", "-"))
    return clean


def load_cached_article(town_name, county):
    """Load a cached Wikipedia article for a town."""
    cache_key = sanitize_filename(f"{town_name}_{county}")
    cache_path = CACHE_DIR / f"{cache_key}.json"

    if not cache_path.exists():
        return None

    with open(cache_path, encoding="utf-8") as f:
        return json.load(f)


def load_towns_csv():
    """Load the master towns.csv."""
    if not TOWNS_CSV.exists():
        return []
    towns = []
    with open(TOWNS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            towns.append(row)
    return towns


def prepare_article_text(article):
    """Prepare article text for the LLM prompt, with truncation if needed."""
    text = article.get("extract", "")
    if not text:
        # Fall back to summary
        text = article.get("summary", "")

    # Add infobox data if available
    infobox = article.get("infobox", {})
    if infobox:
        infobox_lines = ["INFOBOX DATA:"]
        for k, v in infobox.items():
            infobox_lines.append(f"  {k}: {v}")
        text = "\n".join(infobox_lines) + "\n\n" + text

    # Truncate if too long
    if len(text) > MAX_ARTICLE_LENGTH:
        text = text[:MAX_ARTICLE_LENGTH] + "\n\n[Article truncated for length]"

    return text


def build_prompt(town_name, county, article_text):
    """Build the research extraction prompt."""
    return RESEARCH_PROMPT_TEMPLATE.format(
        town_name=town_name,
        county=county,
        article_text=article_text,
    )


# ---------------------------------------------------------------------------
# LLM backend implementations
# ---------------------------------------------------------------------------

def call_openai(prompt, model, api_key=None):
    """Call OpenAI API for research extraction."""
    try:
        import openai
    except ImportError:
        log.error("openai package not installed. Run: pip install openai")
        sys.exit(1)

    client = openai.OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=model or "gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are a concise research assistant specializing in New Jersey history and culture.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=2000,
    )
    return response.choices[0].message.content


def call_anthropic(prompt, model, api_key=None):
    """Call Anthropic API for research extraction."""
    try:
        import anthropic
    except ImportError:
        log.error("anthropic package not installed. Run: pip install anthropic")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=model or "claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
        system="You are a concise research assistant specializing in New Jersey history and culture.",
        temperature=0.3,
    )
    return response.content[0].text


def call_llamacpp(prompt, model_path=None, server_url=None):
    """
    Call a local llama.cpp server for research extraction.

    Expects a llama.cpp server running (e.g., `llama-server -m model.gguf`).
    Default server URL: http://localhost:8080/v1/chat/completions
    """
    import requests

    url = server_url or "http://localhost:8080/v1/chat/completions"
    payload = {
        "messages": [
            {
                "role": "system",
                "content": "You are a concise research assistant specializing in New Jersey history and culture.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
    }

    if model_path:
        payload["model"] = model_path

    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except requests.ConnectionError:
        log.error(
            "Cannot connect to llama.cpp server at %s. "
            "Start it with: llama-server -m <model.gguf> --port 8080",
            url,
        )
        sys.exit(1)


def call_llm(prompt, backend, model=None, config=None):
    """
    Route the prompt to the configured LLM backend.

    Parameters
    ----------
    prompt : str
        The full research extraction prompt.
    backend : str
        One of: "openai", "anthropic", "llamacpp".
    model : str, optional
        Model name/path override.
    config : dict, optional
        Config from config.json research section.

    Returns
    -------
    str
        LLM response text.
    """
    cfg = config or {}

    if backend == "openai":
        return call_openai(
            prompt,
            model=model or cfg.get("openai_model"),
            api_key=cfg.get("openai_api_key"),
        )
    elif backend == "anthropic":
        return call_anthropic(
            prompt,
            model=model or cfg.get("anthropic_model"),
            api_key=cfg.get("anthropic_api_key"),
        )
    elif backend == "llamacpp":
        return call_llamacpp(
            prompt,
            model_path=model or cfg.get("llamacpp_model_path"),
            server_url=cfg.get("llamacpp_server_url"),
        )
    else:
        log.error("Unknown backend: %s. Use: openai, anthropic, llamacpp", backend)
        sys.exit(1)


def post_github_comment(town_name, county, brief_text, repo=None):
    """
    Post the research brief as a comment on the town's GitHub Issue.

    Finds the issue by searching for the town name, then adds a comment
    via the `gh` CLI.

    Parameters
    ----------
    town_name : str
    county : str
    brief_text : str
        Markdown research brief to post.
    repo : str, optional
        GitHub repo in OWNER/REPO format. Read from config.json if omitted.
    """
    if not repo:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
            repo = cfg.get("github", {}).get("repo", "")
        if not repo:
            log.warning("  No GitHub repo configured. Skipping comment post.")
            return

    # Search for the issue by town name
    search_query = f"{town_name} {county} County"
    try:
        result = subprocess.run(
            [
                "gh", "issue", "list",
                "--repo", repo,
                "--search", search_query,
                "--json", "number,title",
                "--limit", "5",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        issues = json.loads(result.stdout)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        log.warning("  Could not search GitHub Issues: %s", e)
        return

    if not issues:
        log.warning("  No GitHub Issue found for '%s'", search_query)
        return

    # Use the first matching issue
    issue_number = issues[0]["number"]
    issue_title = issues[0]["title"]

    comment_body = f"## Research Brief\n\n{brief_text}\n\n---\n*Auto-generated from Wikipedia by `extract_research.py`*"

    try:
        subprocess.run(
            [
                "gh", "issue", "comment",
                str(issue_number),
                "--repo", repo,
                "--body", comment_body,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        log.info("  Posted research brief to issue #%d: %s", issue_number, issue_title)
    except subprocess.CalledProcessError as e:
        log.warning("  Failed to post comment to issue #%d: %s", issue_number, e)


def extract_single(town_name, county, backend, model=None, output_dir=None,
                   force=False, post_comment=False, config=None):
    """
    Extract a research brief for a single town.

    Returns the output path, or None if skipped/failed.
    """
    article = load_cached_article(town_name, county)
    if article is None:
        log.warning("  No cached article for %s (%s County). Run fetch_wikipedia.py first.", town_name, county)
        return None

    if article.get("missing"):
        log.warning("  Wikipedia article missing for %s (%s County). Skipping.", town_name, county)
        return None

    out_dir = Path(output_dir) if output_dir else RESEARCH_DIR
    out_key = sanitize_filename(f"{town_name}_{county}")
    out_path = out_dir / f"{out_key}.md"

    if out_path.exists() and not force:
        log.info("  Research brief exists: %s (use --force to overwrite)", out_path.name)
        return out_path

    article_text = prepare_article_text(article)
    if not article_text.strip():
        log.warning("  Empty article text for %s. Skipping.", town_name)
        return None

    prompt = build_prompt(town_name, county, article_text)

    log.info("  Calling %s for %s (%s County)...", backend, town_name, county)
    try:
        brief = call_llm(prompt, backend, model=model, config=config)
    except Exception as e:
        log.error("  LLM call failed for %s: %s", town_name, e)
        return None

    # Write output
    out_dir.mkdir(parents=True, exist_ok=True)

    header = (
        f"# Research Brief: {town_name}, {county} County, NJ\n\n"
        f"*Source: [Wikipedia]({article.get('url', '')})*  \n"
        f"*Generated by: extract_research.py ({backend})*\n\n---\n\n"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header + brief + "\n")

    log.info("  Saved: %s", out_path)

    if post_comment:
        post_github_comment(town_name, county, brief)

    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Extract research briefs from cached Wikipedia articles using an LLM."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--town", type=str, help="Single town name.")
    group.add_argument("--all", action="store_true", help="Process all cached towns.")

    parser.add_argument("--county", type=str, help="County for disambiguation.")
    parser.add_argument(
        "--backend",
        type=str,
        choices=["openai", "anthropic", "llamacpp"],
        help="LLM backend to use. Defaults to config.json research.default_backend.",
    )
    parser.add_argument("--model", type=str, help="Model name/path override.")
    parser.add_argument(
        "--output-dir", type=str, help="Output directory for research briefs."
    )
    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing research briefs."
    )
    parser.add_argument(
        "--post-comment",
        action="store_true",
        help="Post research brief as a GitHub Issue comment.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be processed."
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging."
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    cfg = load_config()
    backend = args.backend or cfg.get("default_backend", "openai")

    if args.all:
        towns = load_towns_csv()
        print(f"Extracting research briefs for cached towns (backend: {backend})...")
        print(f"  Output dir: {args.output_dir or RESEARCH_DIR}")
        print()

        extracted = 0
        skipped = 0
        errors = 0

        for i, row in enumerate(towns, 1):
            name = row.get("town_name", "").strip()
            county = row.get("county", "").strip()
            if not name or not county:
                continue

            if args.dry_run:
                cache_key = sanitize_filename(f"{name}_{county}")
                cached = (CACHE_DIR / f"{cache_key}.json").exists()
                out_key = sanitize_filename(f"{name}_{county}")
                has_brief = (
                    Path(args.output_dir) / f"{out_key}.md"
                    if args.output_dir
                    else RESEARCH_DIR / f"{out_key}.md"
                ).exists()
                status = "SKIP (no cache)" if not cached else (
                    "SKIP (exists)" if has_brief and not args.force else "EXTRACT"
                )
                print(f"  [{status}] {name} ({county} County)")
                continue

            result = extract_single(
                name,
                county,
                backend,
                model=args.model,
                output_dir=args.output_dir,
                force=args.force,
                post_comment=args.post_comment,
                config=cfg,
            )

            if result:
                extracted += 1
            else:
                skipped += 1

        if not args.dry_run:
            print(f"\nDone. Extracted: {extracted}, Skipped: {skipped}")
    else:
        # Single town
        town_name = args.town
        county = args.county

        if not county:
            towns = load_towns_csv()
            matches = [
                t for t in towns
                if t.get("town_name", "").strip().lower() == town_name.strip().lower()
            ]
            if len(matches) == 1:
                county = matches[0].get("county", "")
            elif len(matches) > 1:
                counties = [m.get("county", "") for m in matches]
                print(
                    f"Multiple towns named '{town_name}' in counties: {counties}. "
                    f"Use --county to disambiguate."
                )
                sys.exit(1)
            else:
                print(f"Town '{town_name}' not found in towns.csv. Use --county to specify.")
                sys.exit(1)

        if args.dry_run:
            cache_key = sanitize_filename(f"{town_name}_{county}")
            print(f"Would extract: {town_name} ({county} County)")
            print(f"  Cache: data/wikipedia_cache/{cache_key}.json")
            print(f"  Backend: {backend}")
            sys.exit(0)

        result = extract_single(
            town_name,
            county,
            backend,
            model=args.model,
            output_dir=args.output_dir,
            force=args.force,
            post_comment=args.post_comment,
            config=cfg,
        )

        if result:
            print(f"\nResearch brief saved to: {result}")
        else:
            print("\nFailed to extract research brief.")
            sys.exit(1)


if __name__ == "__main__":
    main()
