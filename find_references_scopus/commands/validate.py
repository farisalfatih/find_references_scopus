"""``findref validate`` — validate and enrich a list of DOIs.

Use cases:
  - User has a list of DOIs (one per line in a .txt file) → verify Scopus indexing
  - User has a .bib file → extract DOIs via bibtexparser, verify each

**Markdown files are NOT supported.** This tool is focused on reference
discovery, not on parsing drafts.

Example .txt input::

    10.1038/nature12373
    10.1000/abc123
    # Comments are ignored

Example .bib input::

    @article{smith2024,
      doi = {10.1000/xyz},
      title = {...},
      ...
    }
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer
from rich.table import Table

from find_references_scopus import EXIT_NO_RESULT, EXIT_OK
from find_references_scopus.api.base import NotFoundError
from find_references_scopus.config.manager import get_manager
from find_references_scopus.config.project import resolve_defaults
from find_references_scopus.core.models import Paper, extract_dois
from find_references_scopus.core.scopus_checker import ScopusChecker
from find_references_scopus.utils import (
    set_json_mode,
    console,
    load_lines,
    load_text,
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


def validate_command(
    ctx: typer.Context,
    input_file: Optional[Path] = typer.Option(
        None, "--input", "-i",
        help="File with DOIs (.txt with one DOI per line, or .bib BibTeX). Markdown is NOT supported.",
    ),
    dois: Optional[str] = typer.Option(
        None, "--dois",
        help="Comma-separated list of DOIs (alternative to --input)",
    ),
    annotate_scopus: bool = typer.Option(True, "--annotate-scopus/--no-annotate-scopus"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Save JSON results to file (path or dir)"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Directory to save output files"),
    auto_name: Optional[bool] = typer.Option(None, "--auto-name/--no-auto-name", help="Auto-name output with timestamp"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON to stdout"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Validate a list of DOIs — check Scopus indexing and enrich metadata via OpenAlex.

    OpenAlex is the only API source used for enrichment (consistent with ``findref search``).
    """
    set_json_mode(json_output)
    setup_logging("DEBUG" if verbose else "WARNING")

    mgr = get_manager()
    mgr.load(create_if_missing=True)
    defs = resolve_defaults(mgr)
    creds = mgr.effective_credentials(defs)

    # Collect DOIs
    doi_list: List[str] = []
    if input_file:
        if not input_file.is_file():
            print_error(f"File not found: {input_file}")
            raise typer.Exit(1)

        suffix = input_file.suffix.lower()
        if suffix == ".md":
            print_error(
                "Markdown files are not supported. Use a .txt file with one DOI per line, "
                "or a .bib BibTeX file. (Markdown extraction was removed per user request.)"
            )
            raise typer.Exit(1)
        elif suffix == ".bib":
            # Parse BibTeX properly with bibtexparser
            doi_list = _extract_dois_from_bib(input_file)
        elif suffix in {".txt", ".csv", ".tsv", ""}:
            # Plain text: one DOI per line (or extract via regex if mixed text)
            text = load_text(input_file)
            doi_list = extract_dois(text)
            if not doi_list:
                # Fall back to line-by-line
                doi_list = load_lines(str(input_file))
        else:
            # Try regex extraction for any other text file
            text = load_text(input_file)
            doi_list = extract_dois(text)
    elif dois:
        doi_list = [d.strip() for d in dois.split(",") if d.strip()]
    else:
        print_error("Provide --input <file.txt|file.bib> or --dois doi1,doi2,...")
        raise typer.Exit(1)

    if not doi_list:
        print_warning("No DOIs found in input.")
        raise typer.Exit(EXIT_NO_RESULT)

    print_header(
        f"Validating {len(doi_list)} DOIs",
        f"Source: OpenAlex  |  Scopus annotation: {'on' if annotate_scopus else 'off'}",
    )

    # Enrich each DOI via OpenAlex
    enriched: List[Paper] = []
    errors: List[dict] = []
    for doi in doi_list:
        paper = _fetch_one_from_openalex(doi, creds=creds)
        if paper is None:
            errors.append({"doi": doi, "error": "not_found"})
            console.print(f"  [red]✗[/red] {doi} — not found")
            continue
        enriched.append(paper)
        console.print(f"  [green]✓[/green] {doi} — {paper.title[:80]}")

    # Scopus annotation
    if annotate_scopus and enriched:
        console.print("\n[header]Annotating Scopus indexing...[/header]")
        checker = ScopusChecker(
            scimago_path=defs.scimago_path or None,
        )
        stats = checker.annotate_all(enriched)
        console.print(f"  Scopus: {stats['scopus']} / {stats['total']}  |  Non-Scopus: {stats['non_scopus']}")

    # Output
    if output or auto_name is not None or defs.output_dir:
        use_auto_name = is_auto_name_enabled(
            cli_flag=auto_name,
            config_value=defs.auto_name,
        )
        out_path = resolve_output_path(
            explicit_output=output,
            explicit_dir=output_dir,
            config_output_dir=defs.output_dir,
            auto_name_enabled=use_auto_name,
            kind="validate",
            extension="json",
        )
        save_json({"results": [p.to_dict() for p in enriched], "errors": errors}, out_path)
        print_success(f"Saved {len(enriched)} results to [code]{out_path}[/code]")

    if json_output:
        output_json({
            "input_count": len(doi_list),
            "found": len(enriched),
            "scopus_count": sum(1 for p in enriched if p.scopus_indexed),
            "results": [p.to_dict() for p in enriched],
            "errors": errors,
        })
        raise typer.Exit(EXIT_OK)

    # Render table
    _print_validation_table(enriched, errors)


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #

