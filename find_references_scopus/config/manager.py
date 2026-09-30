"""Multi-account configuration manager.

OpenAlex is the only online API findref talks to, and it needs no API key -
only a contact e-mail (the "polite pool" mailto). An *account* therefore holds
one mailto. Users can register several accounts and switch between them via
``findref config use <name>``; all account mailtos also form a pool that is
rotated when OpenAlex answers HTTP 429.

Scopus indexing / quartiles are detected offline from bundled SCImago data
(see :mod:`find_references_scopus.core.scopus_checker`), so no Scopus key is used.

The config file is plain TOML. Its location depends on the OS (run
``findref config path`` to print it): ``~/.config/findref/config.toml`` on Linux,
``~/Library/Application Support/findref/config.toml`` on macOS and
``%LOCALAPPDATA%\\findref\\config.toml`` on Windows. Override the folder with
``FINDREF_CONFIG_DIR``.

Example config::

    [meta]
    version = "2.0.0"
    created_at = "2026-09-27T10:00:00"

    [defaults]
    openalex_mailto = "alice@university.edu"
    request_delay = 1.0
    per_page = 200
    year_from = 2018
    year_to = 2026
    language = "en"
    cache_ttl = 86400

    [current]
    account = "alice-univ"

    [accounts.alice-univ]
    label = "Alice (University)"
    openalex_mailto = "alice@university.edu"

    [accounts.bob-personal]
    label = "Bob (Personal)"
    openalex_mailto = "bob@gmail.com"
"""

from __future__ import annotations

import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # tomllib is stdlib in 3.11+, fall back to tomli
    import tomllib as _toml_reader
except ImportError:  # pragma: no cover
    import tomli as _toml_reader

import tomli_w

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


class ConfigNotFoundError(Exception):
    """Raised when no config file exists yet (user must run ``findref setup``)."""


class AccountNotFoundError(KeyError):
    """Raised when an account name is referenced but doesn't exist."""


@dataclass
class Account:
    """A named OpenAlex polite-pool identity (one mailto).

    Old config files may still contain ``scopus_api_key``, ``crossref_mailto``,
    etc. Those keys are ignored on load and dropped on the next save.
    """

    name: str = ""
    label: str = ""
    openalex_mailto: str = DEFAULT_OPENALEX_MAILTO
    extra: Dict[str, str] = field(default_factory=dict)

    def display(self) -> str:
        """Human-friendly one-line description for ``findref config list``."""
        bits: List[str] = []
        if self.label:
            bits.append(self.label)
        if self.openalex_mailto and self.openalex_mailto != DEFAULT_OPENALEX_MAILTO:
            bits.append(f"[{self.openalex_mailto}]")
        if not bits:
            bits.append("(no mailto)")
        return f"{self.name}  —  " + "  ".join(bits) if bits else self.name

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Don't persist empty extra dict
        if not d.get("extra"):
            d.pop("extra", None)
        return d

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "Account":
        return cls(
            name=name,
            label=str(data.get("label", "")),
            openalex_mailto=str(data.get("openalex_mailto", DEFAULT_OPENALEX_MAILTO)),
            extra={k: str(v) for k, v in data.get("extra", {}).items()} if isinstance(data.get("extra"), dict) else {},
        )


