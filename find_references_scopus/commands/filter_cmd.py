"""``findref filter`` — filter out unsuitable references from a JSON file.

Use cases:
  - User has a search result JSON → apply filter rules → output cleaned JSON
  - Filter by year range, citation count, scopus-only, quartile, keywords
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer

from find_references_scopus import EXIT_NO_RESULT, EXIT_OK
from find_references_scopus.config.manager import get_manager
from find_references_scopus.config.project import resolve_defaults
from find_references_scopus.core.deduplication import deduplicate as _deduplicate_papers
from find_references_scopus.core.filter_rules import build_engine_from_cli
from find_references_scopus.core.models import Paper
from find_references_scopus.core.scopus_checker import ScopusChecker
from find_references_scopus.utils import (
    set_json_mode,
    console,
    load_json,
    output_json,
    print_error,
    print_header,
    print_success,
    print_warning,
    save_json,
    setup_logging,
)
from find_references_scopus.utils.paths import (
    is_auto_name_enabled,
    resolve_output_path,
)


def filter_command(
    ctx: typer.Context,
    input_file: Path = typer.Argument(..., help="JSON file with search results (from `findref search --output`)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output JSON file (path or dir)"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Directory to save output files"),
    auto_name: Optional[bool] = typer.Option(None, "--auto-name/--no-auto-name", help="Auto-name output with timestamp"),
    min_year: Optional[int] = typer.Option(None, "--min-year", help="Drop papers before this year"),
    max_year: Optional[int] = typer.Option(None, "--max-year", help="Drop papers after this year"),
    min_citations: Optional[int] = typer.Option(None, "--min-citations", help="Min cited_by_count"),
    scopus_only: bool = typer.Option(False, "--scopus-only", help="Keep only Scopus-indexed papers"),
    quartile: Optional[str] = typer.Option(None, "--quartile", help="Filter: Q1,Q2 / Q1 / all"),
    no_unranked: bool = typer.Option(False, "--no-unranked", help="Drop Scopus journals with quartile '-'"),
    exclude_keywords: Optional[str] = typer.Option(None, "--exclude-keywords", help="Comma-sep blacklist in title/abstract"),
    include_keywords: Optional[str] = typer.Option(None, "--include-keywords", help="Comma-sep whitelist in title/abstract"),
    open_access_only: bool = typer.Option(False, "--open-access-only", help="Keep only OA papers"),
    language: Optional[str] = typer.Option(None, "--language", help="Filter by language code (en, fr, ...)"),
    deduplicate: bool = typer.Option(True, "--deduplicate/--no-deduplicate", help="Remove duplicates (same DOI or fuzzy title)"),
    annotate_scopus: bool = typer.Option(False, "--annotate-scopus", help="Re-annotate Scopus status before filtering (if missing)"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON to stdout (agent-friendly)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Don't save file, just print stats"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Filter out unsuitable references from a JSON file.

    Output location is resolved in this priority:
      1. ``--output path`` (explicit file or dir)
      2. ``--output-dir dir`` (explicit dir)
      3. ``FINDREF_OUTPUT_DIR`` env var
      4. ``output_dir`` from config.toml / .findref.yaml
      5. Same dir as input file

    Use ``--auto-name`` to auto-name with timestamp.
    """
    set_json_mode(json_output)
    setup_logging("DEBUG" if verbose else "WARNING")

    if not input_file.is_file():
        print_error(f"Input file not found: {input_file}")
        raise typer.Exit(1)

    data = load_json(str(input_file))
    papers = _extract_papers(data)
    print_header(
        f"Filtering {len(papers)} papers",
        f"File: {input_file}",
    )

    # Apply project-local config overrides
    mgr = get_manager()
    mgr.load(create_if_missing=True)
    defs = resolve_defaults(mgr)

    # Optional: re-annotate Scopus
    if annotate_scopus or (scopus_only and not any(p.scopus_indexed for p in papers)):
        checker = ScopusChecker(
            scimago_path=defs.scimago_path or None,
        )
        checker.annotate_all(papers)
        console.print("  [muted]Scopus re-annotation complete.[/muted]")

    # Build engine
    engine = build_engine_from_cli(
        min_year=min_year,
        max_year=max_year,
        min_citations=min_citations,
        scopus_only=scopus_only,
        quartile=quartile,
        include_unranked=not no_unranked,
        exclude_keywords=exclude_keywords,
        include_keywords=include_keywords,
        open_access_only=open_access_only,
        language=language,
    )

    if engine.rules:
        console.print("\n[header]Active filter rules:[/header]")
        for r in engine.rules:
            console.print(f"  • {r.name}: {r.to_dict()}")

    kept, removed = engine.apply(papers)

    # Deduplicate
    dedup_count = 0
    if deduplicate and kept:
        before = len(kept)
        kept, dedup_removed = _deduplicate_papers(kept)
        dedup_count = before - len(kept)
        removed.extend(dedup_removed)

    # Output stats
    print_header("Filter results", "")
    console.print(f"  Total input     : {len(papers)}")
    console.print(f"  Kept            : [green]{len(kept)}[/green]")
    console.print(f"  Removed         : [red]{len(removed)}[/red]")
    if dedup_count:
        console.print(f"  Dedup removed   : {dedup_count}")
    console.print(f"  Scopus-indexed  : {sum(1 for p in kept if p.scopus_indexed)} / {len(kept)}")

    # Removed breakdown
    if removed:
        console.print("\n[header]Removed papers:[/header]")
        for p in removed[:10]:
            doi_str = p.doi or "?"
            title_str = (p.title or "")[:60]
            console.print(f"  [red]✗[/red] {doi_str} — {title_str}")
        if len(removed) > 10:
            console.print(f"  [muted]... and {len(removed) - 10} more[/muted]")

    if not kept:
        if json_output:
            output_json({"input": len(papers), "kept": 0, "removed": len(removed), "errors": []})
            raise typer.Exit(EXIT_NO_RESULT)
        print_warning("No papers survived filtering.")
        raise typer.Exit(EXIT_NO_RESULT)

    # Save / output
    if dry_run:
        console.print("\n[muted]--dry-run: no file saved.[/muted]")
    else:
        use_auto_name = is_auto_name_enabled(
            cli_flag=auto_name,
            config_value=defs.auto_name,
        )
        out_path = resolve_output_path(
            explicit_output=output,
            explicit_dir=output_dir,
            config_output_dir=defs.output_dir,
            auto_name_enabled=use_auto_name,
            kind="filter",
            input_path=input_file,
            extension="json",
        )
        save_json({"input_file": str(input_file), "kept": [p.to_dict() for p in kept], "removed": [p.to_dict() for p in removed], "rules": engine.describe()}, out_path)
        print_success(f"Saved {len(kept)} kept papers to [code]{out_path}[/code]")

    if json_output:
        output_json({
            "input": len(papers),
            "kept": len(kept),
            "removed": len(removed),
            "dedup_removed": dedup_count,
            "rules": engine.describe(),
            "kept_papers": [p.to_dict() for p in kept],
        })
        raise typer.Exit(EXIT_OK)


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #

def _extract_papers(data) -> List[Paper]:
    """Extract papers from various JSON shapes."""
    if isinstance(data, list):
        return [Paper.from_dict(p) if isinstance(p, dict) else p for p in data]
    if isinstance(data, dict):
        # {results: [...]} or {group: [...]}
        if "results" in data and isinstance(data["results"], list):
            return [Paper.from_dict(p) if isinstance(p, dict) else p for p in data["results"]]
        if "kept" in data and isinstance(data["kept"], list):
            return [Paper.from_dict(p) if isinstance(p, dict) else p for p in data["kept"]]
        # {group1: [...], group2: [...]}
        out: List[Paper] = []
        for v in data.values():
            if isinstance(v, list):
                out.extend(Paper.from_dict(p) if isinstance(p, dict) else p for p in v)
        return out
    return []
