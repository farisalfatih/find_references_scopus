"""HTTP cache layer using ``requests-cache``.

Provides a single ``get_session()`` factory that returns a session with:
  - Persistent SQLite cache in the findref cache folder (``findref cache stats`` prints the path)
  - Auto-retry with exponential backoff on 429 / 5xx (handled in BaseClient)

Note: ``requests-ratelimiter`` was removed in v2.0.1 due to API breaking changes
in ``pyrate-limiter`` v4.x. Rate limiting is now handled via per-request ``time.sleep``
in :mod:`find_references_scopus.api.base`.
"""

from __future__ import annotations

import threading
from typing import Optional

from requests import Session
from requests_cache import CacheMixin, SQLiteCache

from find_references_scopus.config.defaults import get_cache_dir


class CachedSession(CacheMixin, Session):
    """Session with persistent SQLite cache."""


_session: Optional[CachedSession] = None
_session_lock = threading.Lock()


def get_session(*, cache_ttl: int = 86400, ignore_cache: bool = False) -> CachedSession:
    """Get a shared session instance.

    Args:
        cache_ttl: Cache expiration in seconds (default 24h).
        ignore_cache: If True, force-refresh (still writes to cache).
    """
    global _session
    with _session_lock:
        if _session is None:
            cache_path = str(get_cache_dir() / "http_cache.sqlite")
            _session = CachedSession(
                cache_name=cache_path,
                expire_after=cache_ttl,
                stale_if_error=True,
            )

        if ignore_cache:
            try:
                _session.cache.clear()  # type: ignore[attr-defined]
            except Exception:
                pass
        return _session


def clear_cache() -> int:
    """Wipe the HTTP cache. Returns number of entries removed."""
    s = get_session()
    try:
        count = len(s.cache.responses)  # type: ignore[attr-defined]
        s.cache.clear()  # type: ignore[attr-defined]
        return count
    except Exception:
        return 0
