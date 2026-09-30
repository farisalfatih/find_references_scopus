"""MailtoPool — rotate through multiple OpenAlex mailtos to avoid rate limits.

OpenAlex is free but applies per-mailto rate limits (the "polite pool").
By rotating through multiple mailtos, you can effectively multiply your
throughput N times, where N = number of unique mailtos in the pool.

Strategy:
  - **Round-robin** (auto-rotate=True): rotate to next mailto after each request.
  - **Reactive** (auto-rotate=False): keep using current mailto until a 429 is
    received, then mark it as "cooling down" for ``cooldown_seconds`` and switch.

The pool is thread-safe.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class _MailtoState:
    mailto: str
    request_count: int = 0
    last_used: float = 0.0
    cooldown_until: float = 0.0


@dataclass
class MailtoPool:
    """Round-robin / reactive pool of OpenAlex mailtos.

    Usage::

        pool = MailtoPool(["alice@univ.edu", "bob@univ.edu"], auto_rotate=True)
        mailto = pool.next()  # get the next mailto to use
        # ... make request ...
        # on 429:
        pool.mark_rate_limited(mailto)
        # next call to pool.next() will skip the rate-limited one
    """

    mailtos: List[str] = field(default_factory=list)
    auto_rotate: bool = False
    cooldown_seconds: float = 60.0  # how long to skip a rate-limited mailto

    _states: Dict[str, _MailtoState] = field(default_factory=dict, repr=False)
    _index: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: List[str] = []
        for m in self.mailtos:
            m_lower = m.strip().lower()
            if m_lower and m_lower not in seen:
                seen.add(m_lower)
                unique.append(m_lower)
        self.mailtos = unique
        self._states = {m: _MailtoState(mailto=m) for m in unique}

    def __len__(self) -> int:
        return len(self.mailtos)

    def is_empty(self) -> bool:
        return not self.mailtos

    # ------------------------------------------------------------------ #
    # Get next mailto
    # ------------------------------------------------------------------ #

    def next(self) -> Optional[str]:
        """Get the next mailto to use.

        Returns None if pool is empty.
        Skips mailtos that are in cooldown.
        """
        if not self.mailtos:
            return None

        with self._lock:
            now = time.time()
            n = len(self.mailtos)

            # Try up to N mailtos to find one not in cooldown
            for attempt in range(n):
                idx = self._index % n
                self._index += 1
                mailto = self.mailtos[idx]
                state = self._states[mailto]

                # Check cooldown
                if state.cooldown_until > now:
                    continue

                # Found a usable mailto
                state.request_count += 1
                state.last_used = now
                return mailto

            # All mailtos in cooldown — return the one with earliest cooldown end
            earliest = min(self._states.values(), key=lambda s: s.cooldown_until)
            earliest.request_count += 1
            earliest.last_used = now
            return earliest.mailto

    def current(self) -> Optional[str]:
        """Return the last-used mailto (without consuming next)."""
        if not self.mailtos:
            return None
        with self._lock:
            # Last index used = self._index - 1
            idx = (self._index - 1) % len(self.mailtos) if self._index > 0 else 0
            return self.mailtos[idx]

    # ------------------------------------------------------------------ #
    # Rate-limit handling
    # ------------------------------------------------------------------ #

    def mark_rate_limited(self, mailto: str, *, retry_after: Optional[float] = None) -> None:
        """Mark a mailto as rate-limited. It will be skipped for ``cooldown_seconds``."""
        mailto = mailto.strip().lower()
        with self._lock:
            if mailto not in self._states:
                return
            cooldown = retry_after if retry_after is not None else self.cooldown_seconds
            self._states[mailto].cooldown_until = time.time() + cooldown

    def mark_ok(self, mailto: str) -> None:
        """Mark a mailto as healthy (clear any cooldown)."""
        mailto = mailto.strip().lower()
        with self._lock:
            if mailto in self._states:
                self._states[mailto].cooldown_until = 0.0

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #

    def stats(self) -> Dict[str, Dict[str, object]]:
        """Return per-mailto stats for debugging."""
        with self._lock:
            now = time.time()
            return {
                m: {
                    "request_count": s.request_count,
                    "last_used": s.last_used,
                    "in_cooldown": s.cooldown_until > now,
                    "cooldown_remaining": max(0.0, s.cooldown_until - now),
                }
                for m, s in self._states.items()
            }

    # ------------------------------------------------------------------ #
    # Mutators
    # ------------------------------------------------------------------ #

    def add(self, mailto: str) -> None:
        """Add a mailto to the pool (no-op if already present)."""
        mailto = mailto.strip().lower()
        if not mailto:
            return
        with self._lock:
            if mailto not in self._states:
                self.mailtos.append(mailto)
                self._states[mailto] = _MailtoState(mailto=mailto)

    def remove(self, mailto: str) -> bool:
        """Remove a mailto. Returns True if removed."""
        mailto = mailto.strip().lower()
        with self._lock:
            if mailto not in self._states:
                return False
            self.mailtos = [m for m in self.mailtos if m != mailto]
            del self._states[mailto]
            # Reset index to avoid out-of-range
            if self._index >= len(self.mailtos):
                self._index = 0
            return True
