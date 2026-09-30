"""``findref search`` — search references via OpenAlex (with multi-mailto rotation + ISSN filter).

OpenAlex is the only search source. If the SCImago ISSN filter is on (see
``findref config set-issn-filter`` and ``.findref.yaml``), results are limited to
journals indexed in SCImago/Scopus, optionally by subject area and quartile.

How the ISSN restriction is applied:

  * up to 100 ISSNs (e.g. ``--issn 1234-5678,9876-5432``) -> sent to OpenAlex as
    one ``primary_location.source.issn`` filter (exact, done by OpenAlex);
  * more than 100 ISSNs (a whole subject area) -> OpenAlex is scanned page by
    page and only papers from those journals are kept, until ``--limit`` papers
    are found or ``--max-scan`` works have been scanned.

Examples::

    findref search "deep learning" --limit 50
    findref search "neural networks" --openalex-pool --auto-name -o ./refs/
    findref search "cancer immunotherapy" --year-from 2020 --no-issn-filter
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from rich.table import Table

from find_references_scopus import (
    EXIT_CONFIG_ERROR,
    EXIT_ERROR,
    EXIT_NO_RESULT,
    EXIT_OK,
    EXIT_RATE_LIMITED,
)
from find_references_scopus.api.base import ApiError, RateLimitError
from find_references_scopus.config.manager import get_manager
from find_references_scopus.config.project import resolve_defaults
from find_references_scopus.core.issn_filter import (
    OPENALEX_MAX_OR_VALUES,
    IssnFilter,
    build_filter_from_defaults,
)
from find_references_scopus.core.mailto_pool import MailtoPool
from find_references_scopus.core.models import Paper
from find_references_scopus.core.scimago import split_issns
from find_references_scopus.core.scopus_checker import ScopusChecker
from find_references_scopus.utils import (
    console,
    output_json,
    print_error,
    print_header,
    print_success,
    print_warning,
    save_json,
    set_json_mode,
    setup_logging,
)
from find_references_scopus.utils.paths import (
    is_auto_name_enabled,
    resolve_output_path,
)

DEFAULT_MAX_SCAN = 2000  # works scanned when matching > 100 ISSNs locally
_ISSN_OFF_WORDS = {"none", "off", "false", "-"}


def search_command(
    ctx: typer.Context,
    query: str,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    limit: int = 50,
    per_page: int = 100,
    issn: Optional[str] = None,
    use_issn_filter: Optional[bool] = None,
    subject_areas: Optional[str] = None,
    quartile: Optional[str] = None,
    max_scan: int = DEFAULT_MAX_SCAN,
    annotate_scopus: bool = True,
    output: Optional[str] = None,
    output_dir: Optional[str] = None,
    auto_name: Optional[bool] = None,
    openalex_pool: bool = False,
    openalex_rotate: Optional[bool] = None,
    json_output: bool = False,
    verbose: bool = False,
) -> None:
    """Search for academic references via OpenAlex.

    ISSN restriction rules (highest priority first):

      1. ``--issn LIST``            only these journals (ignores SCImago options)
      2. ``--no-issn-filter``       no restriction
      3. ``--subject-areas`` / ``--quartile`` / ``--issn-filter``  turn the SCImago filter ON
      4. otherwise                  the configured default (``use_issn_filter``)
    """
    set_json_mode(json_output)
    setup_logging("DEBUG" if verbose else "WARNING")

    mgr = get_manager()
    mgr.load(create_if_missing=True)

    # user config < project file (.findref.yaml) < environment; CLI flags applied below
    defs = resolve_defaults(mgr)
    creds = mgr.effective_credentials(defs)

    year_from = year_from or defs.year_from
    year_to = year_to or defs.year_to

    use_auto_name = is_auto_name_enabled(cli_flag=auto_name, config_value=defs.auto_name)

    openalex_auto_rotate = openalex_rotate
    if openalex_auto_rotate is None:
        openalex_auto_rotate = mgr.is_openalex_auto_rotate(defs)

    # Mailto pool (with --openalex-pool or auto-rotate)
    openalex_pool_obj: Optional[MailtoPool] = None
    mailto_pool_list = mgr.get_openalex_mailto_pool(defs)
    if openalex_pool or openalex_auto_rotate:
        if mailto_pool_list:
            openalex_pool_obj = MailtoPool(mailtos=mailto_pool_list, auto_rotate=openalex_auto_rotate)
            console.print(
                f"  [muted]OpenAlex mailto pool: {len(mailto_pool_list)} mailtos, "
                f"auto_rotate={openalex_auto_rotate}[/muted]"
            )

    # ------------------------------------------------------------------ #
    # ISSN restriction
    # ------------------------------------------------------------------ #
    issn_override: Optional[List[str]] = None
    issn_filter_obj: Optional[IssnFilter] = None
    effective_use_issn = defs.use_issn_filter

    if issn is not None and issn.strip().lower() in _ISSN_OFF_WORDS:
        effective_use_issn = False
    elif issn is not None:
        issn_override = split_issns(issn)
        bad = [t for t in (s.strip() for s in issn.split(",")) if t and not split_issns(t)]
        if bad or not issn_override:
            print_error(
                f"Not a valid ISSN: {', '.join(bad) if bad else issn!r}. "
                "Use the form 1234-5678 (comma-separated for several)."
            )
            raise typer.Exit(EXIT_ERROR)
        if use_issn_filter or subject_areas is not None or quartile is not None:
            print_warning("--issn is set: --issn-filter / --subject-areas / --quartile are ignored.")
        effective_use_issn = False
    elif use_issn_filter is not None:
        effective_use_issn = use_issn_filter
    elif subject_areas is not None or quartile is not None:
        effective_use_issn = True  # asking for a subject/quartile implies the filter

    if effective_use_issn:
        try:
            issn_filter_obj = build_filter_from_defaults(
                use_issn_filter=True,
                subject_areas=subject_areas if subject_areas is not None else defs.issn_subject_areas,
                quartiles=quartile if quartile is not None else defs.issn_quartiles,
                include_unranked=defs.issn_include_unranked,
                scimago_path=defs.scimago_path,
            )
        except (FileNotFoundError, ValueError) as e:
            print_error(f"Cannot read the SCImago data: {e}")
            raise typer.Exit(EXIT_CONFIG_ERROR)

        if issn_filter_obj is None:
            print_warning(
                "ISSN filter is enabled but no SCImago JSON was found. "
                "Set one with `findref config set-issn-filter --scimago-path FILE`, "
                "or use --no-issn-filter to search all journals."
            )
        else:
            unknown = issn_filter_obj.stats.get("unmatched_subject_areas") or []
            if unknown:
                print_warning(
                    f"Not an exact SCImago subject area: {', '.join(unknown)} "
                    "(matched by partial name instead). "
                    "`findref config set-issn-filter` lists the valid names."
                )
            if issn_filter_obj.is_empty():
                print_error(
                    "The ISSN filter matches 0 journals (subject area / quartile too restrictive "
                    "or misspelled). Nothing was searched. Use --no-issn-filter to search all journals."
                )
                raise typer.Exit(EXIT_NO_RESULT)

    # Which ISSNs restrict the search, and how (server-side vs local scan)
    restrict: List[str] = list(issn_override or (issn_filter_obj.issns if issn_filter_obj else []))
    if not restrict:
        mode = "none"
    elif len(restrict) <= OPENALEX_MAX_OR_VALUES:
        mode = "server"
    else:
        mode = "scan"

    # Header
    header_subtitle = f"Year: {year_from}–{year_to}  |  Limit: {limit}"
    if issn_filter_obj is not None:
        d = issn_filter_obj.describe()
        sa_str = ", ".join(d["subject_areas"]) if isinstance(d["subject_areas"], list) else d["subject_areas"]
        q_str = ", ".join(d["quartiles"]) if isinstance(d["quartiles"], list) else d["quartiles"]
        header_subtitle += (
            f"\nISSN filter: {d['issn_count']} ISSNs  |  Subjects: {sa_str}  |  Quartiles: {q_str}"
        )
    elif issn_override:
        header_subtitle += f"\nISSN list: {len(issn_override)} ISSNs (--issn)"
    else:
        header_subtitle += "\nISSN filter: off (searching all journals)"
    if mode == "scan":
        header_subtitle += f"\nMatching {len(restrict)} ISSNs locally (max scan: {max_scan or 'unlimited'} works)"

    print_header(f"Searching OpenAlex for: [code]{query}[/code]", header_subtitle)

    # ------------------------------------------------------------------ #
    # Query OpenAlex
    # ------------------------------------------------------------------ #
    all_papers: List[Paper] = []
    errors: List[Dict[str, Any]] = []
    search_stats: Dict[str, Any] = {}
    fatal_exit: Optional[int] = None

    try:
        all_papers, search_stats = _search_openalex(
            query,
            year_from=year_from,
            year_to=year_to,
            limit=limit,
            per_page=per_page,
            creds=creds,
            openalex_pool=openalex_pool_obj,
            restrict=restrict,
            mode=mode,
            max_scan=max_scan,
        )
        console.print(f"  [green]✓[/green] OpenAlex: {len(all_papers)} results")
    except RateLimitError as e:
        errors.append({"source": "openalex", "error": "rate_limited", "message": str(e)})
        console.print(f"  [yellow]![/yellow] OpenAlex: rate-limited — {e}")
        fatal_exit = EXIT_RATE_LIMITED
    except ApiError as e:
        errors.append({"source": "openalex", "error": type(e).__name__, "message": str(e)})
        console.print(f"  [red]✗[/red] OpenAlex: {e}")
        fatal_exit = e.exit_code
    except Exception as e:  # noqa: BLE001 - report anything else as a generic error
        errors.append({"source": "openalex", "error": "other", "message": str(e)})
        console.print(f"  [red]✗[/red] OpenAlex: {e}")
        fatal_exit = EXIT_ERROR

    if fatal_exit is not None and not all_papers:
        if json_output:
            output_json({"query": query, "results": [], "errors": errors, "count": 0})
        elif fatal_exit == EXIT_RATE_LIMITED:
            print_error("Rate-limited and no results. Try --openalex-pool to rotate mailtos.")
        raise typer.Exit(fatal_exit)

    if mode == "scan":
        console.print(
            f"  [muted]Scanned {search_stats.get('scanned', 0)} works, "
            f"kept {search_stats.get('matched', 0)} from SCImago journals[/muted]"
        )
        if search_stats.get("scan_capped") and len(all_papers) < limit:
            print_warning(
                f"Stopped after scanning {max_scan} works and found only {len(all_papers)} of {limit} "
                "papers. Raise --max-scan, loosen --subject-areas / --quartile, "
                "or use --no-issn-filter."
            )

    # Annotate with Scopus info
    if annotate_scopus and all_papers:
        console.print("\n[header]Annotating Scopus indexing...[/header]")
        checker = ScopusChecker(scimago_path=defs.scimago_path or None)
        stats = checker.annotate_all(all_papers)
        console.print(
            f"  Total: {stats['total']}  |  Scopus-indexed: {stats['scopus']}  "
            f"|  Non-Scopus: {stats['non_scopus']}  |  With quartile: {stats['with_quartile']}"
        )

    if limit and len(all_papers) > limit:
        all_papers = all_papers[:limit]

    if not all_papers:
        if json_output:
            output_json({"query": query, "results": [], "errors": errors, "count": 0})
            raise typer.Exit(EXIT_NO_RESULT)
        print_warning("No results found.")
        raise typer.Exit(EXIT_NO_RESULT)

    # Save / output
    saved_path: Optional[Path] = None
    if output or use_auto_name:
        out_path = resolve_output_path(
            explicit_output=output,
            explicit_dir=output_dir,
            config_output_dir=defs.output_dir,
            auto_name_enabled=use_auto_name,
            kind="search",
            query=query,
            extension="json",
        )
        save_json(
            {"query": query, "results": [p.to_dict() for p in all_papers], "errors": errors},
            out_path,
        )
        saved_path = out_path
        print_success(f"Saved {len(all_papers)} results to [code]{out_path}[/code]")

    if json_output:
        result: Dict[str, Any] = {
            "query": query,
            "results": [p.to_dict() for p in all_papers],
            "errors": errors,
            "count": len(all_papers),
            "saved_to": str(saved_path) if saved_path else None,
            "issn_filter": issn_filter_obj.describe() if issn_filter_obj else None,
            "issn_search": {
                "mode": mode,  # none | server (exact, by OpenAlex) | scan (matched locally)
                "issn_count": len(restrict),
                **search_stats,
            },
        }
        if openalex_pool_obj:
            result["openalex_pool_stats"] = openalex_pool_obj.stats()
        output_json(result)
        raise typer.Exit(EXIT_OK)

    _print_results_table(all_papers)

    if openalex_pool_obj:
        console.print("\n[header]OpenAlex mailto pool stats:[/header]")
        for mailto, stats in openalex_pool_obj.stats().items():
            console.print(
                f"  {mailto}: {stats['request_count']} requests"
                + (f" (cooldown: {stats['cooldown_remaining']:.1f}s)" if stats["in_cooldown"] else "")
            )


# ---------------------------------------------------------------------- #
# Helper: search OpenAlex (server-side ISSN filter or local scan)
# ---------------------------------------------------------------------- #

def _search_openalex(
    query: str,
    *,
    year_from: Optional[int],
    year_to: Optional[int],
    limit: int,
    per_page: int,
    creds: dict,
    openalex_pool: Optional[MailtoPool],
    restrict: List[str],
    mode: str,
    max_scan: int,
) -> tuple[List[Paper], Dict[str, Any]]:
    """Search OpenAlex. Returns ``(papers, stats)``.

    ``mode``: ``none`` (no ISSN restriction), ``server`` (<= 100 ISSNs, filtered by
    OpenAlex) or ``scan`` (> 100 ISSNs, matched locally page by page).
    """
    from find_references_scopus.api.openalex import OpenAlexClient

    if openalex_pool is not None and not openalex_pool.is_empty():
        c = OpenAlexClient(mailto_pool=openalex_pool, rate_limit_delay=0.5)
    else:
        c = OpenAlexClient(mailto=creds.get("openalex_mailto"), rate_limit_delay=0.5)

    kwargs: Dict[str, Any] = {}
    page_size = min(per_page, 200)
    if mode == "server":
        kwargs["issn_filter"] = restrict
    elif mode == "scan":
        wanted = frozenset(restrict)
        kwargs["accept"] = lambda p: any(i in wanted for i in p.issns)
        kwargs["max_scan"] = max_scan
        page_size = 200  # fewest requests while scanning

    papers = c.search(
        query,
        year_from=year_from,
        year_to=year_to,
        per_page=page_size,
        max_results=limit,
        **kwargs,
    )
    return papers, dict(c.last_search_stats)


def _print_results_table(papers: List[Paper]) -> None:
    table = Table(title=f"Search results ({len(papers)} papers)", border_style="blue", show_lines=False)
    table.add_column("#", style="muted", width=4)
    table.add_column("Year", width=6)
    table.add_column("Scopus", width=8)
    table.add_column("Title", overflow="fold")
    table.add_column("First author", width=20)
    table.add_column("Cites", width=6, justify="right")

    for i, p in enumerate(papers, 1):
        scopus_flag = "[green]Y[/green]" if p.scopus_indexed else "[red]N[/red]"
        if p.scopus_indexed and p.quartile:
            scopus_flag += f" [muted]{p.quartile}[/muted]"
        table.add_row(
            str(i),
            str(p.year or "?"),
            scopus_flag,
            (p.title or "(no title)")[:120],
            p.short_authors[:20],
            str(p.cited_by_count),
        )
    console.print(table)
