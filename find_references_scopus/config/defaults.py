"""Default paths and constants for the findref CLI."""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_config_dir, user_cache_dir, user_data_dir, user_log_dir

APP_NAME = "findref"
APP_AUTHOR = "find-refs"
CONFIG_DIR_NAME = ".findref"
CONFIG_FILE_NAME = "config.toml"
PROJECTS_DIR_NAME = "projects"
CACHE_DIR_NAME = "cache"
LOGS_DIR_NAME = "logs"
DATA_DIR_NAME = "data"

DEFAULT_OPENALEX_MAILTO = "researcher@example.com"
DEFAULT_REQUEST_DELAY = 1.0
DEFAULT_PER_PAGE = 200
DEFAULT_YEAR_FROM = 2018
DEFAULT_YEAR_TO = 2026
DEFAULT_LANGUAGE = "en"


def _resolve_config_dir() -> Path:
    """Resolve the config directory.

    Honors the ``FINDREF_CONFIG_DIR`` environment variable for testing / portable
    installations. Otherwise uses the platform default from ``platformdirs``:
    ``~/.config/findref`` (Linux), ``~/Library/Application Support/findref``
    (macOS) or ``%LOCALAPPDATA%\\findref`` (Windows).
    """
    env_override = os.environ.get("FINDREF_CONFIG_DIR")
    if env_override:
        return Path(env_override).expanduser().resolve()

    # Prefer platformdirs (handles Windows / macOS / Linux correctly)
    base = Path(user_config_dir(APP_NAME, appauthor=False))
    return base


def get_config_dir() -> Path:
    """Return (creating if necessary) the config directory."""
    p = _resolve_config_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_config_path() -> Path:
    """Return the path to the main config TOML file."""
    return get_config_dir() / CONFIG_FILE_NAME


def get_projects_dir() -> Path:
    """Return (creating if necessary) the per-project configs dir."""
    p = get_config_dir() / PROJECTS_DIR_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_cache_dir() -> Path:
    """Return (creating if necessary) the HTTP cache dir."""
    p = Path(user_cache_dir(APP_NAME, appauthor=False))
    if env := os.environ.get("FINDREF_CACHE_DIR"):
        p = Path(env).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_logs_dir() -> Path:
    """Return (creating if necessary) the logs dir."""
    p = Path(user_log_dir(APP_NAME, appauthor=False))
    if env := os.environ.get("FINDREF_LOGS_DIR"):
        p = Path(env).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_data_dir() -> Path:
    """Return (creating if necessary) the bundled data dir (read-only).

    This is the directory inside the package that ships with SCImago JSON,
    default filter rules, etc. End-users should NOT modify these files.
    """
    p = Path(__file__).resolve().parent.parent / DATA_DIR_NAME
    return p


def get_user_data_dir() -> Path:
    """Return (creating if necessary) the user data dir for custom SCImago json, etc."""
    p = Path(user_data_dir(APP_NAME, appauthor=False))
    if env := os.environ.get("FINDREF_DATA_DIR"):
        p = Path(env).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p
