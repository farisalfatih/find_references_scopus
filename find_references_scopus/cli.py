"""Main CLI entry point for findref.

Built with Typer + Rich for a Vercel-CLI-style experience:
  - Beautiful colored output
  - Subcommand groups
  - --json flag on every command (agent-friendly)
  - Deterministic exit codes
  - Auto-generated --help
"""

from __future__ import annotations

import sys
from typing import Optional

import typer
from rich.panel import Panel

from find_references_scopus import __version__
from find_references_scopus.commands.config_cmd import config_app
from find_references_scopus.commands.cache_cmd import cache_app
from find_references_scopus.utils import console, setup_logging


# ---------------------------------------------------------------------- #
# Root app
# ---------------------------------------------------------------------- #

app = typer.Typer(
    name="findref",
    help=(
        "[bold]Find-Refs[/bold] — Professional CLI for finding, validating, "
        "filtering, and exporting academic references with Scopus indexing detection.\n\n"
        "Quick start:\n"
        "  [code]findref setup[/code]\n"
        "  [code]findref search 'machine learning finance'[/code]\n"
        "  [code]findref export results.json --format bibtex -o refs.bib[/code]"
    ),
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)


# Register sub-app groups
app.add_typer(config_app, name="config", help="Manage accounts (OpenAlex mailtos) and defaults.")
app.add_typer(cache_app, name="cache", help="Manage the HTTP response cache.")


# ---------------------------------------------------------------------- #
# Global options
# ---------------------------------------------------------------------- #

@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose (DEBUG) logging"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress non-error output"),
    version: bool = typer.Option(False, "--version", "-V", help="Show version and exit"),
) -> None:
    """Configure global state."""
    if version:
        console.print(f"findref v{__version__}")
        raise typer.Exit(0)

    if verbose:
        setup_logging("DEBUG")
    elif quiet:
        setup_logging("ERROR")
    else:
        setup_logging("INFO")

    # If no subcommand given, show help (but only after handling --version)
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)


# ---------------------------------------------------------------------- #
# Top-level commands
# ---------------------------------------------------------------------- #

@app.command()
def setup(
    ctx: typer.Context,
    non_interactive: bool = typer.Option(
        False, "--non-interactive", "-y",
        help="Skip prompts; use defaults / env vars only",
    ),
) -> None:
    """Run the interactive setup wizard."""
    from find_references_scopus.commands.setup import setup_command
    setup_command(ctx, non_interactive=non_interactive)