def _extract_dois_from_bib(bib_path: Path) -> List[str]:
    """Extract DOIs from a BibTeX file using bibtexparser (API v2, ``bibtexparser>=2.0.0b7``)."""
    try:
        import bibtexparser

        library = bibtexparser.parse_file(str(bib_path))

        dois: List[str] = []
        seen: set[str] = set()
        for entry in library.entries:
            doi = ""
            for f in entry.fields:
                if f.key.lower() == "doi" and f.value.strip():
                    doi = f.value.strip()
                    break
            if doi and doi.lower() not in seen:
                seen.add(doi.lower())
                dois.append(doi)
        return dois
    except ImportError:
        # bibtexparser not installed — fall back to regex
        return extract_dois(_read_bib_text_lenient(bib_path))
    except Exception:
        # Parse error (e.g. bad encoding, malformed BibTeX) — fall back to regex.
        # Read leniently here: a strict UTF-8 read (load_text) would raise the very
        # same decode error we're trying to recover from.
        return extract_dois(_read_bib_text_lenient(bib_path))


def _read_bib_text_lenient(bib_path: Path) -> str:
    """Read a .bib file as text, replacing undecodable bytes instead of raising."""
    return bib_path.read_text(encoding="utf-8", errors="replace")


def _fetch_one_from_openalex(doi: str, *, creds: dict) -> Optional[Paper]:
    """Fetch a single paper by DOI via OpenAlex."""
    doi = doi.strip()
    if not doi.startswith("10."):
        return None

    from find_references_scopus.api.openalex import OpenAlexClient
    c = OpenAlexClient(mailto=creds.get("openalex_mailto"))
    try:
        return c.fetch_by_doi(doi)
    except NotFoundError:
        return None
    except Exception:
        return None


def _print_validation_table(papers: List[Paper], errors: List[dict]) -> None:
    table = Table(title=f"Validation results ({len(papers)} found)", border_style="blue", show_lines=False)
    table.add_column("#", style="muted", width=4)
    table.add_column("DOI", width=40, overflow="fold")
    table.add_column("Scopus", width=8)
    table.add_column("Year", width=6)
    table.add_column("Title", overflow="fold")

    for i, p in enumerate(papers, 1):
        scopus_flag = "[green]✓[/green]" if p.scopus_indexed else "[red]✗[/red]"
        if p.quartile:
            scopus_flag += f" [muted]{p.quartile}[/muted]"
        table.add_row(
            str(i),
            p.doi or "",
            scopus_flag,
            str(p.year or "?"),
            p.title or "(no title)",
        )

    if errors:
        for e in errors:
            table.add_row("?", e["doi"], "[red]ERR[/red]", "?", e.get("error", "unknown"))

    console.print(table)
    scopus_count = sum(1 for p in papers if p.scopus_indexed)
    console.print(
        f"\n[header]Summary:[/header]  Found: {len(papers)}  "
        f"|  Scopus: {scopus_count}  |  Non-Scopus: {len(papers) - scopus_count}  "
        f"|  Errors: {len(errors)}"
    )
