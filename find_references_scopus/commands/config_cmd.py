"""``findref config`` — accounts (OpenAlex mailtos) and defaults.

An "account" holds one OpenAlex polite-pool mailto. Register several accounts
to rotate between mailtos when OpenAlex rate-limits you. No API keys are used.

Subcommands::

    findref config list                       Show all accounts + current
    findref config add-account                Add a new account (interactive)
    findref config use <name>                 Switch to account <name>
    findref config remove <name>              Delete account <name>
    findref config show [<name>]              Show details of an account
    findref config set-default <key> <value>  Update a default value
    findref config path                       Print the config file path
    findref config edit                       Open config in $EDITOR
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

import questionary
import typer
from rich.table import Table

from find_references_scopus import EXIT_ERROR, EXIT_OK
from find_references_scopus.config.defaults import DEFAULT_OPENALEX_MAILTO
from find_references_scopus.config.manager import (
    Account,
    AccountNotFoundError,
    ConfigManager,
    ConfigNotFoundError,
    get_manager,
)
from find_references_scopus.utils import (
    set_json_mode,
    console,
    err_console,
    output_json,
    print_error,
    print_header,
    print_success,
    print_table,
    print_warning,
    setup_logging,
)


config_app = typer.Typer(
    name="config",
    help="Manage accounts (OpenAlex mailtos) and defaults.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


# ---------------------------------------------------------------------- #
# findref config list
# ---------------------------------------------------------------------- #

@config_app.command("list")
def config_list(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON (agent-friendly)"),
) -> None:
    """List all accounts and highlight the current one."""
    set_json_mode(json_output)
    setup_logging("WARNING")
    mgr = get_manager()
    try:
        mgr.load(create_if_missing=False)
    except ConfigNotFoundError:
        if json_output:
            output_json({"accounts": [], "current": None, "error": "no config"})
            raise typer.Exit(EXIT_ERROR)
        print_error("No config found. Run `findref setup` first.")
        raise typer.Exit(EXIT_ERROR)

    accounts = mgr.list_accounts()
    current = mgr.get_current_account()
    current_name = current.name if current else None

    if json_output:
        output_json({
            "accounts": [a.to_dict() for a in accounts],
            "current": current_name,
            "config_path": str(mgr.path),
        })
        raise typer.Exit(EXIT_OK)

    print_header("Configured accounts", str(mgr.path))

    rows = []
    for a in accounts:
        marker = "[green]→[/green]" if a.name == current_name else " "
        mailto = a.openalex_mailto if a.openalex_mailto and a.openalex_mailto != DEFAULT_OPENALEX_MAILTO else "(placeholder)"
        rows.append([marker, a.name, a.label or "(no label)", mailto])
    print_table(
        "Accounts",
        ["", "Name", "Label", "OpenAlex mailto"],
        rows,
    )

    defs = mgr.get_defaults()
    console.print(f"\n[header]Current defaults:[/header]")
    console.print(f"  openalex_mailto : {defs.openalex_mailto}")
    console.print(f"  year_from → year_to : {defs.year_from} – {defs.year_to}")
    console.print(f"  language        : {defs.language}")
    console.print(f"  per_page        : {defs.per_page}")
    console.print(f"  request_delay   : {defs.request_delay}s")
    console.print(f"  cache           : {'enabled' if defs.cache_enabled else 'disabled'} (ttl {defs.cache_ttl}s)")
    if defs.scimago_path:
        console.print(f"  scimago_path    : {defs.scimago_path}")


# ---------------------------------------------------------------------- #
# findref config add-account
# ---------------------------------------------------------------------- #

@config_app.command("add-account")
def config_add_account(
    name: str = typer.Option(..., "--name", "-n", help="Account name (unique identifier)"),
    label: Optional[str] = typer.Option(None, "--label", "-l", help="Human-friendly label"),
    openalex_mailto: Optional[str] = typer.Option(None, "--openalex-mailto", "--mailto", help="Email for the OpenAlex polite pool"),
    make_current: bool = typer.Option(True, "--make-current/--no-make-current", help="Switch to this account after adding"),
    non_interactive: bool = typer.Option(False, "--non-interactive", "-y", help="Skip prompts; require all flags"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Add a new account."""
    set_json_mode(json_output)
    setup_logging("WARNING")
    mgr = get_manager()
    mgr.load(create_if_missing=True)

    # If not all flags given and interactive allowed, prompt for missing
    if not non_interactive and not openalex_mailto:
        label = label or questionary.text("Account label:", default=name).ask()
        openalex_mailto = questionary.text(
            "OpenAlex mailto (Enter for default):",
            default=mgr.get_defaults().openalex_mailto,
        ).ask() or openalex_mailto

    acc = Account(
        name=name,
        label=label or name,
        openalex_mailto=openalex_mailto or DEFAULT_OPENALEX_MAILTO,
    )
    mgr.add_account(acc)
    if make_current:
        mgr.use_account(name)
    mgr.save()

    if json_output:
        output_json({"action": "added", "account": acc.to_dict(), "current": name})
        raise typer.Exit(EXIT_OK)

    print_success(f"Account '{name}' added" + (f" and set as current." if make_current else "."))