@app.command()
def search(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Search query (e.g. 'deep learning forecasting')"),
    year_from: Optional[int] = typer.Option(None, "--year-from", help="Filter: minimum publication year"),
    year_to: Optional[int] = typer.Option(None, "--year-to", help="Filter: maximum publication year"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max results to return"),
    per_page: int = typer.Option(100, "--per-page", help="Page size for API requests"),
    issn: Optional[str] = typer.Option(
        None, "--issn",
        help="Override ISSN filter (comma-separated). Pass 'none' to disable ISSN filter for this search.",
    ),
    use_issn_filter: Optional[bool] = typer.Option(
        None, "--issn-filter/--no-issn-filter",
        help="Enable/disable SCImago ISSN filter (overrides config default)",
    ),
    subject_areas: Optional[str] = typer.Option(
        None, "--subject-areas",
        help="Override subject areas filter (comma-separated, e.g. 'Computer Science,Medicine')",
    ),
    quartile: Optional[str] = typer.Option(
        None, "--quartile",
        help="Override quartile filter (e.g. 'Q1,Q2' or 'all')",
    ),
    max_scan: int = typer.Option(
        2000, "--max-scan",
        help="When the ISSN filter has >100 ISSNs, how many OpenAlex works to scan locally before giving up (0 = unlimited)",
    ),
    annotate_scopus: bool = typer.Option(True, "--annotate-scopus/--no-annotate-scopus", help="Annotate Scopus indexing"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Save JSON results to file (path or dir)"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Directory to save output files"),
    auto_name: Optional[bool] = typer.Option(None, "--auto-name/--no-auto-name", help="Auto-name output with timestamp"),
    openalex_pool: bool = typer.Option(False, "--openalex-pool", help="Use ALL OpenAlex mailtos as rotation pool"),
    openalex_rotate: Optional[bool] = typer.Option(None, "--openalex-rotate/--no-openalex-rotate", help="Rotate mailto per request"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON to stdout (agent-friendly)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
) -> None:
    """Search for academic references via OpenAlex (with optional SCImago ISSN filter)."""
    from find_references_scopus.commands.search import search_command
    search_command(
        ctx,
        query=query,
        year_from=year_from,
        year_to=year_to,
        limit=limit,
        per_page=per_page,
        issn=issn,
        use_issn_filter=use_issn_filter,
        subject_areas=subject_areas,
        quartile=quartile,
        max_scan=max_scan,
        annotate_scopus=annotate_scopus,
        output=output,
        output_dir=output_dir,
        auto_name=auto_name,
        openalex_pool=openalex_pool,
        openalex_rotate=openalex_rotate,
        json_output=json_output,
        verbose=verbose,
    )


@app.command()
def validate(
    ctx: typer.Context,
    input_file: Optional[str] = typer.Option(
        None, "--input", "-i",
        help="File with DOIs (.txt with one DOI per line, or .bib BibTeX). Markdown NOT supported.",
    ),
    dois: Optional[str] = typer.Option(None, "--dois", help="Comma-separated list of DOIs"),
    annotate_scopus: bool = typer.Option(True, "--annotate-scopus/--no-annotate-scopus"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Save JSON results to file (path or dir)"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Directory to save output files"),
    auto_name: Optional[bool] = typer.Option(None, "--auto-name/--no-auto-name", help="Auto-name output with timestamp"),
    json_output: bool = typer.Option(False, "--json"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Validate a list of DOIs — check Scopus indexing and enrich metadata via OpenAlex."""
    from find_references_scopus.commands.validate import validate_command
    from pathlib import Path
    validate_command(
        ctx,
        input_file=Path(input_file) if input_file else None,
        dois=dois,
        annotate_scopus=annotate_scopus,
        output=output,
        output_dir=output_dir,
        auto_name=auto_name,
        json_output=json_output,
        verbose=verbose,
    )


@app.command(name="filter")
def filter_cmd(
    ctx: typer.Context,
    input_file: str = typer.Argument(..., help="JSON file with search results"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output JSON file (path or dir)"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Directory to save output files"),
    auto_name: Optional[bool] = typer.Option(None, "--auto-name/--no-auto-name", help="Auto-name output with timestamp"),
    min_year: Optional[int] = typer.Option(None, "--min-year"),
    max_year: Optional[int] = typer.Option(None, "--max-year"),
    min_citations: Optional[int] = typer.Option(None, "--min-citations"),
    scopus_only: bool = typer.Option(False, "--scopus-only"),
    quartile: Optional[str] = typer.Option(None, "--quartile", help="Q1,Q2 / Q1 / all"),
    no_unranked: bool = typer.Option(False, "--no-unranked"),
    exclude_keywords: Optional[str] = typer.Option(None, "--exclude-keywords"),
    include_keywords: Optional[str] = typer.Option(None, "--include-keywords"),
    open_access_only: bool = typer.Option(False, "--open-access-only"),
    language: Optional[str] = typer.Option(None, "--language"),
    deduplicate: bool = typer.Option(True, "--deduplicate/--no-deduplicate"),
    annotate_scopus: bool = typer.Option(False, "--annotate-scopus"),
    json_output: bool = typer.Option(False, "--json"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Filter out unsuitable references from a JSON file."""
    from find_references_scopus.commands.filter_cmd import filter_command
    from pathlib import Path
    filter_command(
        ctx,
        input_file=Path(input_file),
        output=output,
        output_dir=output_dir,
        auto_name=auto_name,
        min_year=min_year,
        max_year=max_year,
        min_citations=min_citations,
        scopus_only=scopus_only,
        quartile=quartile,
        no_unranked=no_unranked,
        exclude_keywords=exclude_keywords,
        include_keywords=include_keywords,
        open_access_only=open_access_only,
        language=language,
        deduplicate=deduplicate,
        annotate_scopus=annotate_scopus,
        json_output=json_output,
        dry_run=dry_run,
        verbose=verbose,
    )


@app.command()
def export(
    ctx: typer.Context,
    input_file: str = typer.Argument(..., help="JSON file with papers"),
    format: str = typer.Option("bibtex", "--format", "-f", help="bibtex, ris, csv, jsonl, md"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file (path or dir)"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Directory to save output files"),
    auto_name: Optional[bool] = typer.Option(None, "--auto-name/--no-auto-name", help="Auto-name output with timestamp"),
    annotate_scopus: bool = typer.Option(False, "--annotate-scopus"),
    scopus_only: bool = typer.Option(False, "--scopus-only"),
    json_output: bool = typer.Option(False, "--json"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Export papers to BibTeX/RIS/CSV/JSONL/Markdown."""
    from find_references_scopus.commands.export_cmd import export_command
    from pathlib import Path
    export_command(
        ctx,
        input_file=Path(input_file),
        format=format,
        output=output,
        output_dir=output_dir,
        auto_name=auto_name,
        annotate_scopus=annotate_scopus,
        scopus_only=scopus_only,
        json_output=json_output,
        verbose=verbose,
    )


@app.command()
def issn(
    ctx: typer.Context,
    issns: list[str] = typer.Argument(..., help="One or more ISSNs, e.g. 0007-9235"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Look up ISSNs in the bundled SCImago data (Scopus indexing + quartile), offline."""
    from find_references_scopus.commands.issn_cmd import issn_command
    issn_command(ctx, issns=issns, json_output=json_output, verbose=verbose)


@app.command()
def uninstall(
    ctx: typer.Context,
    yes: bool = typer.Option(False, "--yes", "-y", help="Don't ask for confirmation"),
    purge: bool = typer.Option(False, "--purge", help="Also delete config, accounts, cache, and logs"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be removed, change nothing"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Remove findref (installed via install.sh / install.ps1) from this computer."""
    from find_references_scopus.commands.uninstall import uninstall_command
    uninstall_command(ctx, yes=yes, purge=purge, dry_run=dry_run, json_output=json_output)


@app.command()
def doctor(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Diagnose installation, config, and API connectivity."""
    from find_references_scopus.commands.doctor import doctor_command
    doctor_command(ctx, json_output=json_output, verbose=verbose)


@app.command()
def guide() -> None:
    """Show the workflow guide."""
    from find_references_scopus.commands.guide import guide_command
    guide_command()


@app.command()
def version() -> None:
    """Print the version."""
    console.print(f"findref v{__version__}")


# ---------------------------------------------------------------------- #
# Entry point
# ---------------------------------------------------------------------- #

if __name__ == "__main__":
    app()
