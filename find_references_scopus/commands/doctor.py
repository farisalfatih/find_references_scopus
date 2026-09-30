"""``findref doctor`` — check installation, config, and OpenAlex connectivity."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer
from rich.panel import Panel
from rich.table import Table

from find_references_scopus import __version__
from find_references_scopus.config.defaults import (
    DEFAULT_OPENALEX_MAILTO,
    get_cache_dir,
    get_config_path,
    get_data_dir,
    get_logs_dir,
    get_user_data_dir,
)
from find_references_scopus.config.manager import ConfigNotFoundError, get_manager
from find_references_scopus.utils import (
    set_json_mode,
    console,
    output_json,
    print_header,
    print_success,
    print_warning,
    print_error,
    setup_logging,
)


def doctor_command(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Diagnose installation: Python version, paths, config, OpenAlex connectivity."""
    set_json_mode(json_output)
    setup_logging("DEBUG" if verbose else "WARNING")

    checks: list[dict] = []

    # 1) Python version
    py_version = sys.version.split()[0]
    py_ok = sys.version_info >= (3, 10)
    checks.append({
        "name": "Python version",
        "status": "ok" if py_ok else "fail",
        "detail": py_version + (" (>=3.10 required)" if not py_ok else ""),
    })

    # 2) findref version
    checks.append({
        "name": "findref version",
        "status": "ok",
        "detail": __version__,
    })

    # 3) Config file
    cfg_path = get_config_path()
    cfg_exists = cfg_path.is_file()
    checks.append({
        "name": "Config file",
        "status": "ok" if cfg_exists else "warn",
        "detail": str(cfg_path) + (" (run `findref setup`)" if not cfg_exists else ""),
    })

    # 4) Config loads OK
    try:
        mgr = get_manager()
        mgr.load(create_if_missing=False)
        accounts = mgr.list_accounts()
        current = mgr.get_current_account()
        checks.append({
            "name": "Config valid",
            "status": "ok",
            "detail": f"{len(accounts)} accounts, current={current.name if current else 'none'}",
        })
    except ConfigNotFoundError:
        checks.append({"name": "Config valid", "status": "warn", "detail": "no config"})
    except Exception as e:
        checks.append({"name": "Config valid", "status": "fail", "detail": str(e)[:80]})

    # 5) Directories writable
    for name, p in [
        ("Cache dir", get_cache_dir()),
        ("Logs dir", get_logs_dir()),
        ("User data dir", get_user_data_dir()),
    ]:
        try:
            test_file = p / ".write_test"
            test_file.write_text("ok")
            test_file.unlink()
            checks.append({"name": name + " writable", "status": "ok", "detail": str(p)})
        except Exception as e:
            checks.append({"name": name + " writable", "status": "fail", "detail": f"{p} — {e}"})

    # 6) Bundled SCImago data
    scimago_default = get_data_dir() / "scimagojr_2025.json"
    scimago_present = scimago_default.is_file()
    checks.append({
        "name": "Bundled SCImago data",
        "status": "ok" if scimago_present else "warn",
        "detail": str(scimago_default) + (" (download via `findref scimago download`)" if not scimago_present else ""),
    })

    # 7) Optional dependencies
    for pkg in ["bibtexparser"]:
        try:
            __import__(pkg)
            checks.append({"name": f"Optional dep: {pkg}", "status": "ok", "detail": "installed"})
        except ImportError:
            checks.append({"name": f"Optional dep: {pkg}", "status": "warn", "detail": "not installed (optional)"})

    # 8) API connectivity
    api_results = _check_apis()
    checks.extend(api_results)

    # Render
    if json_output:
        output_json({"version": __version__, "checks": checks})
        raise typer.Exit(0)

    print_header("findref doctor", f"version {__version__}")

    table = Table(title="Diagnostics", border_style="blue", show_lines=False)
    table.add_column("Check", width=30)
    table.add_column("Status", width=10)
    table.add_column("Detail", overflow="fold")

    ok_count = 0
    warn_count = 0
    fail_count = 0

    for c in checks:
        status = c["status"]
        icon = {
            "ok": "[green]OK[/green]",
            "warn": "[yellow]WARN[/yellow]",
            "fail": "[red]FAIL[/red]",
        }.get(status, "?")
        if status == "ok":
            ok_count += 1
        elif status == "warn":
            warn_count += 1
        else:
            fail_count += 1
        table.add_row(c["name"], icon, c["detail"])

    console.print(table)

    console.print(
        f"\n[green]{ok_count} ok[/green]  |  [yellow]{warn_count} warnings[/yellow]  |  [red]{fail_count} failures[/red]\n"
    )

    if fail_count:
        raise typer.Exit(1)


def _check_apis() -> list[dict]:
    """OpenAlex connectivity probe (OpenAlex is the only online API used)."""
    out: list[dict] = []

    # Which mailto will actually be sent to OpenAlex?
    mailto = DEFAULT_OPENALEX_MAILTO
    try:
        mgr = get_manager()
        mgr.load(create_if_missing=False)
        mailto = mgr.effective_credentials().get("openalex_mailto") or DEFAULT_OPENALEX_MAILTO
    except Exception:
        pass

    try:
        from find_references_scopus.api.openalex import OpenAlexClient
        c = OpenAlexClient(mailto=mailto)
        c.request("GET", "/works/https://doi.org/10.1038/nature12373")
        out.append({"name": "API: OpenAlex", "status": "ok", "detail": "reachable"})
    except Exception as e:
        out.append({"name": "API: OpenAlex", "status": "fail", "detail": str(e)[:80]})

    if mailto == DEFAULT_OPENALEX_MAILTO:
        out.append({
            "name": "OpenAlex mailto",
            "status": "warn",
            "detail": "placeholder in use - run `findref setup` to set your own email",
        })
    else:
        out.append({"name": "OpenAlex mailto", "status": "ok", "detail": mailto})

    return out