# ---------------------------------------------------------------------- #
# findref config use
# ---------------------------------------------------------------------- #

@config_app.command("use")
def config_use(
    name: str = typer.Argument(..., help="Account name to switch to"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Switch the current account."""
    set_json_mode(json_output)
    setup_logging("WARNING")
    mgr = get_manager()
    mgr.load(create_if_missing=False)
    try:
        acc = mgr.use_account(name)
    except AccountNotFoundError:
        if json_output:
            output_json({"error": "account_not_found", "name": name})
            raise typer.Exit(EXIT_ERROR)
        print_error(f"Account not found: {name}")
        raise typer.Exit(EXIT_ERROR)
    mgr.save()

    if json_output:
        output_json({"action": "switched", "current": name, "account": acc.to_dict()})
        raise typer.Exit(EXIT_OK)

    print_success(f"Switched to account '{name}'")


# ---------------------------------------------------------------------- #
# findref config remove
# ---------------------------------------------------------------------- #

@config_app.command("remove")
def config_remove(
    name: str = typer.Argument(..., help="Account name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Remove an account."""
    set_json_mode(json_output)
    setup_logging("WARNING")
    mgr = get_manager()
    mgr.load(create_if_missing=False)

    if not force and not json_output:
        ok = questionary.confirm(f"Remove account '{name}'?").ask()
        if not ok:
            print_warning("Cancelled.")
            raise typer.Exit(EXIT_OK)

    removed = mgr.remove_account(name)
    if not removed:
        if json_output:
            output_json({"error": "account_not_found", "name": name})
            raise typer.Exit(EXIT_ERROR)
        print_error(f"Account not found: {name}")
        raise typer.Exit(EXIT_ERROR)

    mgr.save()

    if json_output:
        output_json({"action": "removed", "name": name, "remaining": [a.name for a in mgr.list_accounts()]})
        raise typer.Exit(EXIT_OK)

    print_success(f"Removed account '{name}'.")


# ---------------------------------------------------------------------- #
# findref config show
# ---------------------------------------------------------------------- #

@config_app.command("show")
def config_show(
    name: Optional[str] = typer.Argument(None, help="Account name (default: current)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show details of an account (or current if no name given)."""
    set_json_mode(json_output)
    setup_logging("WARNING")
    mgr = get_manager()
    mgr.load(create_if_missing=False)

    if name is None:
        acc = mgr.get_current_account()
        if acc is None:
            print_error("No current account. Run `findref config use <name>` first.")
            raise typer.Exit(EXIT_ERROR)
    else:
        try:
            acc = mgr.get_account(name)
        except AccountNotFoundError:
            print_error(f"Account not found: {name}")
            raise typer.Exit(EXIT_ERROR)

    if json_output:
        output_json(acc.to_dict())
        raise typer.Exit(EXIT_OK)

    print_header(f"Account: {acc.name}", acc.label or "")
    console.print(f"  openalex_mailto : {acc.openalex_mailto}")


# ---------------------------------------------------------------------- #
# findref config set-default
# ---------------------------------------------------------------------- #

@config_app.command("set-default")
def config_set_default(
    key: str = typer.Argument(..., help="Default key (e.g. year_from, openalex_mailto)"),
    value: str = typer.Argument(..., help="New value (string, will be coerced)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Update a single default value."""
    set_json_mode(json_output)
    setup_logging("WARNING")
    mgr = get_manager()
    mgr.load(create_if_missing=True)

    defs = mgr.get_defaults()
    if not hasattr(defs, key):
        print_error(f"Unknown default key: {key}\nValid: {', '.join(defs.__dataclass_fields__.keys())}")
        raise typer.Exit(EXIT_ERROR)

    # Coerce value type
    current = getattr(defs, key)
    try:
        if isinstance(current, bool):
            new_val = value.lower() in {"true", "1", "yes", "y"}
        elif isinstance(current, int):
            new_val = int(value)
        elif isinstance(current, float):
            new_val = float(value)
        else:
            new_val = value
    except ValueError:
        print_error(f"Cannot convert '{value}' to {type(current).__name__}")
        raise typer.Exit(EXIT_ERROR)

    mgr.update_defaults(**{key: new_val})
    mgr.save()

    if json_output:
        output_json({"action": "updated", "key": key, "value": new_val})
        raise typer.Exit(EXIT_OK)

    print_success(f"Set {key} = {new_val!r}")


# ---------------------------------------------------------------------- #
# findref config path
# ---------------------------------------------------------------------- #

@config_app.command("path")
def config_path(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Print the path to the config file."""
    mgr = get_manager()
    if json_output:
        output_json({"config_path": str(mgr.path)})
        raise typer.Exit(EXIT_OK)
    console.print(str(mgr.path))


# ---------------------------------------------------------------------- #
# findref config edit
# ---------------------------------------------------------------------- #

@config_app.command("edit")
def config_edit() -> None:
    """Open the config file in $EDITOR."""
    mgr = get_manager()
    path = mgr.path
    if not path.is_file():
        mgr.load(create_if_missing=True)
        mgr.save()

    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "nano"
    try:
        subprocess.run([editor, str(path)], check=True)
    except FileNotFoundError:
        print_error(f"Editor not found: {editor}. Set $EDITOR or $VISUAL.")
        raise typer.Exit(EXIT_ERROR)
    except subprocess.CalledProcessError as e:
        print_error(f"Editor exited with code {e.returncode}")
        raise typer.Exit(EXIT_ERROR)


# ---------------------------------------------------------------------- #
# findref config show-pool
# ---------------------------------------------------------------------- #

@config_app.command("show-pool")
def config_show_pool(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show the OpenAlex mailto pool (all mailtos collected for rotation).

    This shows what mailtos will be used when you run
    ``findref search --openalex-pool``. Sources:
      1. Current account's openalex_mailto
      2. All other accounts' openalex_mailto
      3. Defaults.openalex_mailto_pool (extra mailtos)
      4. Defaults.openalex_mailto
      5. FINDREF_OPENALEX_MAILTO_POOL env var
      6. FINDREF_OPENALEX_MAILTO env var

    Empty mailtos and the default placeholder ``researcher@example.com``
    are skipped (they don't help with rate limits).
    """
    set_json_mode(json_output)
    setup_logging("WARNING")
    mgr = get_manager()
    mgr.load(create_if_missing=True)

    pool = mgr.get_openalex_mailto_pool()
    auto_rotate = mgr.is_openalex_auto_rotate()

    if json_output:
        output_json({
            "pool": pool,
            "count": len(pool),
            "auto_rotate": auto_rotate,
            "config_path": str(mgr.path),
        })
        raise typer.Exit(EXIT_OK)

    print_header("OpenAlex mailto pool", "Mailtos collected for rotation")
    if not pool:
        console.print("  [yellow]Pool is empty[/yellow]. Add accounts with `findref config add-account`")
        console.print("  or set `FINDREF_OPENALEX_MAILTO_POOL` env var.")
        return

    rows = []
    for i, mailto in enumerate(pool, 1):
        rows.append([str(i), mailto])
    print_table("Mailto pool", ["#", "Email"], rows)

    console.print(f"\n  Auto-rotate: {'enabled' if auto_rotate else 'disabled'}")
    console.print(f"  Total mailtos: {len(pool)}")
    console.print(f"\n  [muted]Use: findref search \"query\" --openalex-pool[/muted]")


# ---------------------------------------------------------------------- #
# findref config add-mailto
# ---------------------------------------------------------------------- #

@config_app.command("add-mailto")
def config_add_mailto(
    mailto: str = typer.Argument(..., help="Email address to add to the pool"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Add an extra OpenAlex mailto to the rotation pool.

    This stores the mailto in ``defaults.openalex_mailto_pool`` (comma-separated).
    You don't need to create a fake account for it.

    Example::

        findref config add-mailto bob@univ.edu
        findref config add-mailto carol@gmail.com

    Then verify with::

        findref config show-pool
    """
    set_json_mode(json_output)
    setup_logging("WARNING")
    mgr = get_manager()
    mgr.load(create_if_missing=True)

    mailto = mailto.strip().lower()
    if "@" not in mailto:
        print_error(f"Invalid email: {mailto}")
        raise typer.Exit(EXIT_ERROR)

    defs = mgr.get_defaults()
    existing = defs.openalex_mailto_pool or ""
    existing_list = [m.strip() for m in existing.split(",") if m.strip()]

    if mailto in existing_list:
        print_warning(f"{mailto} is already in the pool.")
        if json_output:
            output_json({"action": "noop", "mailto": mailto, "already_present": True})
            raise typer.Exit(EXIT_OK)
        return

    existing_list.append(mailto)
    new_pool = ",".join(existing_list)
    mgr.update_defaults(openalex_mailto_pool=new_pool)
    mgr.save()

    if json_output:
        output_json({
            "action": "added",
            "mailto": mailto,
            "pool": existing_list,
            "count": len(existing_list),
        })
        raise typer.Exit(EXIT_OK)

    print_success(f"Added {mailto} to the OpenAlex mailto pool.")
    console.print(f"  Pool now has {len(existing_list)} mailtos.")
    console.print(f"  [muted]Verify with: findref config show-pool[/muted]")


# ---------------------------------------------------------------------- #
# findref config remove-mailto
# ---------------------------------------------------------------------- #

@config_app.command("remove-mailto")
def config_remove_mailto(
    mailto: str = typer.Argument(..., help="Email address to remove from the pool"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Remove a mailto from the OpenAlex rotation pool."""
    set_json_mode(json_output)
    setup_logging("WARNING")
    mgr = get_manager()
    mgr.load(create_if_missing=True)

    mailto = mailto.strip().lower()
    defs = mgr.get_defaults()
    existing = defs.openalex_mailto_pool or ""
    existing_list = [m.strip() for m in existing.split(",") if m.strip()]

    if mailto not in existing_list:
        print_warning(f"{mailto} is not in the pool.")
        if json_output:
            output_json({"action": "noop", "mailto": mailto, "not_present": True})
            raise typer.Exit(EXIT_OK)
        return

    existing_list.remove(mailto)
    new_pool = ",".join(existing_list)
    mgr.update_defaults(openalex_mailto_pool=new_pool)
    mgr.save()

    if json_output:
        output_json({
            "action": "removed",
            "mailto": mailto,
            "pool": existing_list,
            "count": len(existing_list),
        })
        raise typer.Exit(EXIT_OK)

    print_success(f"Removed {mailto} from the OpenAlex mailto pool.")


# ---------------------------------------------------------------------- #
# findref config set-issn-filter
# ---------------------------------------------------------------------- #

@config_app.command("set-issn-filter")
def config_set_issn_filter(
    enable: Optional[bool] = typer.Option(
        None, "--enable/--disable",
        help="Enable or disable the ISSN filter (skip interactive prompt)",
    ),
    subject_areas: Optional[str] = typer.Option(
        None, "--subject-areas",
        help="Comma-separated subject areas (e.g. 'Computer Science,Medicine'). Empty = all.",
    ),
    quartiles: Optional[str] = typer.Option(
        None, "--quartiles",
        help="Comma-separated quartiles (e.g. 'Q1,Q2'). 'all' or empty = all.",
    ),
    include_unranked: Optional[bool] = typer.Option(
        None, "--include-unranked/--no-unranked",
        help="Include Scopus journals with quartile '-' (unranked)",
    ),
    scimago_path: Optional[str] = typer.Option(
        None, "--scimago-path",
        help="Path to SCImago JSON file (overrides existing config)",
    ),
    non_interactive: bool = typer.Option(
        False, "--non-interactive", "-y",
        help="Skip prompts; use flags / defaults only",
    ),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Configure the SCImago ISSN filter for OpenAlex search.

    When enabled, ``findref search`` will restrict results to journals indexed
    in SCImago (filtered by subject area + quartile).

    Interactive mode (default) will:

      1. Ask whether to enable the ISSN filter
      2. Show available subject areas in your SCImago JSON (multi-select)
      3. Ask which quartiles to include (Q1, Q2, Q3, Q4, all)
      4. Ask whether to include unranked Scopus journals (quartile '-')
      5. Save the config and show a preview of the resolved ISSN list

    Example non-interactive::

        findref config set-issn-filter \\
            --enable \\
            --subject-areas "Computer Science,Mathematics" \\
            --quartiles "Q1,Q2" \\
            --non-interactive
    """
    set_json_mode(json_output)
    setup_logging("WARNING")
    mgr = get_manager()
    mgr.load(create_if_missing=True)
    defs = mgr.get_defaults()

    # Resolve SCImago path (use existing or override)
    effective_scimago = scimago_path or defs.scimago_path
    if not effective_scimago:
        # Try bundled
        from find_references_scopus.config.defaults import get_data_dir
        bundled = get_data_dir() / "scimagojr_2025.json"
        if bundled.is_file():
            effective_scimago = str(bundled)

    if non_interactive:
        # Use flag values directly
        final_enable = enable if enable is not None else defs.use_issn_filter
        final_sa = subject_areas if subject_areas is not None else defs.issn_subject_areas
        final_q = quartiles if quartiles is not None else defs.issn_quartiles
        final_unranked = include_unranked if include_unranked is not None else defs.issn_include_unranked
    else:
        # Interactive flow
        print_header("SCImago ISSN Filter Configuration")

        if not effective_scimago:
            console.print(
                "[yellow]![/yellow] No SCImago JSON found. Please provide the path "
                "to your scimagojr.json file:"
            )
            console.print("  You can download it from https://scimagojr.com/")
            path_input = questionary.path("Path to SCImago JSON:").ask()
            if path_input and Path(path_input).is_file():
                effective_scimago = path_input
            else:
                print_error("No valid SCImago JSON path provided. Aborting.")
                raise typer.Exit(EXIT_ERROR)
        else:
            console.print(f"  [muted]SCImago JSON: {effective_scimago}[/muted]")

        # 1. Enable / disable
        if enable is None:
            final_enable = questionary.confirm(
                "Enable SCImago ISSN filter for OpenAlex search?",
                default=defs.use_issn_filter,
            ).ask()
        else:
            final_enable = enable

        if not final_enable:
            mgr.update_defaults(
                use_issn_filter=False,
                scimago_path=effective_scimago,
            )
            mgr.save()
            print_success("ISSN filter disabled. Search will query all journals.")
            if json_output:
                output_json({"action": "disabled"})
                raise typer.Exit(EXIT_OK)
            return

        # 2. Subject areas (multi-select from available)
        from find_references_scopus.core.issn_filter import list_subject_areas
        available_areas = list_subject_areas(effective_scimago)
        if available_areas:
            console.print(f"\n  [muted]Found {len(available_areas)} subject areas in SCImago JSON[/muted]")
            if subject_areas is None:
                # Multi-select (limit display to first 30 for readability)
                choices = ["(all subject areas)"] + available_areas[:30]
                if len(available_areas) > 30:
                    console.print(f"  [muted](showing first 30 of {len(available_areas)})[/muted]")
                selected = questionary.checkbox(
                    "Select subject areas (Space to toggle, Enter to confirm):",
                    choices=choices,
                ).ask()
                if selected and "(all subject areas)" not in selected:
                    final_sa = ",".join(selected)
                else:
                    final_sa = ""
            else:
                final_sa = subject_areas
        else:
            console.print("  [yellow]![/yellow] No subject areas found in SCImago JSON.")
            final_sa = subject_areas or ""

        # 3. Quartiles
        if quartiles is None:
            q_choices = ["Q1", "Q2", "Q3", "Q4", "- (unranked)"]
            selected_q = questionary.checkbox(
                "Select quartiles to include:",
                choices=q_choices,
                default=["Q1", "Q2", "Q3", "Q4", "- (unranked)"],
            ).ask()
            # Normalize
            normalized = []
            for q in selected_q:
                q_clean = q.split(" ")[0].strip().upper()
                if q_clean == "-":
                    normalized.append("-")
                else:
                    normalized.append(q_clean)
            final_q = ",".join(normalized) if normalized else ""
        else:
            final_q = quartiles

        # 4. Include unranked
        if include_unranked is None:
            final_unranked = questionary.confirm(
                "Include Scopus journals with quartile '-' (unranked)?",
                default=defs.issn_include_unranked,
            ).ask()
        else:
            final_unranked = include_unranked

    # Save
    mgr.update_defaults(
        use_issn_filter=final_enable,
        issn_subject_areas=final_sa,
        issn_quartiles=final_q,
        issn_include_unranked=final_unranked,
        scimago_path=effective_scimago,
    )
    mgr.save()

    # Build the filter to show preview
    if final_enable:
        from find_references_scopus.core.issn_filter import build_filter_from_defaults
        f = build_filter_from_defaults(
            use_issn_filter=True,
            subject_areas=final_sa,
            quartiles=final_q,
            include_unranked=final_unranked,
            scimago_path=effective_scimago,
        )
        if f:
            d = f.describe()
            sa_str = ", ".join(d["subject_areas"]) if isinstance(d["subject_areas"], list) else d["subject_areas"]
            q_str = ", ".join(d["quartiles"]) if isinstance(d["quartiles"], list) else d["quartiles"]
            print_success(f"ISSN filter enabled — {d['issn_count']} ISSNs resolved")
            console.print(f"  Subject areas: {sa_str}")
            console.print(f"  Quartiles:     {q_str}")
            console.print(f"  Unranked:      {'included' if final_unranked else 'excluded'}")
            console.print(f"  SCImago JSON:  {effective_scimago}")
            console.print(f"  [muted]Stats: {d['stats']}[/muted]")
            if json_output:
                output_json({
                    "action": "enabled",
                    "filter": d,
                    "scimago_path": effective_scimago,
                })
        else:
            print_warning("ISSN filter enabled but no ISSNs resolved (check SCImago JSON).")
            if json_output:
                output_json({"action": "enabled_empty", "scimago_path": effective_scimago})
    else:
        print_success("ISSN filter disabled.")
        if json_output:
            output_json({"action": "disabled"})


# ---------------------------------------------------------------------- #
# findref config show-issn-filter
# ---------------------------------------------------------------------- #

@config_app.command("show-issn-filter")
def config_show_issn_filter(
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show the current SCImago ISSN filter configuration + resolved ISSN count."""
    set_json_mode(json_output)
    setup_logging("WARNING")
    mgr = get_manager()
    mgr.load(create_if_missing=True)
    defs = mgr.get_defaults()

    # Build filter to show resolved count
    resolved_count = 0
    filter_desc = None
    if defs.use_issn_filter:
        from find_references_scopus.core.issn_filter import build_filter_from_defaults
        f = build_filter_from_defaults(
            use_issn_filter=True,
            subject_areas=defs.issn_subject_areas,
            quartiles=defs.issn_quartiles,
            include_unranked=defs.issn_include_unranked,
            scimago_path=defs.scimago_path,
        )
        if f:
            resolved_count = len(f.issns)
            filter_desc = f.describe()

    if json_output:
        output_json({
            "use_issn_filter": defs.use_issn_filter,
            "subject_areas": defs.issn_subject_areas,
            "quartiles": defs.issn_quartiles,
            "include_unranked": defs.issn_include_unranked,
            "scimago_path": defs.scimago_path,
            "resolved_issn_count": resolved_count,
            "filter_stats": filter_desc.get("stats") if filter_desc else None,
        })
        raise typer.Exit(EXIT_OK)

    print_header("SCImago ISSN Filter Configuration")
    console.print(f"  Enabled:          {'[green]yes[/green]' if defs.use_issn_filter else '[red]no[/red]'}")
    console.print(f"  Subject areas:    {defs.issn_subject_areas or '(all)'}")
    console.print(f"  Quartiles:        {defs.issn_quartiles or '(all)'}")
    console.print(f"  Include unranked: {'yes' if defs.issn_include_unranked else 'no'}")
    console.print(f"  SCImago JSON:     {defs.scimago_path or '(bundled default)'}")
    if defs.use_issn_filter:
        console.print(f"\n  [green]Resolved: {resolved_count} ISSNs[/green]")
        if filter_desc:
            console.print(f"  [muted]Stats: {filter_desc['stats']}[/muted]")
    console.print(f"\n  [muted]Edit: findref config set-issn-filter[/muted]")