@dataclass
class Defaults:
    """Default runtime parameters — applied unless overridden per-call.

    Priority (highest to lowest) for any given field:
        1. CLI flag (e.g. ``--year-from 2024``)
        2. Environment variable (e.g. ``FINDREF_OUTPUT_DIR``)
        3. Project-local config (``.findref.yaml`` in CWD or a parent folder)
        4. User config defaults (``config.toml``, see ``findref config path``)
        5. These dataclass defaults
    """

    openalex_mailto: str = DEFAULT_OPENALEX_MAILTO
    request_delay: float = DEFAULT_REQUEST_DELAY
    per_page: int = DEFAULT_PER_PAGE
    year_from: int = DEFAULT_YEAR_FROM
    year_to: int = DEFAULT_YEAR_TO
    language: str = DEFAULT_LANGUAGE
    cache_ttl: int = 86400  # seconds
    cache_enabled: bool = True
    log_level: str = "INFO"
    scimago_path: str = ""  # empty = use bundled

    # Output directory: where to save search/filter/export results by default.
    # Empty string = current working directory.
    # Override with env var FINDREF_OUTPUT_DIR or CLI --output-dir.
    output_dir: str = ""

    # Auto-naming: when --auto-name is used, files are named with a timestamp
    # pattern like "search_<slug>_<YYYYMMDD_HHMMSS>.json".
    # Override with env var FINDREF_AUTO_NAME=true.
    auto_name: bool = False

    # OpenAlex mailto pool: comma-separated list of additional mailtos to rotate
    # through when the primary mailto hits a rate limit (429).
    # These are ADDED to the mailtos collected from all accounts.
    # Override with env var FINDREF_OPENALEX_MAILTO_POOL="a@x.com,b@y.com".
    openalex_mailto_pool: str = ""

    # OpenAlex auto-rotate: if True, automatically rotate mailtos per request
    # (round-robin). If False, only switch on 429.
    # Override with env var FINDREF_OPENALEX_AUTO_ROTATE=true.
    openalex_auto_rotate: bool = False

    # --- SCImago ISSN filter (applied to OpenAlex search) ---
    # When True, OpenAlex search is restricted to journals indexed in SCImago
    # (filtered by subject_area + quartile below).
    # Override with env var FINDREF_USE_ISSN_FILTER=true.
    use_issn_filter: bool = False

    # Comma-separated list of subject areas to include (case-insensitive).
    # Empty string = all subject areas.
    # Example: "Computer Science,Mathematics"
    # Override with env var FINDREF_ISSN_SUBJECT_AREAS.
    issn_subject_areas: str = ""

    # Comma-separated list of quartiles to include.
    # Empty string or "ALL" = all quartiles (Q1, Q2, Q3, Q4, -).
    # Example: "Q1,Q2"
    # Override with env var FINDREF_ISSN_QUARTILES.
    issn_quartiles: str = ""

    # Whether to include journals with quartile "-" (unranked but Scopus-indexed).
    # Override with env var FINDREF_ISSN_INCLUDE_UNRANKED=true.
    issn_include_unranked: bool = True


