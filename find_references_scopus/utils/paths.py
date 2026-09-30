"""Path resolution + auto-naming helpers for output files.

Resolves where to save search/filter/export results based on:
  1. Explicit ``--output`` flag (highest priority)
  2. ``FINDREF_OUTPUT_DIR`` environment variable
  3. Config defaults ``output_dir``
  4. Current working directory (fallback)

Also provides auto-naming when ``--auto-name`` is used::

    search_<query-slug>_<YYYYMMDD_HHMMSS>.json
    filter_<input-stem>_filtered_<YYYYMMDD_HHMMSS>.json
    export_<input-stem>_<format>_<YYYYMMDD_HHMMSS>.<ext>
"""

from __future__ import annotations

import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

from find_references_scopus.config.defaults import get_user_data_dir


# ---------------------------------------------------------------------- #
# Output directory resolution
# ---------------------------------------------------------------------- #

def resolve_output_dir(
    *,
    explicit_dir: Optional[str] = None,
    config_output_dir: str = "",
) -> Path:
    """Resolve where output files should be saved by default.

    Priority (highest first):
      1. ``explicit_dir`` (CLI ``--output-dir`` flag)
      2. ``FINDREF_OUTPUT_DIR`` env var
      3. ``config_output_dir`` from the project file / user config (``findref config path``)
      4. Current working directory

    The resolved directory is created if it doesn't exist.

    Special values:
      - ``"cwd"`` → current working directory
      - ``"user_data"`` → the findref user data dir (``findref doctor`` shows it)
      - ``"~"`` or any ``~``-prefixed path → expanded
    """
    # 1. Explicit CLI flag
    candidate = explicit_dir

    # 2. Env var
    if not candidate:
        candidate = os.environ.get("FINDREF_OUTPUT_DIR", "")

    # 3. Config default
    if not candidate:
        candidate = config_output_dir

    # 4. Fallback to CWD
    if not candidate:
        return Path.cwd()

    # Resolve special values
    candidate = candidate.strip()
    if candidate.lower() in {"cwd", ".", "current"}:
        return Path.cwd()
    if candidate.lower() in {"user_data", "user-data", "data"}:
        return get_user_data_dir()

    # Expand ~ and make absolute
    p = Path(candidate).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------- #
# Auto-naming
# ---------------------------------------------------------------------- #

def slugify(text: str, *, max_length: int = 40) -> str:
    """Convert free text to a filesystem-safe slug.

    Examples::

        "Deep Learning for Finance" → "deep-learning-for-finance"
        "LSTM & Bitcoin price!"     → "lstm-bitcoin-price"
        "データサイエンス"            → "datasaisu"  (NFKC normalized)
    """
    if not text:
        return "search"
    # NFKC normalize (e.g. full-width → half-width, decompose ligatures)
    text = unicodedata.normalize("NFKC", text)
    # Lowercase
    text = text.lower()
    # Replace non-alphanumeric runs with single dash
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Strip leading/trailing dashes
    text = text.strip("-")
    # Truncate (don't cut mid-word; cut at last dash before limit)
    if len(text) > max_length:
        text = text[:max_length]
        # Cut at last dash
        if "-" in text:
            text = text[: text.rindex("-")]
        text = text.strip("-")
    return text or "search"


