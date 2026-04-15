# Extract Research Briefs

Extract structured research briefs from cached Wikipedia articles using an LLM. Produces concise Markdown research cards optimized for Instagram Reel script writing.

## Prerequisites

- Wikipedia articles cached (run `fetch_wikipedia.py --all` first)
- An LLM backend configured:
  - **OpenAI**: `pip install openai` + `OPENAI_API_KEY` env var
  - **Anthropic**: `pip install anthropic` + `ANTHROPIC_API_KEY` env var
  - **llama.cpp**: local server running (`llama-server -m <model.gguf>`)

## Usage

### Single town

```bash
python scripts/extract_research.py --town "Hoboken"
```

### Disambiguation

```bash
python scripts/extract_research.py --town "Lawrence" --county Mercer
```

### All cached towns

```bash
python scripts/extract_research.py --all
```

### Specify backend

```bash
python scripts/extract_research.py --town "Hoboken" --backend openai
python scripts/extract_research.py --town "Hoboken" --backend anthropic
python scripts/extract_research.py --town "Hoboken" --backend llamacpp
```

### Specify model

```bash
python scripts/extract_research.py --town "Hoboken" --backend openai --model gpt-4o-mini
```

### Force re-extraction

```bash
python scripts/extract_research.py --all --force
```

### Post as GitHub Issue comment

```bash
python scripts/extract_research.py --town "Hoboken" --post-comment
```

Requires `gh` CLI authenticated and `github.repo` set in `config.json`.

### Dry run

```bash
python scripts/extract_research.py --all --dry-run
```

## Output

Research briefs are saved to `data/research/{town_name}_{county}.md`.

Each brief contains:

1. **Founding & Name Origin** — incorporation date, etymology
2. **Most Interesting Historical Facts** — 3-5 surprising facts ranked by audience appeal
3. **Pop Culture & Notable People** — movies, TV, celebrities, events
4. **Notable Landmarks & Places** — parks, historic sites, unique spots
5. **Surprising Statistics** — population quirks, geographic oddities, records

## LLM backends

### OpenAI

```bash
export OPENAI_API_KEY="sk-..."
python scripts/extract_research.py --town "Hoboken" --backend openai
```

Or set `research.openai_api_key` in `config.json` (not recommended for shared repos).

### Anthropic

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python scripts/extract_research.py --town "Hoboken" --backend anthropic
```

### llama.cpp (local, Apple Silicon Metal)

Start the server:

```bash
llama-server -m ~/models/llama-3-8b.gguf --port 8080 -ngl 99
```

Then run:

```bash
python scripts/extract_research.py --town "Hoboken" --backend llamacpp
```

The default server URL is `http://localhost:8080/v1/chat/completions`. Override in `config.json` under `research.llamacpp_server_url`.

## Configuration

Settings in `config.json` under `research`:

| Key | Default | Description |
|-----|---------|-------------|
| `default_backend` | `openai` | LLM backend: `openai`, `anthropic`, `llamacpp` |
| `openai_model` | `gpt-4o` | OpenAI model name |
| `anthropic_model` | `claude-sonnet-4-20250514` | Anthropic model name |
| `llamacpp_server_url` | `http://localhost:8080/v1/chat/completions` | Local server URL |
| `llamacpp_model_path` | `null` | Path to GGUF model (sent in request) |
| `max_article_length` | `30000` | Max chars of article text sent to LLM |
| `output_dir` | `data/research` | Output directory for briefs |

## GitHub Issue integration

With `--post-comment`, the script:

1. Searches for a matching GitHub Issue by town name and county
2. Posts the research brief as a comment on the first matching issue
3. Requires `gh` CLI authenticated and `github.repo` configured

This integrates with the project board workflow — the research brief appears directly on the town's tracking issue.