class ConfigManager:
    """Thread-safe manager for the multi-account config file.

    Singleton-accessible via ``get_manager()``. Reads/writes ``config.toml`` (see ``findref config path``).
    """

    _instance: Optional["ConfigManager"] = None
    _lock = threading.Lock()

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or get_config_path()
        self._accounts: Dict[str, Account] = {}
        self._defaults = Defaults()
        self._current_account: Optional[str] = None
        self._meta: Dict[str, Any] = {"version": __version__, "created_at": datetime.now().isoformat()}
        self._dirty = False
        self._loaded = False

    # ------------------------------------------------------------------ #
    # Load / save
    # ------------------------------------------------------------------ #

    def load(self, *, create_if_missing: bool = False) -> "ConfigManager":
        """Load the config file. If missing and ``create_if_missing``, initialize
        with defaults (still call ``save()`` to persist). Otherwise raise.
        """
        if not self._path.is_file():
            if create_if_missing:
                self._loaded = True
                self._dirty = True
                return self
            raise ConfigNotFoundError(
                f"No config file found at {self._path}. Run `findref setup` first."
            )
        with self._path.open("rb") as f:
            data = _toml_reader.load(f)

        self._meta = data.get("meta", {"version": __version__, "created_at": datetime.now().isoformat()})

        defs = data.get("defaults", {})
        self._defaults = Defaults(
            openalex_mailto=str(defs.get("openalex_mailto", DEFAULT_OPENALEX_MAILTO)),
            request_delay=float(defs.get("request_delay", DEFAULT_REQUEST_DELAY)),
            per_page=int(defs.get("per_page", DEFAULT_PER_PAGE)),
            year_from=int(defs.get("year_from", DEFAULT_YEAR_FROM)),
            year_to=int(defs.get("year_to", DEFAULT_YEAR_TO)),
            language=str(defs.get("language", DEFAULT_LANGUAGE)),
            cache_ttl=int(defs.get("cache_ttl", 86400)),
            cache_enabled=bool(defs.get("cache_enabled", True)),
            log_level=str(defs.get("log_level", "INFO")),
            scimago_path=str(defs.get("scimago_path", "")),
            output_dir=str(defs.get("output_dir", "")),
            auto_name=bool(defs.get("auto_name", False)),
            openalex_mailto_pool=str(defs.get("openalex_mailto_pool", "")),
            openalex_auto_rotate=bool(defs.get("openalex_auto_rotate", False)),
            use_issn_filter=bool(defs.get("use_issn_filter", False)),
            issn_subject_areas=str(defs.get("issn_subject_areas", "")),
            issn_quartiles=str(defs.get("issn_quartiles", "")),
            issn_include_unranked=bool(defs.get("issn_include_unranked", True)),
        )

        accounts_data = data.get("accounts", {})
        self._accounts = {
            name: Account.from_dict(name, acc) for name, acc in accounts_data.items()
        }

        current = data.get("current", {}).get("account")
        self._current_account = current if current in self._accounts else None

        self._loaded = True
        self._dirty = False
        return self

    def save(self) -> "ConfigManager":
        """Persist the config to disk."""
        if not self._loaded:
            self.load(create_if_missing=True)

        data: Dict[str, Any] = {
            "meta": {
                "version": __version__,
                "created_at": self._meta.get("created_at", datetime.now().isoformat()),
                "updated_at": datetime.now().isoformat(),
            },
            "defaults": asdict(self._defaults),
            "current": {"account": self._current_account} if self._current_account else {},
            "accounts": {name: acc.to_dict() for name, acc in self._accounts.items()},
        }

        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("wb") as f:
            tomli_w.dump(data, f)
        self._dirty = False
        return self

    # ------------------------------------------------------------------ #
    # Account management
    # ------------------------------------------------------------------ #

    def list_accounts(self) -> List[Account]:
        if not self._loaded:
            self.load(create_if_missing=True)
        return list(self._accounts.values())

    def get_account(self, name: str) -> Account:
        if not self._loaded:
            self.load(create_if_missing=True)
        if name not in self._accounts:
            raise AccountNotFoundError(name)
        return self._accounts[name]

    def add_account(self, account: Account) -> None:
        """Add or replace an account by ``account.name``."""
        if not account.name:
            raise ValueError("account.name must be set")
        if not self._loaded:
            self.load(create_if_missing=True)
        self._accounts[account.name] = account
        self._dirty = True
        if self._current_account is None:
            self._current_account = account.name

    def remove_account(self, name: str) -> bool:
        """Remove an account. Returns True if removed, False if not found."""
        if not self._loaded:
            self.load(create_if_missing=True)
        if name not in self._accounts:
            return False
        del self._accounts[name]
        if self._current_account == name:
            self._current_account = next(iter(self._accounts), None)
        self._dirty = True
        return True

    def use_account(self, name: str) -> Account:
        """Switch the current account to ``name``."""
        if not self._loaded:
            self.load(create_if_missing=True)
        if name not in self._accounts:
            raise AccountNotFoundError(name)
        self._current_account = name
        self._dirty = True
        return self._accounts[name]

    def get_current_account(self) -> Optional[Account]:
        if not self._loaded:
            try:
                self.load(create_if_missing=False)
            except ConfigNotFoundError:
                return None
        if not self._current_account:
            return None
        return self._accounts.get(self._current_account)

    # ------------------------------------------------------------------ #
    # OpenAlex mailto pool (collect from all accounts + defaults + env)
    # ------------------------------------------------------------------ #

    def get_openalex_mailto_pool(self, defaults: Optional["Defaults"] = None) -> List[str]:
        """Collect all OpenAlex mailtos available for rotation.

        Pass ``defaults`` (e.g. the result of ``resolve_defaults()``) so that a
        project-local ``.findref.yaml`` can override ``openalex_mailto`` and
        ``openalex_mailto_pool``; without it the user config is used.

        Sources (deduplicated, order preserved):
          1. Current account's openalex_mailto (first in pool — preferred)
          2. All OTHER accounts' openalex_mailto (rotation candidates)
          3. ``openalex_mailto_pool`` from defaults (extra mailtos)
          4. ``openalex_mailto`` from defaults
          5. ``FINDREF_OPENALEX_MAILTO_POOL`` and ``FINDREF_OPENALEX_MAILTO`` env vars

        Empty mailtos and the default placeholder ``researcher@example.com``
        are skipped (they don't help with rate limits).

        Returns:
            List of mailtos. Empty list = no usable mailtos (will fall back
            to DEFAULT_OPENALEX_MAILTO at request time).
        """
        if not self._loaded:
            try:
                self.load(create_if_missing=False)
            except ConfigNotFoundError:
                pass

        defs = defaults if defaults is not None else self._defaults
        pool: List[str] = []
        seen: set[str] = set()

        def _add(mailto: str) -> None:
            mailto = (mailto or "").strip().lower()
            if not mailto:
                return
            if mailto == DEFAULT_OPENALEX_MAILTO:
                return  # placeholder doesn't help with rate limits
            if mailto in seen:
                return
            seen.add(mailto)
            pool.append(mailto)

        # 1. Current account first
        current = self.get_current_account()
        if current:
            _add(current.openalex_mailto)

        # 2. All other accounts
        for acc in self._accounts.values():
            if acc.name == (current.name if current else ""):
                continue
            _add(acc.openalex_mailto)

        # 3. Defaults.openalex_mailto_pool (comma-separated)
        if defs.openalex_mailto_pool:
            for m in defs.openalex_mailto_pool.split(","):
                _add(m)

        # 4. Defaults.openalex_mailto (single)
        _add(defs.openalex_mailto)

        # 5. Env var (highest priority, appended last so it's tried first on round-robin)
        env_pool = os.environ.get("FINDREF_OPENALEX_MAILTO_POOL", "")
        if env_pool:
            for m in env_pool.split(","):
                _add(m)

        # Also check single env var
        env_single = os.environ.get("FINDREF_OPENALEX_MAILTO", "")
        if env_single:
            _add(env_single)

        return pool

    def is_openalex_auto_rotate(self, defaults: Optional["Defaults"] = None) -> bool:
        """Whether to rotate mailtos proactively (True) or only on 429 (False).

        Priority: ``FINDREF_OPENALEX_AUTO_ROTATE`` env var, then ``defaults``
        (project-merged, if given), then the user config.
        """
        env = os.environ.get("FINDREF_OPENALEX_AUTO_ROTATE", "")
        if env:
            return env.lower() in {"true", "1", "yes", "y"}
        return (defaults if defaults is not None else self._defaults).openalex_auto_rotate

    # ------------------------------------------------------------------ #
    # Defaults
    # ------------------------------------------------------------------ #

    def get_defaults(self) -> Defaults:
        if not self._loaded:
            self.load(create_if_missing=True)
        return self._defaults

    def update_defaults(self, **kwargs: Any) -> None:
        if not self._loaded:
            self.load(create_if_missing=True)
        for k, v in kwargs.items():
            if v is not None and hasattr(self._defaults, k):
                setattr(self._defaults, k, v)
                self._dirty = True

    # ------------------------------------------------------------------ #
    # Effective settings (OpenAlex mailto)
    # ------------------------------------------------------------------ #

    def effective_credentials(self, defaults: Optional["Defaults"] = None) -> Dict[str, str]:
        """Return the settings that should be used RIGHT NOW.

        Only ``openalex_mailto`` is relevant (OpenAlex needs no API key).

        Priority (highest first):
          1. ``FINDREF_OPENALEX_MAILTO`` environment variable
          2. ``openalex_mailto`` set by a project-local ``.findref.yaml``
             (only when ``defaults`` is passed and differs from the user config)
          3. Current account's ``openalex_mailto``
          4. Defaults ``openalex_mailto``
          5. Placeholder ``DEFAULT_OPENALEX_MAILTO``
        """
        if not self._loaded:
            try:
                self.load(create_if_missing=False)
            except ConfigNotFoundError:
                pass

        current = self.get_current_account()
        defs = self._defaults

        project_mailto = ""
        if defaults is not None and defaults.openalex_mailto != defs.openalex_mailto:
            project_mailto = defaults.openalex_mailto  # set by the project-local file

        return {
            "openalex_mailto": os.environ.get("FINDREF_OPENALEX_MAILTO", "")
                               or project_mailto
                               or (current.openalex_mailto if current else "")
                               or defs.openalex_mailto
                               or DEFAULT_OPENALEX_MAILTO,
        }

    @property
    def path(self) -> Path:
        return self._path

    def is_dirty(self) -> bool:
        return self._dirty


# ---------------------------------------------------------------------- #
# Singleton helpers
# ---------------------------------------------------------------------- #

_singleton_lock = threading.Lock()
_singleton: Optional[ConfigManager] = None


def get_manager(path: Optional[Path] = None, *, reload: bool = False) -> ConfigManager:
    """Get the singleton ConfigManager. If ``reload`` or first call, loads from disk."""
    global _singleton
    with _singleton_lock:
        if _singleton is None or reload or path is not None:
            _singleton = ConfigManager(path=path)
            try:
                _singleton.load(create_if_missing=False)
            except ConfigNotFoundError:
                pass  # leaves _singleton._loaded = False; save() will create
        return _singleton


def reset_manager() -> None:
    """Reset the singleton (mainly for tests)."""
    global _singleton
    with _singleton_lock:
        _singleton = None