def timestamp() -> str:
    """Current timestamp in YYYYMMDD_HHMMSS format."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def auto_name(
    kind: str,
    *,
    query: Optional[str] = None,
    input_path: Optional[Path] = None,
    format: Optional[str] = None,
    extension: Optional[str] = None,
) -> str:
    """Generate an auto filename based on operation kind.

    Args:
        kind: "search", "filter", "export", "validate"
        query: For search — the query string (will be slugified)
        input_path: For filter/export — the input file path (stem is used)
        format: For export — the output format (bibtex, ris, etc.)
        extension: Override the file extension (default: derived from format/kind)

    Returns:
        A filename like ``search_deep-learning_20260927_120000.json``.
    """
    ts = timestamp()

    # Determine extension
    if extension:
        ext = extension.lstrip(".")
    elif format:
        ext_map = {
            "bibtex": "bib",
            "bib": "bib",
            "ris": "ris",
            "csv": "csv",
            "jsonl": "jsonl",
            "json": "json",
            "md": "md",
            "markdown": "md",
        }
        ext = ext_map.get(format.lower(), format.lower())
    else:
        # Default by kind
        ext = {
            "search": "json",
            "filter": "json",
            "validate": "json",
            "export": "bib",
        }.get(kind, "txt")

    # Build name
    if kind == "search" and query:
        slug = slugify(query)
        return f"search_{slug}_{ts}.{ext}"
    elif kind == "filter" and input_path:
        stem = input_path.stem
        return f"filter_{stem}_filtered_{ts}.{ext}"
    elif kind == "export" and input_path:
        stem = input_path.stem
        fmt = format or "bib"
        return f"export_{stem}_{fmt}_{ts}.{ext}"
    elif kind == "validate":
        return f"validate_{ts}.{ext}"
    else:
        # Generic fallback
        slug = slugify(query or "")
        return f"{kind}_{slug}_{ts}.{ext}" if slug else f"{kind}_{ts}.{ext}"


# ---------------------------------------------------------------------- #
# Full resolution: combine dir + filename
# ---------------------------------------------------------------------- #

def resolve_output_path(
    *,
    explicit_output: Optional[str] = None,
    explicit_dir: Optional[str] = None,
    config_output_dir: str = "",
    auto_name_enabled: bool = False,
    kind: str = "search",
    query: Optional[str] = None,
    input_path: Optional[Path] = None,
    format: Optional[str] = None,
    extension: Optional[str] = None,
) -> Path:
    """Resolve the full output file path.

    Priority for the FILENAME:
      1. If ``explicit_output`` is given AND it's a path to a file → use it as-is
      2. If ``explicit_output`` is given AND it's just a directory → auto-name inside it
      3. If ``auto_name_enabled`` is True → use ``auto_name()``
      4. Otherwise → default name like ``results.json`` / ``filtered.json`` / ``export.bib``

    The directory portion is resolved via :func:`resolve_output_dir`.

    Args:
        explicit_output: ``--output`` flag value (could be file or dir).
        explicit_dir: ``--output-dir`` flag value.
        config_output_dir: ``output_dir`` from config.
        auto_name_enabled: ``--auto-name`` flag.
        kind: "search" / "filter" / "export" / "validate".
        query: For search — the query string.
        input_path: For filter/export — the input file.
        format: For export — the format name.
        extension: Force a specific extension.

    Returns:
        Absolute Path to the output file (parent dir auto-created).
    """
    # Case 1: explicit_output is a full file path
    if explicit_output:
        p = Path(explicit_output).expanduser()
        # If user gave a path ending with / or it's an existing dir → treat as dir
        if explicit_output.endswith("/") or p.is_dir():
            out_dir = resolve_output_dir(
                explicit_dir=str(p),
                config_output_dir=config_output_dir,
            )
            filename = auto_name(
                kind=kind, query=query, input_path=input_path,
                format=format, extension=extension,
            ) if auto_name_enabled else _default_name(kind, format, extension)
            return out_dir / filename
        # Otherwise treat as full file path
        if not p.is_absolute():
            p = Path.cwd() / p
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    # Case 2: no explicit output — resolve dir + filename
    out_dir = resolve_output_dir(
        explicit_dir=explicit_dir,
        config_output_dir=config_output_dir,
    )

    if auto_name_enabled:
        filename = auto_name(
            kind=kind, query=query, input_path=input_path,
            format=format, extension=extension,
        )
    else:
        filename = _default_name(kind, format, extension)

    return out_dir / filename


def _default_name(kind: str, format: Optional[str] = None, extension: Optional[str] = None) -> str:
    """Generate a simple default filename (no timestamp)."""
    if kind == "search":
        return "search_results.json"
    if kind == "filter":
        return "filtered.json"
    if kind == "validate":
        return "validated.json"
    if kind == "export":
        ext_map = {
            "bibtex": "bib", "bib": "bib",
            "ris": "ris", "csv": "csv",
            "jsonl": "jsonl", "json": "json",
            "md": "md", "markdown": "md",
        }
        ext = extension.lstrip(".") if extension else (ext_map.get((format or "bibtex").lower(), "bib"))
        return f"references.{ext}"
    return "output.txt"


# ---------------------------------------------------------------------- #
# Auto-name env helper
# ---------------------------------------------------------------------- #

def is_auto_name_enabled(
    *,
    cli_flag: Optional[bool] = None,
    config_value: bool = False,
) -> bool:
    """Determine if auto-naming should be used.

    Priority:
      1. CLI flag (``--auto-name`` / ``--no-auto-name``)
      2. ``FINDREF_AUTO_NAME`` env var
      3. Config default ``auto_name``
    """
    if cli_flag is not None:
        return cli_flag
    env = os.environ.get("FINDREF_AUTO_NAME", "")
    if env:
        return env.lower() in {"true", "1", "yes", "y"}
    return config_value
