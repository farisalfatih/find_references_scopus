"""Shared utilities: console output, logging, JSON helpers, exit codes."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, List, Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

from find_references_scopus import EXIT_INTERRUPTED
from find_references_scopus.config.defaults import get_logs_dir


# ---------------------------------------------------------------------- #
# Theme + consoles
# ---------------------------------------------------------------------- #

_THEME = Theme(
    {
        "info": "cyan",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "header": "bold blue",
        "muted": "dim",
    }
)

# Consoles — one for stdout (rich-formatted), one for stderr.
console: Console = Console(theme=_THEME, highlight=False)
err_console: Console = Console(stderr=True, theme=_THEME, highlight=False)


def set_json_mode(enabled: bool) -> None:
    """In ``--json`` mode send ALL human-readable output to stderr.

    stdout then carries only the JSON document, so ``findref ... --json | jq``
    works. Call it at the start of every command with its ``--json`` flag; it is
    reversible, so calling it with ``False`` restores normal output.
    """
    console.stderr = bool(enabled)


# ---------------------------------------------------------------------- #
# Logging
# ---------------------------------------------------------------------- #

_LOGGING_CONFIGURED = False


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure root logging with Rich handler. Idempotent."""
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return logging.getLogger("findref")

    logs_dir = get_logs_dir()
    log_file = logs_dir / f"findref-{datetime.now().strftime('%Y%m%d')}.log"

    rich_handler = RichHandler(
        console=err_console,
        show_path=False,
        show_time=True,
        markup=True,
        rich_tracebacks=True,
    )
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(rich_handler)
    root.addHandler(file_handler)
    _LOGGING_CONFIGURED = True
    return logging.getLogger("findref")


def get_logger(name: str = "findref") -> logging.Logger:
    return logging.getLogger(name)


# ---------------------------------------------------------------------- #
# Console output helpers
# ---------------------------------------------------------------------- #

def print_header(title: str, subtitle: str = "") -> None:
    """Print a styled section header."""
    body = f"[header]{title}[/header]"
    if subtitle:
        body += f"\n[muted]{subtitle}[/muted]"
    console.print(Panel(body, border_style="blue", expand=False))


def print_success(message: str) -> None:
    console.print(f"[success]✓[/success] {message}")


def print_error(message: str) -> None:
    err_console.print(f"[error]✗[/error] {message}")


def print_warning(message: str) -> None:
    console.print(f"[warning]![/warning] {message}")


def print_info(message: str) -> None:
    console.print(f"[info]i[/info] {message}")


def print_table(
    title: str,
    columns: List[str],
    rows: List[List[Any]],
    *,
    show_lines: bool = False,
) -> None:
    """Render a table to the console."""
    table = Table(title=title, show_lines=show_lines, border_style="blue")
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*[str(c) for c in row])
    console.print(table)


# ---------------------------------------------------------------------- #
# JSON helpers
# ---------------------------------------------------------------------- #

def output_json(data: Any) -> int:
    """Print ``data`` as JSON to stdout (agent-friendly). Returns exit code 0."""
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    return 0


def load_json(path: str | Path) -> Any:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: Any, path: str | Path, *, indent: int = 2) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent, default=str)


def load_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def save_text(text: str, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def load_lines(path: str | Path) -> List[str]:
    """Read a text file, return non-empty non-comment lines."""
    text = load_text(path)
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]


# ---------------------------------------------------------------------- #
# Misc
# ---------------------------------------------------------------------- #

def die(message: str, exit_code: int = 1) -> "Any":
    """Print error and exit with code."""
    print_error(message)
    raise SystemExit(exit_code)


def confirm_interrupt() -> None:
    """Handle Ctrl+C cleanly."""
    console.print("\n[muted]Interrupted by user.[/muted]")
    raise SystemExit(EXIT_INTERRUPTED)
