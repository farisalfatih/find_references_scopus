"""``findref export`` — export papers to BibTeX/RIS/CSV/JSONL/Markdown.

Supports flexible output location:
  - ``--output path`` (explicit file or dir)
  - ``--output-dir dir`` (explicit dir, auto-name inside)
  - ``--auto-name`` for timestamp-based naming
  - ``FINDREF_OUTPUT_DIR`` env var
  - ``output_dir`` from config.toml / .findref.yaml
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer

from find_references_scopus import EXIT_OK
from find_references_scopus.config.manager import get_manager
from find_references_scopus.config.project import resolve_defaults
from find_references_scopus.core.models import Paper, ReferenceList
from find_references_scopus.core.scopus_checker import ScopusChecker
from find_references_scopus.exporters import get_exporter
from find_references_scopus.utils import (
    set_json_mode,
    console,
    load_json,
    output_json,
    print_error,
    print_header,
    print_success,
    setup_logging,
)
from find_references_scopus.utils.paths import (
    is_auto_name_enabled,
    resolve_output_path,
)


def export_command(
    ctx: typer.Context,
    input_file: Path = typer.Argument(..., help="JSON file with papers (from `findref search` or `findref filter`)"),
    format: str = typer.Option(
        "bibtex", "--format", "-f",
        help="Output format: bibtex, ris, csv, jsonl, md",
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="Output file (path or dir). Default: <input>.<ext>",
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir",
        help="Directory to save output files (overrides config + env var)",
    ),
    auto_name: Optional[bool] = typer.Option(
        None, "--auto-name/--no-auto-name",
        help="Auto-name output file with timestamp (e.g. export_input_bibtex_20260927_120000.bib)",
    ),
    annotate_scopus: bool = typer.Option(
        False, "--annotate-scopus",
        help="Re-annotate Scopus status before exporting (if missing)",
    ),
    scopus_only: bool = typer.Option(
        False, "--scopus-only",
        help="Only export Scopus-indexed papers",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output JSON summary (agent-friendly)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Export a JSON file of papers to BibTeX/RIS/CSV/JSONL/Markdown."""
    set_json_mode(json_output)
    setup_logging("DEBUG" if verbose else "WARNING")

    if not input_file.is_file():
        print_error(f"Input file not found: {input_file}")
        raise typer.Exit(1)

    data = load_json(str(input_file))
    papers = _extract_papers(data)

    if not papers:
        print_error("No papers found in input file.")
        raise typer.Exit(1)

    print_header(f"Exporting {len(papers)} papers to {format.upper()}", str(input_file))

    # Apply project-local config overrides
    mgr = get_manager()
    mgr.load(create_if_missing=True)
    defs = resolve_defaults(mgr)

    # Optional Scopus re-annotation
    if annotate_scopus:
        checker = ScopusChecker(
            scimago_path=defs.scimago_path or None,
        )
        stats = checker.annotate_all(papers)
        console.print(f"  [muted]Scopus re-annotation: {stats['scopus']} / {stats['total']} indexed[/muted]")

    if scopus_only:
        before = len(papers)
        papers = [p for p in papers if p.scopus_indexed]
        console.print(f"  [muted]--scopus-only: {before} → {len(papers)}[/muted]")

    # Resolve output path
    exporter = get_exporter(format)
    use_auto_name = is_auto_name_enabled(
        cli_flag=auto_name,
        config_value=defs.auto_name,
    )
    out_path = resolve_output_path(
        explicit_output=output,
        explicit_dir=output_dir,
        config_output_dir=defs.output_dir,
        auto_name_enabled=use_auto_name,
        kind="export",
        input_path=input_file,
        format=format,
        extension=exporter.file_extension,
    )

    # Export
    ref_list = ReferenceList(groups={"default": papers})
    exporter.export_to_file(ref_list, out_path)

    # Stats
    scopus_count = sum(1 for p in papers if p.scopus_indexed)
    print_success(f"Exported {len(papers)} papers to [code]{out_path}[/code]")
    console.print(f"  Scopus-indexed: {scopus_count} / {len(papers)}")
    console.print(f"  Format: {format}")
    console.print(f"  Size: {out_path.stat().st_size} bytes")

    if json_output:
        output_json({
            "input": str(input_file),
            "output": str(out_path),
            "format": format,
            "papers": len(papers),
            "scopus_indexed": scopus_count,
            "file_size_bytes": out_path.stat().st_size,
        })
        raise typer.Exit(EXIT_OK)


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #

def _extract_papers(data) -> List[Paper]:
    if isinstance(data, list):
        return [Paper.from_dict(p) if isinstance(p, dict) else p for p in data]
    if isinstance(data, dict):
        if "results" in data and isinstance(data["results"], list):
            return [Paper.from_dict(p) if isinstance(p, dict) else p for p in data["results"]]
        if "kept" in data and isinstance(data["kept"], list):
            return [Paper.from_dict(p) if isinstance(p, dict) else p for p in data["kept"]]
        out: List[Paper] = []
        for v in data.values():
            if isinstance(v, list):
                out.extend(Paper.from_dict(p) if isinstance(p, dict) else p for p in v)
        return out
    return []
