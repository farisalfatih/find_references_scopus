"""Configuration subpackage: OpenAlex mailto accounts + defaults + project config.

Where things live (via ``platformdirs``; ``findref config path`` prints the exact
config file, ``findref doctor`` lists every folder):

    config.toml   ~/.config/findref/ (Linux) | ~/Library/Application Support/findref/ (macOS)
                  | %LOCALAPPDATA%\\findref\\ (Windows)
    cache / logs  the OS cache and log folders (on Windows they sit inside %LOCALAPPDATA%\\findref\\)

Each folder can be moved with FINDREF_CONFIG_DIR / FINDREF_CACHE_DIR /
FINDREF_LOGS_DIR / FINDREF_DATA_DIR. A project can override settings with a
``.findref.yaml`` file (see :mod:`find_references_scopus.config.project`).

The config is plain TOML. It stores no secrets: OpenAlex needs no API key,
only a contact e-mail (mailto) for its polite pool.
"""

from __future__ import annotations

from find_references_scopus.config.manager import (
    ConfigManager,
    ConfigNotFoundError,
    Account,
    get_manager,
    reset_manager,
)
from find_references_scopus.config.defaults import (
    APP_NAME,
    CONFIG_DIR_NAME,
    CONFIG_FILE_NAME,
    DEFAULT_OPENALEX_MAILTO,
    get_config_dir,
    get_config_path,
    get_cache_dir,
    get_logs_dir,
    get_data_dir,
)
from find_references_scopus.config.project import (
    find_project_config,
    load_project_config,
    apply_env_overrides,
    apply_project_overrides,
    get_effective_config_path,
    resolve_defaults,
)

__all__ = [
    "ConfigManager",
    "ConfigNotFoundError",
    "Account",
    "get_manager",
    "reset_manager",
    "APP_NAME",
    "CONFIG_DIR_NAME",
    "CONFIG_FILE_NAME",
    "DEFAULT_OPENALEX_MAILTO",
    "get_config_dir",
    "get_config_path",
    "get_cache_dir",
    "get_logs_dir",
    "get_data_dir",
    "find_project_config",
    "load_project_config",
    "apply_project_overrides",
    "apply_env_overrides",
    "resolve_defaults",
    "get_effective_config_path",
]
