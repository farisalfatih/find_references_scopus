"""API clients subpackage.

Only OpenAlex is exposed as a search client. Scopus checker (for indexing
detection) lives in :mod:`find_references_scopus.core.scopus_checker`.
"""

from __future__ import annotations

from find_references_scopus.api.base import (
    BaseClient,
    ApiError,
    RateLimitError,
    AuthError,
    NotFoundError,
    NetworkError,
)
from find_references_scopus.api.openalex import OpenAlexClient

__all__ = [
    "BaseClient",
    "ApiError",
    "RateLimitError",
    "AuthError",
    "NotFoundError",
    "NetworkError",
    "OpenAlexClient",
]
