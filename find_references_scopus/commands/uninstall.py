"""``findref uninstall`` — remove findref from this computer.

What it removes
---------------
Installed with the installer scripts (``install.sh`` / ``install.ps1``):

  * the launchers  (``findref`` / ``find-refs``)   -> ``~/.local/bin`` (Linux/macOS) or ``<home>\\bin`` (Windows)
  * the PATH entry the installer added             -> ``# findref`` block in ``~/.bashrc`` etc. / user PATH on Windows
  * the program itself                             -> ``<home>/src`` and ``<home>/venv``

``<home>`` is ``~/.findref`` on Linux/macOS and ``%LOCALAPPDATA%\\findref`` on Windows.
Only those folders are removed, never the whole of ``<home>`` blindly.

Your settings (config, accounts, cache, logs) are KEPT unless you pass ``--purge``.

Installed some other way (``pip install`` into your own venv)? Then findref cannot
remove itself; it tells you the ``pip uninstall find-refs`` command to run.

The folders that contain the running program are deleted by a small helper that
starts after findref exits (a running program cannot delete itself, notably on Windows).

Examples::

    findref uninstall --dry-run       # show what would be removed
    findref uninstall                 # ask, then remove the program (keep settings)
    findref uninstall --yes --purge   # remove everything, no questions
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer

from find_references_scopus import EXIT_ERROR, EXIT_OK
from find_references_scopus.utils import (
    console,
    output_json,
    print_error,
    print_header,
    print_success,
    print_warning,
    set_json_mode,
)

LAUNCHER_NAMES = ("findref", "find-refs")
PATH_MARKER = "# findref"  # comment line the installer puts above its PATH line
INSTALL_MARKER = ".findref-install"  # file the installers drop in <home>
PIP_PACKAGE = "find-refs"
IS_WINDOWS = os.name == "nt"


# ---------------------------------------------------------------------- #
# Data model
# ---------------------------------------------------------------------- #

@dataclass
class Layout:
    """How this copy of findref was installed."""

    kind: str  # "installer" | "other"
    home: Optional[Path] = None

    @property
    def venv(self) -> Optional[Path]:
        return self.home / "venv" if self.home else None

    @property
    def src(self) -> Optional[Path]:
        return self.home / "src" if self.home else None

    @property
    def win_bin(self) -> Optional[Path]:
        return self.home / "bin" if self.home else None


@dataclass
class Step:
    """One thing the uninstaller will do."""

    kind: str  # launcher | rc_line | user_path | dir | file | glob
    target: str
    detail: str = ""
    deferred: bool = False  # deleted by the helper process after findref exits
    status: str = "planned"  # planned | done | scheduled | skipped | failed
    error: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {"kind": self.kind, "target": self.target, "detail": self.detail, "status": self.status}
        if self.error:
            d["error"] = self.error
        return d


# ---------------------------------------------------------------------- #
# Detection
# ---------------------------------------------------------------------- #

def detect_layout(prefix: Optional[Path] = None) -> Layout:
    """Decide whether findref runs from an installer-made venv (``<home>/venv``)."""
    prefix = Path(prefix or sys.prefix).resolve()
    if prefix.name == "venv" and (prefix / "pyvenv.cfg").is_file():
        home = prefix.parent
        if (home / INSTALL_MARKER).is_file() or (home / "src").is_dir() or (home / "bin").is_dir():
            return Layout("installer", home)
    return Layout("other")


# ---------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# ---------------------------------------------------------------------- #

def strip_path_block(text: str) -> tuple[str, bool]:
    """Remove the ``# findref`` + ``export PATH=...`` block the installer appended.

    Returns ``(new_text, removed)``. Other lines are left untouched; a blank line
    directly before the block (which the installer added) is removed with it.
    """
    lines = text.split("\n")
    out: List[str] = []
    removed = False
    i = 0
    while i < len(lines):
        if lines[i].strip() == PATH_MARKER:
            removed = True
            if out and out[-1].strip() == "":
                out.pop()
            i += 1
            if i < len(lines) and lines[i].lstrip().startswith("export PATH="):
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out), removed


def _findref_root(path: Path) -> Optional[Path]:
    """The folder named ``findref`` that owns ``path`` (itself or its parent), if any."""
    if path.name.lower() == "findref":
        return path
    if path.parent.name.lower() == "findref":
        return path.parent  # e.g. ~/.local/state/findref/log
    return None


def is_safe_delete_target(path: Path) -> bool:
    """Guard for recursive deletes: absolute, not a root, not the home directory or above it."""
    if not path.is_absolute():
        return False  # never resolve a relative path against an arbitrary CWD before deleting
    try:
        p = path.resolve()
    except OSError:
        return False
    home = Path.home().resolve()
    if p == Path(p.anchor) or len(p.parts) < 3:
        return False
    if p == home or p in home.parents:
        return False
    return True


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------- #
# Planning
# ---------------------------------------------------------------------- #

def _user_data_locations() -> List[tuple[str, str, Path, List[str]]]:
    """(label, env var, folder, files findref creates there) for config/data/cache/logs."""
    from find_references_scopus.config.defaults import (
        get_cache_dir,
        get_config_dir,
        get_logs_dir,
        get_user_data_dir,
    )

    return [
        ("config", "FINDREF_CONFIG_DIR", get_config_dir(), ["config.toml", "projects"]),
        ("data", "FINDREF_DATA_DIR", get_user_data_dir(), ["scimagojr.json", "scimagojr_2025.json"]),
        ("cache", "FINDREF_CACHE_DIR", get_cache_dir(), ["http_cache*"]),
        ("logs", "FINDREF_LOGS_DIR", get_logs_dir(), ["findref-*.log"]),
    ]


def plan_uninstall(layout: Layout, *, purge: bool, bin_dir: Optional[Path] = None) -> List[Step]:
    """List the steps for this layout. Nothing is changed here."""
    steps: List[Step] = []
    bin_dir = bin_dir or (Path.home() / ".local" / "bin")

    if layout.kind == "installer" and layout.home is not None:
        venv, src, home = layout.venv, layout.src, layout.home
        assert venv is not None and src is not None

        if IS_WINDOWS:
            wb = layout.win_bin
            assert wb is not None
            steps.append(Step("user_path", str(wb), "remove from the user PATH"))
        else:
            for name in LAUNCHER_NAMES:
                link = bin_dir / name
                if link.is_symlink() and _is_within(link, venv):
                    steps.append(Step("launcher", str(link), "remove command"))
            for rc in (Path.home() / n for n in (".bashrc", ".zshrc", ".profile")):
                if rc.is_file():
                    try:
                        if PATH_MARKER in rc.read_text(encoding="utf-8", errors="ignore"):
                            steps.append(Step("rc_line", str(rc), "remove the PATH line added by the installer"))
                    except OSError:
                        pass

        for d, note in ((venv, "program (virtualenv)"), (src, "downloaded source")):
            if d.exists():
                steps.append(Step("dir", str(d), note, deferred=True))
        if IS_WINDOWS and layout.win_bin is not None and layout.win_bin.exists():
            steps.append(Step("dir", str(layout.win_bin), "command shims", deferred=True))
        if (home / INSTALL_MARKER).exists():
            steps.append(Step("file", str(home / INSTALL_MARKER), "install marker", deferred=True))

    if purge:
        scheduled: List[Path] = []
        for label, env_name, folder, names in _user_data_locations():
            root = None if os.environ.get(env_name) else _findref_root(folder)
            if root is not None and is_safe_delete_target(root):
                if any(_is_within(root, s) for s in scheduled):
                    continue  # already covered by a folder we delete anyway
                scheduled.append(root)
                steps.append(Step("dir", str(root), f"{label} folder", deferred=True))
            else:
                # Folder chosen through an env var (or not app-owned): delete only what findref put there.
                steps.append(Step("glob", str(folder), f"findref {label} files", deferred=True, extra={"names": names}))

    return steps


# ---------------------------------------------------------------------- #
# Execution
# ---------------------------------------------------------------------- #

def _remove_launcher(step: Step) -> None:
    Path(step.target).unlink()


def _remove_rc_line(step: Step) -> None:
    rc = Path(step.target)
    text = rc.read_text(encoding="utf-8", errors="ignore")
    new_text, removed = strip_path_block(text)
    if not removed:
        step.status = "skipped"
        return
    rc.write_text(new_text, encoding="utf-8")


def _remove_windows_user_path(step: Step) -> None:
    """Drop the shim folder from the user PATH (PowerShell also broadcasts the change)."""
    target = step.target.replace("'", "''")
    script = (
        f"$b='{target}'; $p=[Environment]::GetEnvironmentVariable('Path','User'); "
        "if($p){ $n=($p.Split(';') | Where-Object { $_ -and ($_.TrimEnd('\\') -ne $b.TrimEnd('\\')) }) -join ';'; "
        "[Environment]::SetEnvironmentVariable('Path',$n,'User') }"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        check=True,
        capture_output=True,
        timeout=60,
    )


def _spawn_helper(dir_targets: List[Path], file_targets: List[Path], cleanup_dirs: List[Path]) -> None:
    """Start a detached process that deletes the paths a moment after findref exits."""
    if IS_WINDOWS:
        lines = ["@echo off", "ping -n 4 127.0.0.1 >nul"]
        for d in dir_targets:
            lines.append(f'rmdir /s /q "{d}"')
        for f in file_targets:
            lines.append(f'del /f /q "{f}"')
        for d in cleanup_dirs:
            lines.append(f'rmdir "{d}" 2>nul')  # only succeeds when empty
        lines.append('(goto) 2>nul & del "%~f0"')
        fd, script = tempfile.mkstemp(prefix="findref-uninstall-", suffix=".cmd")
        with os.fdopen(fd, "w", encoding="ascii", errors="replace") as fh:
            fh.write("\r\n".join(lines) + "\r\n")
        flags = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW
        subprocess.Popen(
            ["cmd.exe", "/c", script],
            creationflags=flags,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    cmds = ["sleep 1"]
    for d in dir_targets:
        cmds.append(f"rm -rf -- {shlex.quote(str(d))}")
    for f in file_targets:
        cmds.append(f"rm -f -- {shlex.quote(str(f))}")
    for d in cleanup_dirs:
        cmds.append(f"rmdir -- {shlex.quote(str(d))} 2>/dev/null")  # only succeeds when empty
    subprocess.Popen(
        ["/bin/sh", "-c", "; ".join(cmds)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def execute(steps: List[Step], layout: Layout) -> None:
    """Run the immediate steps, then start one helper for everything deferred."""
    for s in steps:
        if s.deferred:
            continue
        try:
            if s.kind == "launcher":
                _remove_launcher(s)
            elif s.kind == "rc_line":
                _remove_rc_line(s)
            elif s.kind == "user_path":
                _remove_windows_user_path(s)
            if s.status == "planned":
                s.status = "done"
        except Exception as e:  # noqa: BLE001 - report and continue with the rest
            s.status = "failed"
            s.error = str(e)

    import glob

    dir_targets: List[Path] = []
    file_targets: List[Path] = []
    cleanup: List[Path] = [layout.home] if (layout.kind == "installer" and layout.home is not None) else []
    for s in steps:
        if not s.deferred:
            continue
        p = Path(s.target)
        if s.kind == "dir":
            if is_safe_delete_target(p):
                dir_targets.append(p)
            else:
                s.status, s.error = "failed", "refusing to delete an unsafe path"
        elif s.kind == "file":
            file_targets.append(p)
        elif s.kind == "glob":
            # Expand now, delete after exit (a log file may be open on Windows).
            for pattern in s.extra.get("names", []):
                for hit in glob.glob(str(p / pattern)):
                    hp = Path(hit)
                    if hp.is_dir():
                        if is_safe_delete_target(hp):
                            dir_targets.append(hp)
                    else:
                        file_targets.append(hp)
            cleanup.append(p)  # removed afterwards only if it ended up empty

    if dir_targets or file_targets:
        try:
            _spawn_helper(dir_targets, file_targets, cleanup)
        except Exception as e:  # noqa: BLE001
            for s in steps:
                if s.deferred and s.status == "planned":
                    s.status, s.error = "failed", f"could not start the cleanup helper: {e}"
            return

    for s in steps:
        if s.deferred and s.status == "planned":
            s.status = "scheduled"


# ---------------------------------------------------------------------- #
# Command
# ---------------------------------------------------------------------- #

def uninstall_command(
    ctx: typer.Context,
    yes: bool = False,
    purge: bool = False,
    dry_run: bool = False,
    json_output: bool = False,
) -> None:
    """Remove findref (program + launchers + PATH entry); keep settings unless ``--purge``."""
    set_json_mode(json_output)

    layout = detect_layout()
    interactive = sys.stdin.isatty() and not json_output

    if json_output and not (yes or dry_run):
        print_error("With --json add --yes (to run) or --dry-run (to preview); there is no prompt in JSON mode.")
        raise typer.Exit(EXIT_ERROR)

    # Ask about settings only when the user has not decided with --purge / --yes
    if not purge and not yes and not dry_run and interactive:
        purge = typer.confirm(
            "Also delete your settings (config, accounts, cache, logs)? [default: keep them]",
            default=False,
        )

    steps = plan_uninstall(layout, purge=purge)
    pip_hint = f"{sys.executable} -m pip uninstall {PIP_PACKAGE}"

    if not json_output:
        print_header("findref uninstall", "Preview" if dry_run else "")
        if layout.kind == "installer":
            console.print(f"Installed by the installer script in: [code]{layout.home}[/code]")
        else:
            print_warning(
                "findref was not installed by the installer script, so it cannot remove its own program files."
            )
            console.print(f"  To remove the program run:  [code]{pip_hint}[/code]")
        if steps:
            console.print("\nWill remove:")
            for s in steps:
                console.print(f"  - {s.target}  [muted]({s.detail})[/muted]")
        if not purge:
            console.print("\n[muted]Your settings (config, accounts, cache, logs) are kept. Use --purge to delete them.[/muted]")

    if not steps:
        if json_output:
            output_json({"layout": layout.kind, "purge": purge, "dry_run": dry_run, "steps": [],
                         "program_removed": False, "hint": pip_hint if layout.kind == "other" else ""})
        else:
            console.print("\nNothing to remove.")
        raise typer.Exit(EXIT_OK)

    if dry_run:
        if json_output:
            output_json({"layout": layout.kind, "purge": purge, "dry_run": True,
                         "steps": [s.to_dict() for s in steps], "program_removed": False,
                         "hint": pip_hint if layout.kind == "other" else ""})
        else:
            console.print("\n[muted]Dry run: nothing was changed.[/muted]")
        raise typer.Exit(EXIT_OK)

    if not yes:
        if not interactive:
            print_error("Not running in a terminal: add --yes to confirm, or --dry-run to preview.")
            raise typer.Exit(EXIT_ERROR)
        if not typer.confirm("\nProceed?", default=False):
            console.print("Cancelled. Nothing was changed.")
            raise typer.Exit(EXIT_OK)

    execute(steps, layout)

    failed = [s for s in steps if s.status == "failed"]
    if json_output:
        output_json({
            "layout": layout.kind,
            "purge": purge,
            "dry_run": False,
            "steps": [s.to_dict() for s in steps],
            "program_removed": layout.kind == "installer" and not failed,
            "hint": pip_hint if layout.kind == "other" else "",
        })
    else:
        for s in steps:
            mark = {"done": "[green]✓[/green]", "scheduled": "[green]✓[/green]", "skipped": "[muted]-[/muted]"}.get(
                s.status, "[red]✗[/red]"
            )
            note = " (deleted in a moment, after findref exits)" if s.status == "scheduled" else ""
            note = f" — {s.error}" if s.error else note
            console.print(f"  {mark} {s.target}{note}")
        if failed:
            print_error("Some steps failed (see above). You can delete those paths by hand.")
        else:
            print_success("findref has been uninstalled." if layout.kind == "installer" else "Done.")
            if IS_WINDOWS and layout.kind == "installer":
                console.print("  Close and reopen your terminal so the PATH change takes effect.")
            elif layout.kind == "installer":
                console.print("  Open a new terminal (the PATH line was removed from your shell startup files).")
    raise typer.Exit(EXIT_ERROR if failed else EXIT_OK)
