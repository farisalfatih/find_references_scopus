"""Find-Refs: Professional CLI for academic reference discovery, filtering, and export.

A focused tool for researchers and AI agents that need to:
  - Search academic papers via OpenAlex (the only online API used; no API key needed)
  - Detect whether a paper is indexed in Scopus, offline via bundled SCImago data (Q1/Q2/Q3/Q4 tier)
  - Filter and remove unsuitable references (year, citations, journal tier, keywords)
  - Export curated reference lists to BibTeX / RIS / CSV / JSONL

Designed to be agent-friendly: every command supports ``--json`` for structured output
and returns deterministic exit codes (0=ok, 1=error, 2=no-result, 3=rate-limited,
4=auth-failed, 5=network-error).
"""

from __future__ import annotations

__version__ = "2.0.0"
__app_name__ = "findref"
__display_name__ = "Find-Refs"
__author__ = "Find-Refs Team"
__license__ = "MIT"

# Exit codes (used by all CLI commands — agents should rely on these)
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NO_RESULT = 2
EXIT_RATE_LIMITED = 3
EXIT_AUTH_FAILED = 4
EXIT_NETWORK_ERROR = 5
EXIT_CONFIG_ERROR = 6
EXIT_INTERRUPTED = 130
