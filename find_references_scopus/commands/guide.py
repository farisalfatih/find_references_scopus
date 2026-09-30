"""``findref guide`` — show usage guide for the workflow."""

from __future__ import annotations

import typer
from rich.panel import Panel

from find_references_scopus.utils import console, print_header


GUIDE_TEXT = """
[header]Find-Refs Workflow Guide[/header]

Find-Refs is a focused CLI for [bold]finding, validating, filtering, and exporting[/bold]
academic references with Scopus indexing detection.

Search and DOI validation use [bold]OpenAlex only[/bold] (free, no API key - just your email).
Scopus indexing and Q1-Q4 quartiles come from bundled [bold]SCImago[/bold] data (offline).

[header]Quick start[/header]

  [code]findref setup[/code]                          # First-run wizard (interactive)
  [code]findref doctor[/code]                         # Diagnose installation

[header]1. Search for references[/header]

  [code]findref search "deep learning forecasting"[/code]
  [code]findref search "LSTM bitcoin" --year-from 2020 --limit 100[/code]
  [code]findref search "cancer immunotherapy" --quartile Q1,Q2 -o results.json[/code]

  Use [code]--issn 1234-5678,9876-5432[/code] to filter by specific journals.
  Use [code]--issn-filter --subject-areas "Computer Science"[/code] to keep only
  Scopus-indexed journals of a subject area (SCImago).
  Use [code]--openalex-pool[/code] to rotate mailtos if OpenAlex rate-limits you.

[header]2. Validate a list of DOIs[/header]

  [code]findref validate -i dois.txt[/code]                          # One DOI per line
  [code]findref validate -i draft.bib[/code]                        # Extract DOIs from .bib
  [code]findref validate --dois 10.1000/xxx,10.1000/yyy[/code]

  Each paper is enriched with metadata + Scopus-indexed flag.

[header]3. Filter unsuitable references[/header]

  [code]findref filter results.json --min-year 2020 --min-citations 5 --scopus-only[/code]
  [code]findref filter results.json --quartile Q1,Q2 --exclude-keywords preprint,survey[/code]
  [code]findref filter results.json --include-keywords "neural network" --open-access-only[/code]

  Add [code]--dry-run[/code] to preview without saving.

[header]4. Export to BibTeX / RIS / CSV / JSONL[/header]

  [code]findref export results.json --format bibtex -o refs.bib[/code]
  [code]findref export results.filtered.json --format ris -o refs.ris[/code]
  [code]findref export results.json --format csv --annotate-scopus[/code]
  [code]findref export results.json --format bibtex --scopus-only -o scopus_only.bib[/code]

  The .bib output embeds a [code]scopus_indexed = {true|false}[/code] field per entry.

[header]5. Manage accounts (OpenAlex mailtos)[/header]

  An account is just a name + your email for the OpenAlex polite pool.
  Several accounts = several mailtos to rotate through on rate limits.

  [code]findref config add-account --name alice-univ --mailto alice@univ.ac.id[/code]
  [code]findref config use alice-univ[/code]
  [code]findref config list[/code]
  [code]findref config show[/code]                    # Show current account
  [code]findref config remove alice-univ[/code]

[header]6. Agent integration[/header]

  All commands support [code]--json[/code] for structured output:

  [code]findref search "topic" --json[/code]
  [code]findref validate --dois 10.1000/xxx --json[/code]
  [code]findref filter results.json --json[/code]
  [code]findref export results.json --format bibtex --json[/code]

  Exit codes:
    0 = ok          1 = generic error      2 = no results
    3 = rate-limited 4 = auth failed        5 = network error
    6 = config error 130 = interrupted

[header]7. Cache management[/header]

  HTTP responses are cached at [code]~/.findref/cache/[/code] (TTL 24h by default).
  [code]findref cache clear[/code]           # Wipe cache
  [code]findref cache stats[/code]           # Show cache size

[header]Tips[/header]
  - Run [code]findref doctor[/code] if anything breaks.
  - Set [code]FINDREF_CONFIG_DIR[/code] env var to use a portable / project-local config.
  - Set [code]FINDREF_OPENALEX_MAILTO[/code] env var to override the config mailto (useful in CI).
"""


def guide_command() -> None:
    """Show the workflow guide."""
    console.print(GUIDE_TEXT)
