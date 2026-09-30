"""``findref issn`` — look up journals by ISSN in the bundled SCImago data.

Answers "is this journal indexed in Scopus, and in which quartile?" offline.
Print and electronic ISSNs both work, with or without the hyphen.

Examples::

    findref issn 0007-9235
    findref issn 15424863 1471-0080 --json
"""

from __future__ import annotations

from typing import Any, Dict, List

import typer

from find_references_scopus import EXIT_CONFIG_ERROR, EXIT_ERROR, EXIT_NO_RESULT, EXIT_OK
from find_references_scopus.config.manager import get_manager
from find_references_scopus.config.project import resolve_defaults
from find_references_scopus.core.scimago import normalize_issn
from find_references_scopus.core.scopus_checker import ScopusChecker
from find_references_scopus.utils import (
    console,
    output_json,
    print_error,
    print_header,
    print_warning,
    set_json_mode,
    setup_logging,
)


def issn_command(
    ctx: typer.Context,
    issns: List[str],
    json_output: bool = False,
    verbose: bool = False,
) -> None:
    """Look up one or more ISSNs in the SCImago data (offline)."""
    set_json_mode(json_output)
    setup_logging("DEBUG" if verbose else "WARNING")

    bad = [t for t in issns if not normalize_issn(t)]
    if bad:
        print_error(f"Not a valid ISSN: {', '.join(bad)}. Use the form 1234-5678.")
        raise typer.Exit(EXIT_ERROR)

    mgr = get_manager()
    mgr.load(create_if_missing=True)
    defs = resolve_defaults(mgr)

    checker = ScopusChecker(scimago_path=defs.scimago_path or None)
    if not checker.scimago_path:
        print_error("No SCImago data found. Set one with `findref config set-issn-filter --scimago-path FILE`.")
        raise typer.Exit(EXIT_CONFIG_ERROR)

    results: List[Dict[str, Any]] = []
    for raw in issns:
        n = normalize_issn(raw)
        j = checker.lookup_issn(n)
        item: Dict[str, Any] = {"issn": n, "found": j is not None, "scopus_indexed": j is not None}
        if j is not None:
            item.update(j.to_dict())
        results.append(item)

    found = sum(1 for r in results if r["found"])

    if json_output:
        output_json({"count": len(results), "found": found, "results": results})
        raise typer.Exit(EXIT_OK if found else EXIT_NO_RESULT)

    print_header("SCImago ISSN lookup", f"Data: {checker.scimago_path}")
    for r in results:
        if r["found"]:
            console.print(f"[green]✓[/green] [bold]{r['issn']}[/bold]  {r['journal']}")
            console.print(f"    Scopus-indexed: yes   Quartile: {r['quartile'] or '?'}   Open access: {r['open_access'] or '?'}")
            console.print(f"    ISSNs: {', '.join(r['issns'])}")
            console.print(f"    Subject areas: {', '.join(r['subject_areas']) or '?'}")
        else:
            console.print(f"[red]✗[/red] [bold]{r['issn']}[/bold]  not in the SCImago data (treated as not Scopus-indexed)")
    if not found:
        print_warning("None of the ISSNs were found.")
        raise typer.Exit(EXIT_NO_RESULT)
