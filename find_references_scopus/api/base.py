"""Base API client — common retry/cache/network plumbing."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from find_references_scopus import (
    __version__,
    EXIT_AUTH_FAILED,
    EXIT_NETWORK_ERROR,
    EXIT_RATE_LIMITED,
)
from find_references_scopus.utils.cache import get_session


class ApiError(Exception):
    """Generic API error."""
    exit_code: int = 1


class NetworkError(ApiError):
    exit_code = EXIT_NETWORK_ERROR


class RateLimitError(ApiError):
    exit_code = EXIT_RATE_LIMITED


class AuthError(ApiError):
    exit_code = EXIT_AUTH_FAILED


class NotFoundError(ApiError):
    """Resource not found (404)."""


class BaseClient:
    """Common HTTP plumbing for all API clients."""

    name: str = "base"
    base_url: str = ""
    default_headers: Dict[str, str] = {}

    def __init__(
        self,
        *,
        mailto: Optional[str] = None,
        rate_limit_delay: float = 1.0,
        timeout: int = 30,
    ) -> None:
        self.mailto = mailto
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout

    # ------------------------------------------------------------------ #
    # HTTP request wrapper with retry
    # ------------------------------------------------------------------ #

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        retries: int = 3,
    ) -> Dict[str, Any]:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        h = {**self.default_headers, **(headers or {})}
        if self.mailto and self.name == "openalex":
            # Polite pool: send User-Agent + mailto
            h["User-Agent"] = f"findref/{__version__} (mailto:{self.mailto})"

        session = get_session()
        last_err: Optional[Exception] = None
        for attempt in range(retries):
            try:
                resp = session.request(
                    method,
                    url,
                    params=params,
                    headers=h,
                    json=json_body,
                    timeout=self.timeout,
                )
            except Exception as e:
                last_err = e
                time.sleep(min(2 ** attempt, 8))
                continue

            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError:
                    return {"_raw_text": resp.text}

            if resp.status_code == 404:
                raise NotFoundError(f"{self.name}: 404 not found at {url}")

            if resp.status_code == 401 or resp.status_code == 403:
                raise AuthError(f"{self.name}: auth failed ({resp.status_code})")

            if resp.status_code == 429:
                # Rate-limited — wait and retry
                wait = float(resp.headers.get("Retry-After", "2"))
                time.sleep(min(wait, 60))
                last_err = RateLimitError(f"{self.name}: rate limited")
                continue

            if 500 <= resp.status_code < 600:
                last_err = ApiError(f"{self.name}: server error {resp.status_code}")
                time.sleep(min(2 ** attempt, 8))
                continue

            # Other 4xx
            raise ApiError(f"{self.name}: HTTP {resp.status_code} — {resp.text[:300]}")

        if isinstance(last_err, RateLimitError):
            raise last_err
        if isinstance(last_err, AuthError):
            raise last_err
        if last_err:
            raise NetworkError(f"{self.name}: network error after {retries} retries: {last_err}")
        raise ApiError(f"{self.name}: unknown failure")

    # ------------------------------------------------------------------ #
    # Subclasses implement these
    # ------------------------------------------------------------------ #

    def search(self, query: str, **kwargs: Any) -> list[Dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError

    def fetch_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError
