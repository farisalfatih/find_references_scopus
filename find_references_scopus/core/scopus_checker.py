"""Scopus indexing checker.

Uses a **SCImago local lookup**: the bundled ``scimagojr_*.json`` is indexed by
ISSN. It works offline, needs no API key, and gives quartile info
(Q1-Q4 / ``-`` for unranked). A journal listed in SCImago is treated as
Scopus-indexed (SCImago ranks Scopus-indexed sources).

Every ISSN of a journal (print AND electronic) is indexed, so a paper is found
no matter which of its journal's ISSNs OpenAlex reports.

OpenAlex is the only online API used by findref; this module makes no
network calls.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Set

from find_references_scopus.core.models import Paper
from find_references_scopus.core.scimago import (
    ScimagoJournal,
    build_issn_index,
    default_scimago_path,
    load_journals,
    normalize_issn,
)


_VALID_QUARTILES: Set[str] = {"Q1", "Q2", "Q3", "Q4", "-"}


class ScopusChecker:
    """Look up whether a journal/paper is indexed in Scopus, with quartile info."""

    _instance: Optional["ScopusChecker"] = None
    _lock = threading.Lock()

    def __init__(self, scimago_path: Optional[str] = None) -> None:
        self.scimago_path = scimago_path or self._find_default_scimago()
        self._journal_index: Optional[Dict[str, ScimagoJournal]] = None

    # ------------------------------------------------------------------ #
    # Singleton
    # ------------------------------------------------------------------ #

    @classmethod
    def get(cls, **kwargs: Any) -> "ScopusChecker":
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    # ------------------------------------------------------------------ #
    # SCImago local lookup
    # ------------------------------------------------------------------ #

    @staticmethod
    def _find_default_scimago() -> Optional[str]:
        """Find the SCImago JSON: user data dir first, then bundled."""
        found = default_scimago_path()
        return str(found) if found else None

    def _load_scimago(self) -> Dict[str, ScimagoJournal]:
        """Build (once) the index ``ISSN -> journal`` covering print + electronic ISSNs."""
        with self._lock:
            if self._journal_index is not None:
                return self._journal_index
            try:
                journals = load_journals(self.scimago_path) if self.scimago_path else ()
            except (FileNotFoundError, ValueError):
                journals = ()
            self._journal_index = build_issn_index(journals)
            return self._journal_index

    def lookup_issn(self, issn: str) -> Optional[ScimagoJournal]:
        """Return the SCImago journal that owns ``issn`` (any format), or None."""
        n = normalize_issn(issn)
        if not n:
            return None
        return self._load_scimago().get(n)

    def _lookup_scimago(self, issn: str) -> Optional[Dict[str, Any]]:
        """Dict view of :meth:`lookup_issn` (kept for backward compatibility)."""
        j = self.lookup_issn(issn)
        if j is None:
            return None
        return {
            "quartile": j.quartile,
            "open_access": j.open_access,
            "title": j.title,
            "subject_area": list(j.subject_areas),
        }

    # ------------------------------------------------------------------ #
    # Main API
    # ------------------------------------------------------------------ #

    @staticmethod
    def _paper_issns(paper: Paper) -> List[str]:
        """Every ISSN known for the paper's journal, normalized and de-duplicated."""
        out: List[str] = []
        for raw in (*paper.issns, paper.issn_l, paper.issn_electronic, paper.issn_print):
            n = normalize_issn(raw)
            if n and n not in out:
                out.append(n)
        return out

    def annotate(self, paper: Paper) -> Paper:
        """Annotate ``paper`` in-place with ``quartile`` and ``scopus_indexed``.
        Returns the same paper.

        Strategy:
          1. If the paper already carries a valid quartile, trust it.
          2. Otherwise look up all of its journal's ISSNs in the SCImago data.
        """
        if paper.quartile and paper.quartile.upper() in _VALID_QUARTILES:
            paper.scopus_indexed = True
            return paper

        for issn in self._paper_issns(paper):
            journal = self.lookup_issn(issn)
            if journal:
                paper.scopus_indexed = True
                paper.quartile = journal.quartile or paper.quartile
                return paper

        paper.scopus_indexed = False
        return paper

    # ------------------------------------------------------------------ #
    # Bulk operations
    # ------------------------------------------------------------------ #

    def annotate_all(self, papers: list[Paper]) -> dict[str, int]:
        """Annotate every paper in ``papers``. Returns stats dict."""
        stats = {"total": 0, "scopus": 0, "non_scopus": 0, "with_quartile": 0}
        for p in papers:
            self.annotate(p)
            stats["total"] += 1
            if p.scopus_indexed:
                stats["scopus"] += 1
                if p.quartile and p.quartile.upper() in {"Q1", "Q2", "Q3", "Q4"}:
                    stats["with_quartile"] += 1
            else:
                stats["non_scopus"] += 1
        return stats


def is_valid_quartile(q: str) -> bool:
    return q.upper() in _VALID_QUARTILES
