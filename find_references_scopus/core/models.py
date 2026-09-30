"""Core data models: ``Paper`` and ``ReferenceList``."""

from __future__ import annotations

import re
import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


# Regex DOI dari Crossref (registrant 4-9 digit)
DOI_REGEX = re.compile(r"10\.\d{4,9}/[^\s\"<>{}|\\^`]+")


@dataclass
class Paper:
    """A normalized academic paper record.

    All fields are optional except ``title`` — different APIs provide different
    metadata completeness, and our pipeline must tolerate missing fields.
    """

    doi: str = ""
    title: str = ""
    authors: List[str] = field(default_factory=list)
    journal: str = ""
    publisher: str = ""
    year: Optional[int] = None
    pub_date: str = ""
    month: str = ""
    volume: str = ""
    issue: str = ""
    first_page: str = ""
    last_page: str = ""
    # ISSNs of the journal. OpenAlex reports them in no fixed order, so
    # ``issn_electronic`` / ``issn_print`` are simply the 1st / 2nd ISSN it listed.
    # Use ``issns`` (all of them) for lookups and matching.
    issn_electronic: str = ""
    issn_print: str = ""
    issn_l: str = ""  # linking ISSN
    issns: List[str] = field(default_factory=list)
    abstract: str = ""
    language: str = "en"
    cited_by_count: int = 0
    is_open_access: bool = False
    open_access_url: str = ""
    open_access_status: str = ""
    quartile: str = ""  # Q1, Q2, Q3, Q4, "-" (unranked Scopus), "" (not in Scopus)
    scopus_indexed: bool = False
    scopus_eid: str = ""
    subjects: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    source: str = ""  # "openalex" (or "manual")
    url: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)  # original API payload (debugging)

    # ------------------------------------------------------------------ #
    # Computed
    # ------------------------------------------------------------------ #

    def citation_key(self, index: int = 0) -> str:
        """Generate a stable BibTeX citation key.

        Format: ``<lastname><year>_<hash5>`` where hash is derived from DOI
        (so the same paper always gets the same key regardless of dataset order).
        """
        first_author = self.authors[0] if self.authors else ""
        last_name = _extract_last_name(first_author)
        last_name_clean = re.sub(r"[^a-zA-Z]", "", last_name).lower() or "unknown"

        year = self.year or (self.pub_date[:4] if self.pub_date else "nodate")

        doi = self.doi.strip().lower()
        if doi:
            suffix = hashlib.md5(doi.encode("utf-8")).hexdigest()[:5]
        else:
            suffix = f"idx{index}"

        return f"{last_name_clean}{year}_{suffix}"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Drop empty raw to keep output compact
        if not d.get("raw"):
            d.pop("raw", None)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Paper":
        """Build from a dict (e.g. JSON or API response)."""
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        kwargs: Dict[str, Any] = {}
        for k, v in data.items():
            if k in known:
                kwargs[k] = v
        if "raw" not in kwargs:
            kwargs["raw"] = data  # preserve original
        return cls(**kwargs)

    # ------------------------------------------------------------------ #
    # Convenience
    # ------------------------------------------------------------------ #

    @property
    def pages(self) -> str:
        if self.first_page and self.last_page and self.first_page != self.last_page:
            return f"{self.first_page}--{self.last_page}"
        return self.first_page or ""

    @property
    def short_authors(self) -> str:
        """First author + et al. format."""
        if not self.authors:
            return "Unknown"
        if len(self.authors) == 1:
            return _extract_last_name(self.authors[0])
        if len(self.authors) == 2:
            return f"{_extract_last_name(self.authors[0])} and {_extract_last_name(self.authors[1])}"
        return f"{_extract_last_name(self.authors[0])} et al."

    def matches_doi(self, doi: str) -> bool:
        return bool(self.doi) and self.doi.lower().strip() == doi.lower().strip()


@dataclass
class ReferenceList:
    """A collection of papers grouped by search group / topic.

    Mirrors the legacy JSON shape ``{group_name: [paper, ...]}`` for backward
    compat with the old pipeline outputs.
    """

    groups: Dict[str, List[Paper]] = field(default_factory=dict)

    def add(self, group: str, paper: Paper) -> None:
        self.groups.setdefault(group, []).append(paper)

    def flatten(self) -> List[Paper]:
        out: List[Paper] = []
        for papers in self.groups.values():
            out.extend(papers)
        return out

    def total(self) -> int:
        return sum(len(p) for p in self.groups.values())

    def to_dict(self) -> Dict[str, Any]:
        return {g: [p.to_dict() for p in ps] for g, ps in self.groups.items()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReferenceList":
        rl = cls()
        for group, papers in data.items():
            if isinstance(papers, list):
                for p in papers:
                    if isinstance(p, dict):
                        rl.add(group, Paper.from_dict(p))
                    elif isinstance(p, Paper):
                        rl.add(group, p)
        return rl


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #

def _extract_last_name(author: str) -> str:
    """Extract last name from ``"First Middle Last"`` or ``"Last, First"`` or ``"Last F."``.

    For "Last, First" format, returns the part before comma.
    For "First Middle Last" format, returns the last word — UNLESS the last word
    is a single letter (initial), in which case the previous word is used.
    For "Last F." (academic citation format), returns "Last".
    """
    author = (author or "").strip().rstrip(",.")
    if not author:
        return ""
    if "," in author:
        return author.split(",", 1)[0].strip().rstrip(",.")
    parts = author.split()
    if not parts:
        return ""
    # If last "word" is a single letter (initial like "J."), use the previous word
    last_word = parts[-1].rstrip(",.")
    if len(last_word) == 1 and len(parts) > 1:
        return parts[-2].rstrip(",.")
    return last_word


def extract_dois(text: str) -> List[str]:
    """Extract all DOI strings from a free-text blob."""
    matches = DOI_REGEX.findall(text)
    seen: set[str] = set()
    out: List[str] = []
    for m in matches:
        doi = m.rstrip(".,;:)]}\"'")
        if doi.lower() not in seen:
            seen.add(doi.lower())
            out.append(doi)
    return out
