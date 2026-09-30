"""``findref setup`` — interactive first-run wizard.

Walks the user through:
  1. Default mailto for the OpenAlex polite pool (the only online API used)
  2. Adding their first account (an account = a mailto; several accounts
     give several mailtos to rotate through when OpenAlex rate-limits)
  3. Path to SCImago JSON (default: bundled) + Scopus/quartile ISSN filter
  4. Cache & logging preferences
  5. Verifies OpenAlex connectivity

Idempotent — safe to re-run anytime.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import questionary
import typer
from rich.panel import Panel
from rich.table import Table

from find_references_scopus import __version__
from find_references_scopus.config.defaults import (
    DEFAULT_LANGUAGE,
    DEFAULT_OPENALEX_MAILTO,
    DEFAULT_PER_PAGE,
    DEFAULT_REQUEST_DELAY,
    DEFAULT_YEAR_FROM,
    DEFAULT_YEAR_TO,
    get_config_path,
)
from find_references_scopus.config.manager import Account, ConfigManager, get_manager
from find_references_scopus.utils import (
    console,
    err_console,
    print_header,
    print_success,
    print_warning,
    setup_logging,
)


def setup_command(
    ctx: typer.Context,
    non_interactive: bool = typer.Option(
        False, "--non-interactive", "-y", help="Skip prompts; use defaults / env vars only"
    ),
) -> None:
    """Run the interactive setup wizard."""
    setup_logging("INFO")
    config_path = get_config_path()

    print_header(
        f"Welcome to findref v{__version__}",
        f"Config will be stored at: [code]{config_path}[/code]",
    )
    console.print(
        Panel.fit(
            "This wizard will:\n"
            "  1. Set your OpenAlex mailto (polite pool)\n"
            "  2. Add your first account (optional, extra mailto for rotation)\n"
            "  3. Configure the SCImago Scopus/quartile filter\n"
            "  4. Verify OpenAlex connectivity\n\n"
            "[muted]No API key is needed: search uses OpenAlex only, and Scopus "
            "indexing is detected offline from bundled SCImago data.[/muted]\n\n"
            "[muted]You can re-run this anytime — it's idempotent.[/muted]",
            border_style="blue",
        )
    )

    if non_interactive:
        _run_non_interactive(ctx)
        return

    _run_interactive(ctx)


# ---------------------------------------------------------------------- #
# Interactive flow
# ---------------------------------------------------------------------- #

def _run_interactive(ctx: typer.Context) -> None:
    mgr = get_manager()
    try:
        mgr.load(create_if_missing=True)
    except Exception as e:
        print_warning(f"Could not load existing config: {e}")

    # Step 1: defaults
    console.print("\n[header]Step 1: Defaults[/header]")
    mailto = questionary.text(
        "Your email for the OpenAlex polite pool:",
        default=mgr.get_defaults().openalex_mailto or DEFAULT_OPENALEX_MAILTO,
    ).ask()
    if not mailto:
        mailto = DEFAULT_OPENALEX_MAILTO

    year_from = int(questionary.text(
        "Default year-from for searches:",
        default=str(mgr.get_defaults().year_from or DEFAULT_YEAR_FROM),
    ).ask() or DEFAULT_YEAR_FROM)
    year_to = int(questionary.text(
        "Default year-to for searches:",
        default=str(mgr.get_defaults().year_to or DEFAULT_YEAR_TO),
    ).ask() or DEFAULT_YEAR_TO)

    mgr.update_defaults(
        openalex_mailto=mailto,
        year_from=year_from,
        year_to=year_to,
        language=DEFAULT_LANGUAGE,
        per_page=DEFAULT_PER_PAGE,
        request_delay=DEFAULT_REQUEST_DELAY,
        cache_enabled=True,
        cache_ttl=86400,
        log_level="INFO",
    )

    # Step 2: first account
    console.print("\n[header]Step 2: Add your first account[/header]")
    add_account = questionary.confirm(
        "Add an account now? (you can do this later with `findref config add-account`)",
        default=True,
    ).ask()

    if add_account:
        account_name = questionary.text("Account name (e.g. alice-univ):").ask()
        if account_name:
            label = questionary.text("Account label (e.g. 'Alice @ Univ'):", default=account_name).ask()
            openalex_mailto = questionary.text(
                "OpenAlex mailto (Enter to use default):",
                default=mailto,
            ).ask()

            acc = Account(
                name=account_name,
                label=label or account_name,
                openalex_mailto=openalex_mailto or mailto,
            )
            mgr.add_account(acc)
            mgr.use_account(account_name)
            print_success(f"Account '{account_name}' added and selected as current.")

    # Step 3: SCImago data file + ISSN filter
    console.print("\n[header]Step 3: SCImago journal data + ISSN filter[/header]")
    scimago_path = questionary.path(
        "Path to SCImago JSON (Enter to use bundled default):",
        default=mgr.get_defaults().scimago_path or "",
        only_directories=False,
    ).ask()
    if scimago_path:
        if not Path(scimago_path).is_file():
            print_warning(f"File not found: {scimago_path} — will use bundled data.")
            scimago_path = ""
        mgr.update_defaults(scimago_path=scimago_path)

    # SCImago path for ISSN filter (use resolved path)
    effective_scimago = scimago_path or str(_bundled_scimago_path())

    # 3a. Enable ISSN filter?
    use_issn_filter = questionary.confirm(
        "Enable SCImago ISSN filter? (restricts search to Scopus-indexed journals)",
        default=True,
    ).ask()
    mgr.update_defaults(use_issn_filter=use_issn_filter)

    if use_issn_filter and effective_scimago and Path(effective_scimago).is_file():
        # 3b. Subject areas
        from find_references_scopus.core.issn_filter import list_subject_areas
        available_areas = list_subject_areas(effective_scimago)
        if available_areas:
            console.print(f"\n  [muted]Found {len(available_areas)} subject areas in SCImago JSON[/muted]")
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
            console.print("  [yellow]![/yellow] No subject areas found in SCImago JSON.")
            final_sa = ""
        mgr.update_defaults(issn_subject_areas=final_sa)

        # 3c. Quartiles
        _q_default = {"Q1", "Q2", "Q3", "Q4"}
        q_choices = [
            questionary.Choice(v, checked=(v in _q_default))
            for v in ["Q1", "Q2", "Q3", "Q4", "- (unranked)"]
        ]
        selected_q = questionary.checkbox(
            "Select quartiles to include:",
            choices=q_choices,
        ).ask()
        normalized = []
        for q in selected_q:
            q_clean = q.split(" ")[0].strip().upper()
            if q_clean == "-":
                normalized.append("-")
            else:
                normalized.append(q_clean)
        final_q = ",".join(normalized) if normalized else ""
        mgr.update_defaults(issn_quartiles=final_q)

        # 3d. Include unranked
        include_unranked = questionary.confirm(
            "Include Scopus journals with quartile '-' (unranked)?",
            default=True,
        ).ask()
        mgr.update_defaults(issn_include_unranked=include_unranked)

        # Preview the resolved ISSN count
        from find_references_scopus.core.issn_filter import build_filter_from_defaults
        f = build_filter_from_defaults(
            use_issn_filter=True,
            subject_areas=final_sa,
            quartiles=final_q,
            include_unranked=include_unranked,
            scimago_path=effective_scimago,
        )
        if f:
            console.print(f"\n  [green]ISSN filter resolved: {len(f.issns)} unique ISSNs[/green]")
            console.print(f"  [muted]Stats: {f.stats}[/muted]")
    elif use_issn_filter and not effective_scimago:
        print_warning(
            "ISSN filter enabled but no SCImago JSON available. "
            "Run `findref config set-issn-filter` after downloading SCImago data."
        )

    # Step 4: Save
    console.print("\n[header]Step 4: Saving config[/header]")
    mgr.save()
    print_success(f"Config saved to {mgr.path}")

    # Step 5: Connectivity check
    console.print("\n[header]Step 5: Connectivity check[/header]")
    _check_connectivity(mgr)

    console.print("\n[success]✓ Setup complete![/success]")
    console.print(f"Next steps:\n  [code]findref search 'machine learning finance'[/code]\n  [code]findref config list[/code]\n  [code]findref config show-issn-filter[/code]\n  [code]findref --help[/code]")


def _bundled_scimago_path() -> Path:
    """Return path to the bundled SCImago JSON, or empty Path if not available."""
    from find_references_scopus.config.defaults import get_data_dir
    return get_data_dir() / "scimagojr_2025.json"


# ---------------------------------------------------------------------- #
# Non-interactive flow
# ---------------------------------------------------------------------- #

def _run_non_interactive(ctx: typer.Context) -> None:
    import os

    mgr = get_manager()
    mgr.load(create_if_missing=True)

    mailto = os.environ.get("FINDREF_OPENALEX_MAILTO", DEFAULT_OPENALEX_MAILTO)
    mgr.update_defaults(
        openalex_mailto=mailto,
        cache_enabled=True,
    )

    # Auto-add a "default" account from env if a real mailto was provided
    if mailto and mailto != DEFAULT_OPENALEX_MAILTO:
        acc = Account(
            name="default",
            label="Default (from env)",
            openalex_mailto=mailto,
        )
        mgr.add_account(acc)
        mgr.use_account("default")
        print_success("Account 'default' added from FINDREF_OPENALEX_MAILTO.")
    else:
        print_warning(
            "FINDREF_OPENALEX_MAILTO not set - using the placeholder mailto. "
            "Set it to your own email for a reliable OpenAlex polite pool."
        )

    mgr.save()
    print_success(f"Config saved to {mgr.path}")


# ---------------------------------------------------------------------- #
# Connectivity check
# ---------------------------------------------------------------------- #

def _check_connectivity(mgr: ConfigManager) -> None:
    creds = mgr.effective_credentials()

    table = Table(title="Connectivity check", border_style="blue")
    table.add_column("Service")
    table.add_column("Status")
    table.add_column("Note")

    # OpenAlex
    try:
        from find_references_scopus.api.openalex import OpenAlexClient
        c = OpenAlexClient(mailto=creds["openalex_mailto"])
        c.request("GET", "/works/https://doi.org/10.1038/nature12373")
        table.add_row("OpenAlex", "[green]OK[/green]", f"mailto={creds['openalex_mailto']}")
    except Exception as e:
        table.add_row("OpenAlex", "[red]FAIL[/red]", str(e)[:80])

    console.print(table)
