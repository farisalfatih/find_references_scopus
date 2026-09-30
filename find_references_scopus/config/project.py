"""Project-local config loader.

Loads ``.findref.yaml`` (or ``findref.yaml``) from the current working
directory, if present. Project-local values OVERRIDE the user config defaults
but are OVERRIDDEN by CLI flags and environment variables.

This is useful for project-specific overrides such as:
  - Different SCImago path per project
  - Different default output directory per project
  - Different OpenAlex mailto pool per project

Priority for any setting (highest first):

  1. CLI flag
  2. Environment variable (``FINDREF_*``)
  3. Project-local file (this module)
  4. User config (``findref config path`` shows where ``config.toml`` lives)
  5. Built-in default

Example ``.findref.yaml``::

    # Project-local findref config
    defaults:
      openalex_mailto: alice@project-specific.edu
      openalex_mailto_pool: "alice@x.edu,bob@y.edu"   # or a YAML list
      openalex_auto_rotate: true
      output_dir: ./refs
      auto_name: true
      year_from: 2020
      year_to: 2025

      # SCImago ISSN filter (same keys as `findref config set-issn-filter`)
      use_issn_filter: true
      issn_subject_areas: [Computer Science, Mathematics]   # or "Computer Science,Mathematics"
      issn_quartiles: "Q1,Q2"
      issn_include_unranked: false

    # Project-specific SCImago data (same as defaults.scimago_path)
    scimago_path: ./data/scimagojr_2025.json
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


# Files to look for, in order of priority
PROJECT_CONFIG_FILES = [
    ".findref.yaml",
    ".findref.yml",
    "findref.yaml",
    "findref.yml",
]


def find_project_config(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Find a project-local config file by walking up from ``start_dir``.

    Searches for ``.findref.yaml`` (or variants) starting from ``start_dir``
    (default: CWD) and walking up the directory tree until found or until
    reaching the filesystem root.

    Returns:
        Path to the config file, or None if not found.
    """
    start = Path(start_dir or Path.cwd()).resolve()
    for current in [start, *start.parents]:
        for name in PROJECT_CONFIG_FILES:
            candidate = current / name
            if candidate.is_file():
                return candidate
    return None


def load_project_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load and parse a project-local config file.

    Args:
        path: Explicit path to the config file. If None, auto-discovers.

    Returns:
        Dict with config values. Empty dict if no file found or parse error.
    """
    config_path = path or find_project_config()
    if not config_path:
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            return {}
        data["__project_config_path__"] = str(config_path)
        return data
    except Exception:
        return {}


def apply_project_overrides(
    user_defaults: Any,
    project_config: Dict[str, Any],
) -> Any:
    """Apply project-local overrides to a Defaults dataclass.

    Only overrides fields that are explicitly set in the project config.
    Returns a NEW Defaults instance (doesn't mutate the input).

    Args:
        user_defaults: The Defaults dataclass from user config.
        project_config: Dict from load_project_config().

    Returns:
        New Defaults dataclass with project overrides applied.
    """
    import copy
    new_defaults = copy.deepcopy(user_defaults)

    project_defaults = project_config.get("defaults", {})
    if not isinstance(project_defaults, dict):
        return new_defaults

    # Map project YAML keys to Defaults fields
    field_mapping = {
        "openalex_mailto": _to_str,
        "openalex_mailto_pool": _to_csv,
        "openalex_auto_rotate": _to_bool,
        "output_dir": _to_str,
        "auto_name": _to_bool,
        "year_from": int,
        "year_to": int,
        "language": _to_str,
        "per_page": int,
        "request_delay": float,
        "scimago_path": _to_str,
        "cache_enabled": _to_bool,
        "cache_ttl": int,
        "log_level": _to_str,
        # SCImago ISSN filter
        "use_issn_filter": _to_bool,
        "issn_subject_areas": _to_csv,
        "issn_quartiles": _to_csv,
        "issn_include_unranked": _to_bool,
    }

    for key, cast_fn in field_mapping.items():
        if key in project_defaults and project_defaults[key] is not None:
            try:
                value = cast_fn(project_defaults[key])
                setattr(new_defaults, key, value)
            except (ValueError, TypeError):
                continue

    # Also support top-level scimago_path (convenience shorthand)
    if "scimago_path" in project_config:
        try:
            setattr(new_defaults, "scimago_path", str(project_config["scimago_path"]))
        except Exception:
            pass

    return new_defaults


def get_effective_config_path() -> Optional[Path]:
    """Convenience: return the path of the active project config (if any)."""
    return find_project_config()


# ---------------------------------------------------------------------- #
# Value casting (YAML-friendly)
# ---------------------------------------------------------------------- #

_TRUE = {"true", "1", "yes", "y", "on"}
_FALSE = {"false", "0", "no", "n", "off", ""}


def _to_str(value: Any) -> str:
    return str(value)


def _to_bool(value: Any) -> bool:
    """YAML/env friendly bool: real bools pass through, strings like "false" are False."""
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    raise ValueError(f"not a boolean: {value!r}")


def _to_csv(value: Any) -> str:
    """Accept ``"a,b"`` or a YAML list ``[a, b]`` and return ``"a,b"``."""
    if isinstance(value, (list, tuple, set)):
        return ",".join(str(v).strip() for v in value if str(v).strip())
    return str(value)


# ---------------------------------------------------------------------- #
# Environment variable overrides
# ---------------------------------------------------------------------- #

# env var -> (Defaults field, caster)
ENV_DEFAULT_OVERRIDES = {
    "FINDREF_USE_ISSN_FILTER": ("use_issn_filter", _to_bool),
    "FINDREF_ISSN_SUBJECT_AREAS": ("issn_subject_areas", _to_csv),
    "FINDREF_ISSN_QUARTILES": ("issn_quartiles", _to_csv),
    "FINDREF_ISSN_INCLUDE_UNRANKED": ("issn_include_unranked", _to_bool),
}


def apply_env_overrides(defaults: Any) -> Any:
    """Apply ``FINDREF_*`` environment overrides for the ISSN filter settings.

    Returns a NEW Defaults instance. (Mailto, pool, rotation, output dir and
    auto-name env vars are handled where they are used.)
    """
    import copy

    new_defaults = copy.deepcopy(defaults)
    for env_name, (attr, cast_fn) in ENV_DEFAULT_OVERRIDES.items():
        raw = os.environ.get(env_name)
        if raw is None or (cast_fn is _to_bool and raw.strip() == ""):
            continue  # unset, or an empty boolean: leave the config value alone
        try:
            setattr(new_defaults, attr, cast_fn(raw))
        except (ValueError, TypeError):
            continue
    return new_defaults


def resolve_defaults(mgr: Any = None) -> Any:
    """User config + project-local file + environment, in that order of increasing priority.

    (CLI flags are applied by the commands themselves, on top of this result.)
    """
    if mgr is None:
        from find_references_scopus.config.manager import get_manager

        mgr = get_manager()
    merged = apply_project_overrides(mgr.get_defaults(), load_project_config())
    return apply_env_overrides(merged)
