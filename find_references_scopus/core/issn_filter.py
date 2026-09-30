"""SCImago-based ISSN filter for OpenAlex search.

Reads the SCImago journal data and produces the set of ISSNs of every journal
that matches:

  - Subject area (e.g. "Computer Science", "Medicine")
  - Quartile (Q1, Q2, Q3, Q4, "-" for unranked)

Both ISSNs of a journal (print and electronic) are included, because SCImago's
print/electronic labels are unreliable (see :mod:`find_references_scopus.core.scimago`)
and OpenAlex may know a journal under either one.

``findref search`` uses the result to restrict OpenAlex results to journals that
are indexed in Scopus/SCImago:

  * up to :data:`OPENALEX_MAX_OR_VALUES` ISSNs -> sent to OpenAlex as one
    ``primary_location.source.issn:a|b|c`` filter (exact, server-side);
  * more than that (the usual case for a whole subject area) -> OpenAlex is
    scanned page by page and each result is kept only if its journal ISSN is in
    :attr:`IssnFilter.issn_set` (see ``OpenAlexClient.search``). Nothing is
    silently truncated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Set

from find_references_scopus.core.scimago import (
    ScimagoJournal,
    default_scimago_path,
    load_journals,
    normalize_issn,
    split_issns,
)
from find_references_scopus.core.scopus_checker import is_valid_quartile

# OpenAlex allows at most 100 values joined with "|" inside a single filter.
OPENALEX_MAX_OR_VALUES = 100


@dataclass
class IssnFilter:
    """A filter applied to SCImago journal data to produce a list of ISSNs.

    Attributes:
        subject_areas: Subject area names (case-insensitive). Empty = all.
        quartiles: Quartiles to include (Q1, Q2, Q3, Q4, "-"). Empty = all.
        include_unranked: Whether to include journals with quartile "-".
        issns: Resolved ISSNs (populated by ``build()``), print + electronic.
        stats: Counters from the last ``build()``.
    """

    subject_areas: Set[str] = field(default_factory=set)
    quartiles: Set[str] = field(default_factory=set)
    include_unranked: bool = True
    issns: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Build from SCImago JSON
    # ------------------------------------------------------------------ #

    def build(self, scimago_path: str | Path) -> "IssnFilter":
        """Load the SCImago JSON and populate ``self.issns``.

        Subject areas are matched exactly (case-insensitive) against each of a
        journal's subject areas. A term that is not an existing subject area at
        all falls back to a substring match and is reported in
        ``stats["unmatched_subject_areas"]``.

        Raises:
            FileNotFoundError: the SCImago file does not exist.
        """
        journals = load_journals(scimago_path)

        sa_filter = {s.strip().lower() for s in self.subject_areas if s.strip()}
        q_filter = {q.strip().upper() for q in self.quartiles if q.strip()}

        known_areas = {a.lower() for j in journals for a in j.subject_areas}
        exact_terms = {t for t in sa_filter if t in known_areas}
        fuzzy_terms = sa_filter - exact_terms

        seen: Set[str] = set()
        issns: List[str] = []
        stats: Dict[str, Any] = {
            "total_journals": len(journals),
            "after_subject_filter": 0,
            "after_quartile_filter": 0,
            "with_issn": 0,
            "unique_issns": 0,
            "unmatched_subject_areas": sorted(fuzzy_terms),
        }

        for j in journals:
            if sa_filter and not self._subject_matches(j, exact_terms, fuzzy_terms):
                continue
            stats["after_subject_filter"] += 1

            if not self._quartile_matches(j.quartile, q_filter):
                continue
            stats["after_quartile_filter"] += 1

            if not j.issns:
                continue
            stats["with_issn"] += 1

            for issn in j.issns:
                if issn not in seen:
                    seen.add(issn)
                    issns.append(issn)

        stats["unique_issns"] = len(issns)
        self.issns = issns
        self.stats = stats
        return self

    @staticmethod
    def _subject_matches(j: ScimagoJournal, exact: Set[str], fuzzy: Set[str]) -> bool:
        areas = [a.lower() for a in j.subject_areas]
        if exact and any(a in exact for a in areas):
            return True
        return bool(fuzzy) and any(t in a for t in fuzzy for a in areas)

    def _quartile_matches(self, quartile: str, q_filter: Set[str]) -> bool:
        if not quartile:
            # No quartile info: only kept when no quartile filter is active.
            return not q_filter
        if quartile == "-":
            if not self.include_unranked:
                return False
            return not q_filter or "-" in q_filter
        return not q_filter or quartile in q_filter

    # ------------------------------------------------------------------ #
    # Use of the resolved list
    # ------------------------------------------------------------------ #

    @property
    def issn_set(self) -> FrozenSet[str]:
        """The resolved ISSNs as a set (for fast membership tests)."""
        return frozenset(self.issns)

    def to_batches(self, batch_size: int = OPENALEX_MAX_OR_VALUES) -> List[List[str]]:
        """Split ISSNs into chunks of at most ``batch_size`` (OpenAlex OR limit)."""
        return [self.issns[i : i + batch_size] for i in range(0, len(self.issns), batch_size)]

    def describe(self) -> Dict[str, Any]:
        """Return a dict describing the current filter state (for CLI / JSON output)."""
        return {
            "subject_areas": sorted(self.subject_areas) if self.subject_areas else "(all)",
            "quartiles": sorted(self.quartiles) if self.quartiles else "(all)",
            "include_unranked": self.include_unranked,
            "issn_count": len(self.issns),
            "stats": self.stats,
        }

    def is_empty(self) -> bool:
        return not self.issns


# ---------------------------------------------------------------------- #
# Factory: build from config defaults
# ---------------------------------------------------------------------- #

def parse_csv_set(value: str) -> Set[str]:
    """``"a, b ,,c"`` -> ``{"a", "b", "c"}``."""
    return {s.strip() for s in (value or "").split(",") if s.strip()}


def parse_quartiles(value: str) -> Set[str]:
    """``"q1,Q2"`` -> ``{"Q1", "Q2"}``. ``""`` / ``"all"`` -> empty set (= all quartiles)."""
    parts = [q.strip().upper() for q in (value or "").split(",") if q.strip()]
    if not parts or "ALL" in parts:
        return set()
    return {p for p in parts if is_valid_quartile(p)}


def build_filter_from_defaults(
    *,
    use_issn_filter: bool,
    subject_areas: str = "",
    quartiles: str = "",
    include_unranked: bool = True,
    scimago_path: str = "",
) -> Optional[IssnFilter]:
    """Build an IssnFilter from config defaults.

    Returns None if ``use_issn_filter`` is False or if no SCImago JSON can be found.
    """
    if not use_issn_filter:
        return None

    if not scimago_path:
        found = default_scimago_path()
        if found is None:
            return None
        scimago_path = str(found)

    f = IssnFilter(
        subject_areas=parse_csv_set(subject_areas),
        quartiles=parse_quartiles(quartiles),
        include_unranked=include_unranked,
    )
    f.build(scimago_path)
    return f


# ---------------------------------------------------------------------- #
# List available subject areas / quartiles (for interactive setup)
# ---------------------------------------------------------------------- #

def list_subject_areas(scimago_path: str | Path) -> List[str]:
    """Return a sorted list of unique subject areas in the SCImago JSON."""
    try:
        journals = load_journals(scimago_path)
    except (FileNotFoundError, ValueError):
        return []
    return sorted({a for j in journals for a in j.subject_areas})


def list_quartiles(scimago_path: str | Path) -> List[str]:
    """Return a sorted list of unique quartiles in the SCImago JSON."""
    try:
        journals = load_journals(scimago_path)
    except (FileNotFoundError, ValueError):
        return []
    return sorted({j.quartile for j in journals if j.quartile})


__all__ = [
    "OPENALEX_MAX_OR_VALUES",
    "IssnFilter",
    "build_filter_from_defaults",
    "list_quartiles",
    "list_subject_areas",
    "normalize_issn",
    "parse_csv_set",
    "parse_quartiles",
    "split_issns",
]
