"""Filter rules engine — remove unsuitable references.

A rule is a Python dataclass with a ``keep(paper)`` method. The engine runs all
rules in sequence: a paper survives only if ALL rules return True.

Built-in rules cover the common cases the user requested:

  - YearFilter       : ``--min-year 2020 --max-year 2026``
  - CitationFilter   : ``--min-citations 5``
  - ScopusOnlyFilter : ``--scopus-only``
  - QuartileFilter   : ``--quartile Q1,Q2``
  - KeywordBlacklist : ``--exclude-keywords preprint,survey``
  - KeywordWhitelist : ``--include-keywords deep learning``
  - OpenAccessFilter : ``--open-access-only``
  - LanguageFilter   : ``--language en,fr``
  - DuplicateFilter  : by DOI + by fuzzy title

Each rule is also serializable to JSON so agent callers can describe their
filter strategy programmatically.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional, Sequence, Set

from find_references_scopus.core.models import Paper
from find_references_scopus.core.scopus_checker import is_valid_quartile


@dataclass
class Rule:
    """Base interface. Subclasses implement ``keep``."""

    name: str = "rule"

    def keep(self, paper: Paper) -> bool:  # pragma: no cover
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, **self.__dict__}


@dataclass
class YearFilter(Rule):
    name: str = "year"
    min_year: Optional[int] = None
    max_year: Optional[int] = None

    def keep(self, paper: Paper) -> bool:
        y = paper.year
        if y is None:
            return False  # drop unknown years by default
        if self.min_year is not None and y < self.min_year:
            return False
        if self.max_year is not None and y > self.max_year:
            return False
        return True


@dataclass
class CitationFilter(Rule):
    name: str = "citations"
    min_citations: int = 0

    def keep(self, paper: Paper) -> bool:
        return paper.cited_by_count >= self.min_citations


@dataclass
class ScopusOnlyFilter(Rule):
    name: str = "scopus_only"

    def keep(self, paper: Paper) -> bool:
        return bool(paper.scopus_indexed)


@dataclass
class QuartileFilter(Rule):
    name: str = "quartile"
    allowed: Set[str] = field(default_factory=lambda: {"Q1", "Q2", "Q3", "Q4"})
    include_unranked: bool = True

    def keep(self, paper: Paper) -> bool:
        q = (paper.quartile or "").strip().upper()
        if not q:
            return False
        if q == "-":
            return self.include_unranked
        if not is_valid_quartile(q):
            return False
        return q in self.allowed


@dataclass
class KeywordBlacklist(Rule):
    name: str = "exclude_keywords"
    keywords: List[str] = field(default_factory=list)
    fields: List[str] = field(default_factory=lambda: ["title", "abstract", "keywords"])

    def keep(self, paper: Paper) -> bool:
        if not self.keywords:
            return True
        haystack = " ".join(
            str(getattr(paper, f, "") or "") for f in self.fields
        ).lower()
        haystack = _normalize(haystack)
        for kw in self.keywords:
            kw_n = _normalize(kw.lower())
            if kw_n in haystack:
                return False
        return True


@dataclass
class KeywordWhitelist(Rule):
    name: str = "include_keywords"
    keywords: List[str] = field(default_factory=list)
    fields: List[str] = field(default_factory=lambda: ["title", "abstract", "keywords"])

    def keep(self, paper: Paper) -> bool:
        if not self.keywords:
            return True
        haystack = _normalize(" ".join(
            str(getattr(paper, f, "") or "") for f in self.fields
        ).lower())
        return any(_normalize(kw.lower()) in haystack for kw in self.keywords)


@dataclass
class OpenAccessFilter(Rule):
    name: str = "open_access_only"

    def keep(self, paper: Paper) -> bool:
        return bool(paper.is_open_access)


@dataclass
class LanguageFilter(Rule):
    name: str = "language"
    allowed: Set[str] = field(default_factory=lambda: {"en"})

    def keep(self, paper: Paper) -> bool:
        if not paper.language:
            return True  # unknown language — don't drop
        return paper.language.lower() in self.allowed


@dataclass
class DOIBlacklist(Rule):
    name: str = "exclude_dois"
    dois: Set[str] = field(default_factory=set)

    def keep(self, paper: Paper) -> bool:
        if not paper.doi:
            return True
        return paper.doi.lower().strip() not in self.dois


@dataclass
class DOIWhitelist(Rule):
    """KEEP only the listed DOIs (intersection)."""
    name: str = "include_dois"
    dois: Set[str] = field(default_factory=set)

    def keep(self, paper: Paper) -> bool:
        if not self.dois:
            return True
        if not paper.doi:
            return False
        return paper.doi.lower().strip() in self.dois


# ---------------------------------------------------------------------- #
# Engine
# ---------------------------------------------------------------------- #

@dataclass
class FilterEngine:
    """Apply a list of rules to a list of papers."""

    rules: List[Rule] = field(default_factory=list)

    def add(self, rule: Rule) -> "FilterEngine":
        self.rules.append(rule)
        return self

    def keep(self, paper: Paper) -> bool:
        return all(rule.keep(paper) for rule in self.rules)

    def apply(self, papers: Iterable[Paper]) -> tuple[list[Paper], list[Paper]]:
        """Returns (kept, removed)."""
        kept: list[Paper] = []
        removed: list[Paper] = []
        for p in papers:
            if self.keep(p):
                kept.append(p)
            else:
                removed.append(p)
        return kept, removed

    def describe(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.rules]


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #

def _normalize(text: str) -> str:
    """Lowercase + NFKC normalize + collapse whitespace + strip non-alphanumeric."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[\-_/]+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def build_engine_from_cli(
    *,
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
    min_citations: Optional[int] = None,
    scopus_only: bool = False,
    quartile: Optional[str] = None,
    include_unranked: bool = True,
    exclude_keywords: Optional[str] = None,
    include_keywords: Optional[str] = None,
    open_access_only: bool = False,
    language: Optional[str] = None,
    exclude_dois: Optional[Sequence[str]] = None,
    include_dois: Optional[Sequence[str]] = None,
) -> FilterEngine:
    """Convenience factory to build a FilterEngine from CLI flags."""
    eng = FilterEngine()

    if min_year is not None or max_year is not None:
        eng.add(YearFilter(min_year=min_year, max_year=max_year))

    if min_citations is not None and min_citations > 0:
        eng.add(CitationFilter(min_citations=min_citations))

    if scopus_only:
        eng.add(ScopusOnlyFilter())

    if quartile:
        parts = parse_csv(quartile.upper())
        if parts and "ALL" not in parts:
            allowed = {p for p in parts if is_valid_quartile(p)}
            if allowed:
                eng.add(QuartileFilter(allowed=allowed, include_unranked=include_unranked))

    if exclude_keywords:
        eng.add(KeywordBlacklist(keywords=parse_csv(exclude_keywords)))

    if include_keywords:
        eng.add(KeywordWhitelist(keywords=parse_csv(include_keywords)))

    if open_access_only:
        eng.add(OpenAccessFilter())

    if language:
        eng.add(LanguageFilter(allowed=set(parse_csv(language))))

    if exclude_dois:
        eng.add(DOIBlacklist(dois={d.lower().strip() for d in exclude_dois}))

    if include_dois:
        eng.add(DOIWhitelist(dois={d.lower().strip() for d in include_dois}))

    return eng
