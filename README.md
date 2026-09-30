# Find-Refs

> Professional CLI for finding, validating, filtering, and exporting academic references — with **Scopus indexing detection** built in.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.0.0-green.svg)]()

**Find-Refs** is a focused, agent-friendly command-line tool for researchers, students, and AI assistants who need to:

- 🔍 **Search** academic papers via **OpenAlex** — free, no API key needed (just your email)
- 🎯 **Filter** out unsuitable references (by year, citations, journal quartile, keywords, open-access status)
- 📊 **Detect** whether each paper is indexed in Scopus, **offline** from bundled SCImago data, with quartile info (Q1/Q2/Q3/Q4)
- 📤 **Export** curated reference lists to BibTeX, RIS, CSV, JSONL, or Markdown
- 🔐 **Manage multiple OpenAlex mailtos** — rotate between accounts to avoid rate limits

Designed for **agents and automation**: every command supports `--json` for structured output and returns deterministic exit codes.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
  - [Linux / macOS](#linux--macos)
  - [Windows](#windows)
  - [Manual / Development](#manual--development)
- [Configuration & Multi-Account Management](#configuration--multi-account-management)
- [Commands](#commands)
  - [`findref setup`](#findref-setup)
  - [`findref search`](#findref-search)
  - [`findref validate`](#findref-validate)
  - [`findref filter`](#findref-filter)
  - [`findref export`](#findref-export)
  - [`findref config`](#findref-config)
  - [`findref doctor`](#findref-doctor)
  - [`findref guide`](#findref-guide)
  - [`findref cache`](#findref-cache)
- [Agent Integration](#agent-integration)
  - [JSON Output](#json-output)
  - [Exit Codes](#exit-codes)
  - [Environment Variables](#environment-variables)
- [Workflow Examples](#workflow-examples)
- [Project Structure](#project-structure)
- [Migration from v1.x](#migration-from-v1x)
- [License](#license)

---

## Quick Start

```bash
# 1. Install (Linux / macOS / WSL) - see "Installation" for Windows
curl -fsSL https://raw.githubusercontent.com/farisalfatih/find_references_scopus/main/install/install.sh | bash

# 2. Run setup wizard
findref setup

# 3. Search references
findref search "deep learning for financial forecasting" --year-from 2020

# 4. Filter
findref filter results.json --min-year 2020 --scopus-only --quartile Q1,Q2 -o filtered.json

# 5. Export to BibTeX
findref export filtered.json --format bibtex -o references.bib
```

---

## Installation

All installers follow the same (correct) flow: **clone -> create virtualenv -> install packages inside the venv**.
Nothing is installed into your system Python, so you will not hit
`externally-managed-environment` or `Cannot uninstall typing_extensions ... installed by debian` errors.

Requirements: **Python 3.10+** (git is optional - the installers fall back to downloading a zip/tar.gz).

Everything is installed under one folder:

| Platform | Install folder | `findref` command |
|----------|----------------|-------------------|
| Linux / macOS | `~/.findref/` (`src/` + `venv/`) | symlink in `~/.local/bin` |
| Windows | `%LOCALAPPDATA%\findref\app\` (`src\` + `venv\`) | shim in `%LOCALAPPDATA%\findref\app\bin` (added to user PATH) |

### Linux / macOS / WSL - one line

```bash
curl -fsSL https://raw.githubusercontent.com/farisalfatih/find_references_scopus/main/install/install.sh | bash
```

The script asks no questions. Options (pass with `bash -s -- <option>`):

| Option | Meaning |
|--------|---------|
| `--dev` | Editable install (needs a local clone) |
| `--dir PATH` | Install somewhere other than `~/.findref` |
| `--branch NAME` | Use another git branch |
| `--no-modify-path` | Do not touch `~/.bashrc` / `~/.zshrc` |
| `--uninstall` | Remove findref |

Example: `curl -fsSL <url> | bash -s -- --no-modify-path`

Re-running the same command updates findref.

### Windows - one command with curl

Windows 10/11 ships with `curl.exe`. Run in **CMD or PowerShell**:

```bat
curl.exe -fsSL https://raw.githubusercontent.com/farisalfatih/find_references_scopus/main/install/install.ps1 -o install.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

> Type `curl.exe`, not `curl` - in PowerShell `curl` is an alias for `Invoke-WebRequest`.

Then **close and reopen the terminal** and run `findref --version`.

Options are environment variables, e.g. in PowerShell:

```powershell
$env:FINDREF_HOME = "D:\tools\findref"; .\install.ps1      # custom folder
$env:FINDREF_UNINSTALL = "1"; .\install.ps1                  # uninstall
```

Need Python first? `winget install -e --id Python.Python.3.12`

### Manual installation (what the scripts do)

**Linux / macOS**

```bash
git clone -b main https://github.com/farisalfatih/find_references_scopus.git
cd find_references_scopus
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install .            # or: pip install -e .   for development
findref --version
```

**Windows (PowerShell)**

```powershell
git clone -b main https://github.com/farisalfatih/find_references_scopus.git
cd find_references_scopus
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install .
findref --version
```

If PowerShell blocks `Activate.ps1`: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or use CMD and run `.venv\Scripts\activate.bat`.

With the manual method you must activate the venv (`source .venv/bin/activate` / `.\.venv\Scripts\Activate.ps1`) in every new terminal before using `findref`.

### Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `error: externally-managed-environment` | Debian/Ubuntu protect system Python (PEP 668). Use the installer or a venv - do **not** use `--break-system-packages`. |
| `Cannot uninstall typing_extensions ... RECORD file not found ... installed by debian` | You ran `pip install` against the system Python. Use a venv (the installers do this automatically). |
| `The virtual environment was not created successfully` / `ensurepip is not available` | `sudo apt install python3-venv python3-full` |
| `findref: command not found` | Open a new terminal, or `source ~/.bashrc`. Windows: reopen the terminal. |
| `curl` in PowerShell prints a security prompt / errors | Use `curl.exe`. |
| Stale files after upgrading | Delete `build/` and `*.egg-info/` in the source folder, then reinstall. |

### Update / Uninstall

```bash
# Update: re-run the install command (Linux/macOS: curl ... | bash, Windows: the two commands above)

# Uninstall:
findref uninstall                     # interactive; asks whether to also delete your settings
findref uninstall --yes               # no prompts, keep config/cache/logs
findref uninstall --yes --purge       # no prompts, delete everything including config/cache/logs
findref uninstall --dry-run           # show what would be removed, change nothing

# Alternative (works even if findref itself won't run) — same effect, config is always kept:
curl -fsSL https://raw.githubusercontent.com/farisalfatih/find_references_scopus/main/install/install.sh | bash -s -- --uninstall
#   Windows (run install.ps1 as in the Installation section, then):
#   $env:FINDREF_UNINSTALL = "1"; .\install.ps1
```

Installed with `pip install find-refs` yourself, into your own virtualenv?
`findref uninstall` cannot remove program files it doesn't own; it tells you the
`pip uninstall find-refs` command to run instead, and still handles `--purge`.

Your config is kept unless you ask for `--purge` (see the paths in the next section).

---

## Configuration & Multi-Account Management

Find-Refs stores its configuration at:

| Platform | Path |
|----------|------|
| Linux    | `~/.config/findref/config.toml` (or `$XDG_CONFIG_HOME/findref/config.toml` if that variable is set) |
| macOS    | `~/Library/Application Support/findref/config.toml` |
| Windows  | `%LOCALAPPDATA%\findref\config.toml` |

This is a different folder from where the *program* is installed (see the
[Installation](#installation) table above), on purpose: running the installer's
`--uninstall`, or `findref uninstall` without `--purge`, removes the program but
never touches this folder. Run `findref config path` to print the exact file, or
`findref doctor` to see every folder findref uses (config, cache, logs, data).

Override the config folder with the `FINDREF_CONFIG_DIR` environment variable
(useful for CI / portable installs).

### Adding multiple accounts

```bash
# Interactive
findref config add-account --name alice-univ
# Non-interactive (for CI / scripts)
findref config add-account \
  --name alice-univ \
  --label "Alice @ University" \
  --mailto "alice@university.edu" \
  --non-interactive

# Switch between accounts instantly
findref config use alice-univ
findref config use bob-personal

# List accounts
findref config list
```

### Account fields

Find-Refs uses **OpenAlex only** for online lookups, and OpenAlex needs **no API key** —
only a contact email ("polite pool") for faster, more reliable rate limits.
Scopus indexing and quartiles come from bundled SCImago data, so no Scopus key is used either.

An account therefore stores just:

| Field             | Description                                              |
|-------------------|----------------------------------------------------------|
| `label`           | Human-friendly name (optional)                           |
| `openalex_mailto` | Email for the OpenAlex polite pool                       |

> Upgrading from an older config? Leftover `scopus_api_key`, `crossref_mailto`, etc. are ignored
> and removed the next time the config is saved.

---

## OpenAlex Multi-Mailto Rotation (Rate-Limit Avoidance)

OpenAlex is **free**, but applies per-mailto rate limits. By rotating through
multiple mailtos, you can effectively multiply your throughput N times (where
N = number of unique mailtos).

### How it works

The `OpenAlexClient` accepts a `MailtoPool` — a round-robin / reactive pool
of mailtos. When you run `findref search --openalex-pool`, findref automatically
collects mailtos from:

1. **Current account's `openalex_mailto`** (preferred)
2. **All other accounts' `openalex_mailto`** (rotation candidates)
3. **`defaults.openalex_mailto_pool`** (extra mailtos via `findref config add-mailto`)
4. **`FINDREF_OPENALEX_MAILTO_POOL` env var** (CI / Docker)

On HTTP 429, the current mailto is marked as "cooling down" for 60 seconds
(configurable), and the next request automatically uses the next mailto.

### Quick start

```bash
# 1. Add multiple accounts (each with a different mailto)
findref config add-account --name alice --openalex-mailto alice@univ.edu -y
findref config add-account --name bob   --openalex-mailto bob@univ.edu -y
findref config add-account --name carol --openalex-mailto carol@univ.edu -y

# 2. Add extra mailtos WITHOUT creating fake accounts
findref config add-mailto dave@univ.edu
findref config add-mailto eve@univ.edu

# 3. Verify the pool
findref config show-pool

# 4. Search with pool rotation
findref search "deep learning" --openalex-pool --limit 100

# 5. Or with proactive rotation (rotate every request, not just on 429)
findref search "deep learning" --openalex-pool --openalex-rotate
```

### Config persistence

Set defaults in config.toml so you don't need flags every time:

```bash
findref config set-default openalex_auto_rotate true
# Now `findref search` always rotates
```

Or via env var (for CI / Docker):

```bash
export FINDREF_OPENALEX_MAILTO_POOL="alice@univ.edu,bob@univ.edu"
export FINDREF_OPENALEX_AUTO_ROTATE=true
findref search "topic" --openalex-pool
```

### Pool stats (for debugging)

```bash
# JSON output includes pool stats
findref search "topic" --openalex-pool --json | jq '.openalex_pool_stats'
```

Example output:

```json
{
  "alice@univ.edu": {"request_count": 5, "in_cooldown": false},
  "bob@univ.edu":   {"request_count": 4, "in_cooldown": false},
  "carol@univ.edu": {"request_count": 4, "in_cooldown": true, "cooldown_remaining": 45.2}
}
```

---

## Flexible Output Location

All output-producing commands (`search`, `filter`, `export`, `validate`)
support flexible output location resolution:

### Priority (highest first)

| Method | Example |
|--------|---------|
| 1. `--output path` (explicit file) | `findref search "..." -o /tmp/refs.json` |
| 2. `--output dir/` (dir + auto-name) | `findref search "..." -o /tmp/refs/ --auto-name` |
| 3. `--output-dir dir` (dir + default name) | `findref search "..." --output-dir /tmp/refs/` |
| 4. `FINDREF_OUTPUT_DIR` env var | `FINDREF_OUTPUT_DIR=/tmp/refs findref search "..."` |
| 5. `output_dir` from config | `findref config set-default output_dir /tmp/refs` |
| 6. Current working directory | (fallback) |

### Auto-naming

Use `--auto-name` to automatically generate a timestamped filename:

```bash
findref search "deep learning" --auto-name --output-dir ./refs/
# → ./refs/search_deep-learning_20260927_120000.json

findref filter results.json --auto-name --output-dir ./refs/
# → ./refs/filter_results_filtered_20260927_120001.json

findref export results.json --format bibtex --auto-name --output-dir ./refs/
# → ./refs/export_results_bibtex_20260927_120002.bib
```

Enable auto-name globally:

```bash
findref config set-default auto_name true
# Now all commands auto-name unless you pass --no-auto-name
```

Or via env var:

```bash
export FINDREF_AUTO_NAME=true
findref search "topic" --output-dir ./refs/
```

---

## Project-Local Config (`.findref.yaml`)

Create a `.findref.yaml` file in your project root to override user defaults
**per project**. This is useful for:

- Different SCImago path per project
- Different OpenAlex mailto pool per project
- Different default output directory per project

### Example `.findref.yaml`

```yaml
# Project-local findref config
# This file overrides ~/.findref/config.toml defaults for THIS project only.
# CLI flags and env vars still take precedence over this file.

defaults:
  openalex_mailto: alice@this-project.edu
  openalex_mailto_pool: "alice@univ.edu,bob@univ.edu"
  openalex_auto_rotate: true
  output_dir: ./refs        # All output goes to ./refs/ in this project
  auto_name: true            # Auto-name files with timestamp
  year_from: 2020
  year_to: 2025
  language: en

# Top-level convenience (same as defaults.scimago_path)
scimago_path: ./data/scimagojr_2025.json
```

### How it works

When you run any `findref` command, the CLI walks up from your current
directory looking for `.findref.yaml` (or `.findref.yml`, `findref.yaml`).
The first one found is loaded and its values override the user config
defaults — but are themselves overridden by CLI flags and env vars.

```bash
# In a project with .findref.yaml:
cd my-research-project/
findref search "neural networks" --limit 50
# → automatically saves to ./refs/search_neural-networks_<timestamp>.json
# → uses the project's OpenAlex mailto pool
# → uses the project's SCImago path
```

---

## SCImago ISSN Filter (Restrict Search to Scopus Journals)

When enabled, ``findref search`` restricts results to journals indexed in SCImago,
optionally filtered by subject area and quartile. This is the core feature for
ensuring search results are Scopus-indexed (the ``scopus_indexed`` flag will be
``true`` for all results by construction).

### How to configure

**Option A: Interactive wizard (recommended)**

```bash
findref config set-issn-filter
```

This will:
1. Ask whether to enable the filter
2. Show available subject areas in your SCImago JSON (multi-select)
3. Ask which quartiles to include (Q1, Q2, Q3, Q4, unranked)
4. Ask whether to include unranked Scopus journals (quartile '-')
5. Save and show a preview of the resolved ISSN count

**Option B: Non-interactive (for scripts / CI)**

```bash
findref config set-issn-filter \
    --enable \
    --subject-areas "Computer Science,Mathematics" \
    --quartiles "Q1,Q2" \
    --include-unranked \
    --scimago-path /path/to/scimagojr_2025.json \
    --non-interactive
```

**Option C: From setup wizard**

```bash
findref setup
# Step 3 of the wizard handles SCImago path + ISSN filter config interactively
```

### Show current filter config

```bash
findref config show-issn-filter
# Output:
#   Enabled: yes
#   Subject areas: Computer Science, Mathematics
#   Quartiles: Q1,Q2
#   Include unranked: yes
#   SCImago JSON: /path/to/scimagojr_2025.json
#   Resolved: 247 ISSNs
#   Stats: {total_journals: 5000, after_subject_filter: 312, ...}
```

### Disable filter for one search

```bash
# Search ALL journals (ignores config)
findref search "topic" --no-issn-filter

# Override subject area + quartile for just this search
findref search "topic" --subject-areas "Medicine" --quartile Q1
```

### Get SCImago data

Download SCImago journal data from https://scimagojr.com/ (free, registration
required). The expected JSON format is a list of journal dicts:

```json
[
  {
    "issn_electronic": "0306-4379",
    "title": "Decision Support Systems",
    "quartile": "Q1",
    "open_access": "closed",
    "subject_area": "Computer Science",
    "best_quartile": "Q1"
  },
  ...
]
```

You can also use the SCImago CSV export — convert it to JSON first:

```bash
# Future: findref scimago load scimagojr_2025.csv
# For now, use any CSV→JSON converter (e.g. https://csvjson.com/)
```

---

## Commands

### `findref setup`

Interactive first-run wizard. Walks you through:

1. Setting your default OpenAlex mailto (polite pool)
2. Adding your first account (optional — an extra mailto for rotation)
3. Configuring the SCImago Scopus / quartile filter
4. Verifying OpenAlex connectivity

Idempotent — safe to re-run anytime.

```bash
findref setup                     # Interactive
findref setup -y                  # Non-interactive (use env vars / defaults)
```

---

### `findref search`

Search academic papers via **OpenAlex** (the only search source). If the SCImago
ISSN filter is enabled in config, search is restricted to journals indexed in
SCImago (filtered by subject area + quartile).

```bash
# Basic search (uses ISSN filter if configured)
findref search "LSTM bitcoin price prediction"

# With year filter + limit
findref search "cancer immunotherapy" \
  --year-from 2020 --year-to 2025 \
  --limit 100 \
  --output results.json

# Disable ISSN filter for this search (search ALL journals)
findref search "topic" --no-issn-filter

# Override subject area + quartile for this search
findref search "topic" --subject-areas "Computer Science,Medicine" --quartile Q1,Q2

# Explicit ISSN list (overrides SCImago filter)
findref search "machine learning" --issn 1234-5678,9876-5432

# Use mailto pool to avoid rate limits
findref search "topic" --openalex-pool --openalex-rotate

# JSON output for agent integration
findref search "neural networks" --json | jq '.results | length'

# Don't annotate Scopus (faster)
findref search "topic" --no-annotate-scopus
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--year-from` | config default | Minimum publication year |
| `--year-to` | config default | Maximum publication year |
| `--limit, -n` | 50 | Maximum number of results |
| `--per-page` | 100 | Page size for API requests |
| `--issn` | (none) | Override ISSN filter (comma-separated, or 'none' to disable) |
| `--issn-filter / --no-issn-filter` | config default | Enable/disable SCImago ISSN filter |
| `--subject-areas` | config default | Override subject areas (comma-separated) |
| `--quartile` | config default | Override quartile filter (Q1,Q2 / Q1 / all) |
| `--annotate-scopus / --no-annotate-scopus` | on | Look up Scopus indexing after search |
| `--output, -o` | (stdout) | Save results to JSON file (path or dir) |
| `--output-dir` | (none) | Directory to save output files |
| `--auto-name / --no-auto-name` | config default | Auto-name output with timestamp |
| `--openalex-pool` | off | Use ALL mailtos as rotation pool |
| `--openalex-rotate / --no-openalex-rotate` | config default | Rotate mailto per request |
| `--json` | off | Output JSON to stdout (agent-friendly) |

---

### `findref validate`

Validate a list of DOIs and check Scopus indexing. Enriches each DOI with metadata
via OpenAlex.

**Supported input formats:**

- `.txt` — one DOI per line (comments with `#` are ignored)
- `.bib` — BibTeX file (DOIs extracted via bibtexparser)
- `--dois` — comma-separated list of DOIs

**Markdown files (.md) are NOT supported.** (Markdown extraction was removed per user request.)

```bash
# From a text file (one DOI per line)
findref validate -i dois.txt

# From a .bib file (extracts DOIs via bibtexparser)
findref validate -i my_refs.bib

# Direct list
findref validate --dois "10.1000/xxx,10.1000/yyy"

# Save enriched results
findref validate -i dois.txt -o validated.json

# Use OpenAlex as enrichment source (default)
findref validate -i dois.txt --json | jq '.scopus_count'
```

---

### `findref filter`

Filter out unsuitable references from a JSON file.

```bash
# Year + citation filter
findref filter results.json \
  --min-year 2020 \
  --max-year 2025 \
  --min-citations 5 \
  -o filtered.json

# Scopus Q1/Q2 only
findref filter results.json \
  --scopus-only \
  --quartile Q1,Q2 \
  -o q1q2_only.json

# Keyword blacklist + whitelist
findref filter results.json \
  --exclude-keywords "preprint,survey,workshop" \
  --include-keywords "neural network,deep learning" \
  -o filtered.json

# Open access only
findref filter results.json --open-access-only -o oa_only.json

# Dry run (preview without saving)
findref filter results.json --scopus-only --dry-run

# Disable deduplication
findref filter results.json --no-deduplicate
```

**Filter rules available:**

| Flag | Description |
|------|-------------|
| `--min-year YYYY` | Drop papers before this year |
| `--max-year YYYY` | Drop papers after this year |
| `--min-citations N` | Drop papers with fewer than N citations |
| `--scopus-only` | Keep only Scopus-indexed papers |
| `--quartile Q1,Q2` | Keep only specified quartiles |
| `--no-unranked` | Drop Scopus journals with quartile `-` (unranked) |
| `--exclude-keywords kw1,kw2` | Drop papers containing these keywords |
| `--include-keywords kw1,kw2` | Keep only papers containing these keywords |
| `--open-access-only` | Keep only open-access papers |
| `--language en,fr` | Keep only specified languages |
| `--no-deduplicate` | Disable DOI + fuzzy title deduplication |

---

### `findref export`

Export papers to multiple formats.

```bash
# BibTeX (default)
findref export results.json --format bibtex -o refs.bib

# RIS (for EndNote / Covidence / Mendeley)
findref export results.json --format ris -o refs.ris

# CSV (for Excel review)
findref export results.json --format csv -o refs.csv

# JSONL (for agent processing)
findref export results.json --format jsonl -o refs.jsonl

# Markdown (human-readable)
findref export results.json --format md -o refs.md

# Re-annotate Scopus + export only Scopus-indexed
findref export results.json --annotate-scopus --scopus-only -o scopus_only.bib
```

**Supported formats:**

| Format | Extension | Notes |
|--------|-----------|-------|
| `bibtex` | `.bib` | Embeds `scopus_indexed = {true/false}` field per entry |
| `ris` | `.ris` | Adds `N1` (notes) field with Scopus flag + quartile |
| `csv` | `.csv` | All columns including `scopus_indexed`, `quartile` |
| `jsonl` | `.jsonl` | One paper per line — agent-friendly |
| `md` | `.md` | Human-readable with Scopus/Q badge per entry |

---

### `findref config`

Manage accounts (OpenAlex mailtos) and defaults. See [Configuration](#configuration--multi-account-management).

```bash
findref config list                          # List all accounts
findref config add-account --name alice      # Add account (interactive)
findref config use alice                      # Switch to account
findref config show                            # Show current account
findref config remove alice                    # Delete account
findref config set-default year_from 2020     # Update a default value
findref config path                            # Print config file path
findref config edit                            # Open in $EDITOR

# OpenAlex mailto pool management (rate-limit avoidance)
findref config show-pool                      # Show all mailtos collected for rotation
findref config add-mailto bob@univ.edu        # Add mailto to rotation pool
findref config remove-mailto bob@univ.edu     # Remove mailto from pool
findref config set-default openalex_auto_rotate true  # Rotate per request
```

---

### `findref doctor`

Diagnose installation, config, and OpenAlex connectivity.

```bash
findref doctor                # Interactive check
findref doctor --json         # JSON output
```

Checks:
- ✅ Python version (3.10+)
- ✅ Config file exists and loads
- ✅ Cache / logs / data directories writable
- ✅ Bundled SCImago data present
- ✅ OpenAlex reachable, and which mailto is in use (warns if still the placeholder)

---

### `findref guide`

Print the full workflow guide.

```bash
findref guide
```

---

### `findref cache`

Manage the HTTP response cache (SQLite-backed).

```bash
findref cache stats    # Show entries + path
findref cache clear    # Wipe cache
```

---

## Agent Integration

Find-Refs is designed to be called by AI agents, scripts, and CI pipelines.

### JSON Output

Every command supports `--json` for structured output:

```bash
findref search "topic" --json
findref validate -i dois.txt --json
findref filter results.json --scopus-only --json
findref export results.json --format bibtex --json
findref config list --json
findref doctor --json
```

### Exit Codes

| Code | Meaning          |
|------|------------------|
| 0    | Success          |
| 1    | Generic error    |
| 2    | No results found |
| 3    | Rate-limited by API |
| 4    | Access denied by OpenAlex (HTTP 401/403) |
| 5    | Network error    |
| 6    | Config error     |
| 130  | Interrupted (Ctrl+C) |

### Environment Variables

Override config without modifying files — useful in CI / Docker.

| Variable | Purpose |
|----------|---------|
| `FINDREF_CONFIG_DIR` | Use a custom config directory (portable install) |
| `FINDREF_CACHE_DIR` | Use a custom HTTP cache directory |
| `FINDREF_LOGS_DIR` | Use a custom logs directory |
| `FINDREF_DATA_DIR` | Use a custom user data directory |
| `FINDREF_OPENALEX_MAILTO` | Override OpenAlex polite-pool email |
| `FINDREF_OPENALEX_MAILTO_POOL` | Comma-sep list of OpenAlex mailtos for rotation |
| `FINDREF_OPENALEX_AUTO_ROTATE` | `true` to rotate mailtos proactively per request |
| `FINDREF_OUTPUT_DIR` | Default output directory for all commands |
| `FINDREF_AUTO_NAME` | `true` to enable auto-naming globally |

### Example: Agent workflow (Python)

```python
import subprocess
import json

# Search
result = subprocess.run(
    ["findref", "search", "deep learning finance", "--json"],
    capture_output=True, text=True
)
if result.returncode != 0:
    print(f"Search failed: {result.stderr}")
else:
    data = json.loads(result.stdout)
    print(f"Found {data['count']} papers")
    print(f"Scopus-indexed: {sum(1 for p in data['results'] if p['scopus_indexed'])}")

# Filter + export
with open("results.json", "w") as f:
    json.dump(data, f)

subprocess.run([
    "findref", "filter", "results.json",
    "--scopus-only", "--quartile", "Q1,Q2",
    "-o", "filtered.json"
])
subprocess.run([
    "findref", "export", "filtered.json",
    "--format", "bibtex", "-o", "refs.bib"
])
```

---

## Workflow Examples

### Example 1: Literature review for a paper

```bash
# Step 1: Setup
findref setup

# Step 2: Search OpenAlex (Scopus-indexed journals only, Q1/Q2)
findref search "transformer attention mechanism" \
  --issn-filter --quartile Q1,Q2 \
  --year-from 2017 \
  --limit 100 \
  -o search_results.json

# Step 3: Filter to high-quality references only
findref filter search_results.json \
  --min-year 2020 \
  --min-citations 10 \
  --scopus-only \
  --quartile Q1,Q2 \
  --exclude-keywords "preprint,survey" \
  -o high_quality.json

# Step 4: Export to BibTeX
findref export high_quality.json --format bibtex -o references.bib

# Step 5: Also export to Markdown for human review
findref export high_quality.json --format md -o references.md
```

### Example 2: Validate an existing .bib file

```bash
# Extract DOIs from existing BibTeX, check Scopus indexing
findref validate -i my_refs.bib -o validated.json

# Show summary
findref validate -i my_refs.bib --json | jq '{found: .found, scopus: .scopus_count, total: .input_count}'
```

### Example 3: Several mailtos for heavy searching

```bash
# One-time: register a few mailtos (each account = one OpenAlex mailto)
findref config add-account --name alice --mailto alice@univ.edu -y
findref config add-account --name bob   --mailto bob@univ.edu   -y

# Rotate between them when OpenAlex rate-limits
findref search "..." --openalex-pool --limit 200

# Or pick one explicitly
findref config use bob
```

### Example 4: Agent batch processing

```bash
# Use env vars only (no config file — perfect for ephemeral CI)
export FINDREF_OPENALEX_MAILTO="bot@company.com"

findref search "neural networks" --json | \
  jq '.results[] | select(.scopus_indexed == true) | .doi' | \
  xargs -I {} findref validate --dois {} --json
```

---

## Project Structure

```
find-refs/
├── find_references_scopus/
│   ├── __init__.py              # Package metadata + exit codes
│   ├── __main__.py              # python -m find_references_scopus
│   ├── cli.py                   # Main Typer app + top-level commands
│   ├── config/
│   │   ├── defaults.py          # Path resolution (cross-platform)
│   │   └── manager.py           # Multi-account config manager (TOML)
│   ├── commands/
│   │   ├── setup.py             # findref setup (interactive wizard)
│   │   ├── config_cmd.py        # findref config (sub-app)
│   │   ├── search.py            # findref search
│   │   ├── validate.py          # findref validate
│   │   ├── filter_cmd.py        # findref filter
│   │   ├── export_cmd.py        # findref export
│   │   ├── doctor.py            # findref doctor
│   │   ├── guide.py             # findref guide
│   │   └── cache_cmd.py         # findref cache (sub-app)
│   ├── api/
│   │   ├── base.py              # BaseClient with retry/rate-limit/cache
│   │   └── openalex.py          # OpenAlex API client (the only online API)
│   ├── core/
│   │   ├── models.py             # Paper, ReferenceList dataclasses
│   │   ├── scopus_checker.py    # Scopus indexing detection (offline, SCImago)
│   │   ├── filter_rules.py      # Filter engine + rule classes
│   │   └── deduplication.py     # DOI + fuzzy title dedup
│   ├── exporters/
│   │   ├── base.py              # Exporter base class
│   │   ├── bibtex.py            # BibTeX exporter (with scopus_indexed field)
│   │   ├── ris.py               # RIS exporter
│   │   ├── csv_exp.py           # CSV exporter
│   │   ├── jsonl.py             # JSONL exporter
│   │   └── markdown.py          # Markdown exporter
│   ├── utils/
│   │   ├── __init__.py          # Console + logging + JSON helpers
│   │   └── cache.py             # SQLite HTTP cache (requests-cache)
│   └── data/
│       └── scimagojr_2025.json  # Bundled SCImago journal data (optional)
├── install/
│   ├── install.sh               # Linux / macOS installer
│   └── install.ps1              # Windows installer
├── tests/
│   ├── test_config.py
│   ├── test_filter.py
│   └── test_export.py
├── pyproject.toml
├── README.md
└── LICENSE
```

---

## Migration from v1.x

Find-Refs v2.0 is a complete rewrite focused on **reference search and Scopus detection only**.

### Removed (v1.x features no longer present)

- `step_08_extract_claims` — Markdown [DOI] extraction (use your AI agent for this)
- `step_09_extract_references` — Markdown reference generation (replaced by `findref export --format md`)
- Prompt engineering guides for paper writing (out of scope)

### Renamed commands

| v1.x                | v2.0                              |
|---------------------|-----------------------------------|
| `find-refs fetch`   | `findref search` (OpenAlex) |
| `find-refs filter`  | `findref filter` (rewritten)       |
| `find-refs deduplicate` | `findref filter --deduplicate` (built-in) |
| `find-refs remove-excluded` | `findref filter --exclude-keywords` |
| `find-refs distribution` | (removed — use `--json` + `jq`) |
| `find-refs merge-journal` | Automatic (part of `findref search` and `findref filter`) |
| `find-refs filter-scopus` | `findref filter --scopus-only` |
| `find-refs extract-claims` | **Removed** (was markdown extraction) |
| `find-refs extract-references` | `findref export --format md` |
| `find-refs select-articles` | `findref filter --include-keywords ...` or `--include-dois` |
| `find-refs convert-bib` | `findref export --format bibtex` |

### New in v2.0

- ✨ OpenAlex as the single search source (no API key), with multi-mailto rotation (`findref config`)
- ✨ Offline Scopus / quartile detection from bundled SCImago data
- ✨ Multiple export formats (RIS, CSV, JSONL, Markdown)
- ✨ `--json` flag on every command (agent-friendly)
- ✨ Deterministic exit codes
- ✨ HTTP response cache (SQLite-backed)
- ✨ Install scripts for Linux / macOS / Windows
- ✨ `findref setup` interactive wizard
- ✨ `findref doctor` diagnostics
- ✨ Environment variable overrides (for CI / Docker)

---

## License

MIT — see [LICENSE](LICENSE).
