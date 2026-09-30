"""``findref cache`` — manage the HTTP response cache."""

from __future__ import annotations

import typer
from rich.panel import Panel

from find_references_scopus.utils import (
    console,
    output_json,
    print_header,
    print_success,
    print_warning,
    set_json_mode,
    setup_logging,
)
from find_references_scopus.utils.cache import clear_cache, get_session


cache_app = typer.Typer(
    name="cache",
    help="Manage the HTTP response cache.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@cache_app.command("clear")
def cache_clear(
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Clear the HTTP cache."""
    set_json_mode(json_output)
    setup_logging("WARNING")
    count = clear_cache()
    if json_output:
        output_json({"action": "cleared", "entries_removed": count})
        raise typer.Exit(0)
    print_success(f"Cleared {count} cached responses.")


@cache_app.command("stats")
def cache_stats(
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show cache statistics."""
    set_json_mode(json_output)
    setup_logging("WARNING")
    s = get_session()
    try:
        count = len(s.cache.responses)  # type: ignore[attr-defined]
    except Exception:
        count = 0

    cache_path = s.cache.db_path if hasattr(s.cache, "db_path") else "unknown"  # type: ignore[attr-defined]

    if json_output:
        output_json({"entries": count, "path": str(cache_path)})
        raise typer.Exit(0)

    print_header("Cache stats")
    console.print(f"  Entries: {count}")
    console.print(f"  Path:    {cache_path}")
