"""Shared helpers for the SCImago journal data (bundled JSON).

Everything that reads ``scimagojr_*.json`` goes through this module, so the
ISSN filter (:mod:`.issn_filter`), the Scopus checker (:mod:`.scopus_checker`)
and the ``findref issn`` command always interpret the file the same way.

Bundled file format (one object per journal)::

    {
      "journal": "Nature Reviews Molecular Cell Biology",
      "issn_print": "1471-0072",
      "issn_electronic": "1471-0080",
      "quartile": "Q1",
      "open_access": "No",
      "subject_area": ["Biochemistry, Genetics and Molecular Biology"],
      "sub_category": ["Cell Biology", "Molecular Biology"]
    }

Important: SCImago lists a journal's ISSNs in no particular order, so the
labels ``issn_print`` / ``issn_electronic`` in the file are NOT reliable
(e.g. CA - A Cancer Journal for Clinicians has them swapped, and about a third
of the journals have only one ISSN). findref therefore treats every ISSN of a
journal as equivalent and never relies on the print/electronic label.

Older / alternative layouts are still understood: a dict keyed by subject
area (``{"Computer Science": [journal, ...]}``), ``title`` instead of
``journal``, ``Issn`` / ``issn`` / ``issn_l`` keys, and comma-separated ISSNs.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

_ISSN_RE = re.compile(r"(\d{4})-?(\d{3}[\dXx])")

# Keys that may hold an ISSN, in order of preference.
_ISSN_KEYS = ("issn_electronic", "issn_print", "issn_l", "issn", "Issn")


# ---------------------------------------------------------------------- #
# ISSN helpers
# ---------------------------------------------------------------------- #

def normalize_issn(value: Any) -> str:
    """Return ``NNNN-NNNC`` (upper-case check digit) or ``""`` if ``value`` is not an ISSN.

    Accepts ``"0007-9235"``, ``"00079235"``, ``" 0007-923x "``. Only the format is
    checked, not the check digit.
    """
    if value is None:
        return ""
    m = _ISSN_RE.fullmatch(str(value).strip())
    if not m:
        return ""
    return f"{m.group(1)}-{m.group(2).upper()}"


def split_issns(value: Any) -> List[str]:
    """Split free text such as ``"1234-5678, 9876-5432"`` into normalized, unique ISSNs.

    Also accepts a list/tuple/set. Anything that is not a valid ISSN is dropped.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple, set, frozenset)):
        chunks: List[str] = []
        for v in value:
            chunks.extend(split_issns(v))
        return list(dict.fromkeys(chunks))
    out: List[str] = []
    for token in re.split(r"[,;|/\s]+", str(value)):
        n = normalize_issn(token)
        if n and n not in out:
            out.append(n)
    return out


# ---------------------------------------------------------------------- #
# Journal record
# ---------------------------------------------------------------------- #

@dataclass(frozen=True)
class ScimagoJournal:
    """One SCImago journal, normalized."""

    title: str = ""
    issns: Tuple[str, ...] = ()
    quartile: str = ""  # "Q1".."Q4", "-" (unranked), "" (unknown)
    open_access: str = ""
    subject_areas: Tuple[str, ...] = ()
    sub_categories: Tuple[str, ...] = ()
    extra: Dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "journal": self.title,
            "issns": list(self.issns),
            "quartile": self.quartile,
            "open_access": self.open_access,
            "subject_areas": list(self.subject_areas),
            "sub_categories": list(self.sub_categories),
        }


def _as_str_tuple(value: Any) -> Tuple[str, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(str(v).strip() for v in value if str(v).strip())
    return (str(value).strip(),)


def parse_journal(raw: Dict[str, Any], default_area: str = "") -> ScimagoJournal:
    """Normalize one raw journal dict (any supported layout)."""
    issns: List[str] = []
    for key in _ISSN_KEYS:
        for n in split_issns(raw.get(key)):
            if n not in issns:
                issns.append(n)

    areas = _as_str_tuple(raw.get("subject_area") or raw.get("Subject Area") or default_area)
    quartile = str(
        raw.get("quartile") or raw.get("Quartile") or raw.get("best_quartile") or ""
    ).strip().upper()

    return ScimagoJournal(
        title=str(raw.get("journal") or raw.get("title") or raw.get("Title") or "").strip(),
        issns=tuple(issns),
        quartile=quartile,
        open_access=str(raw.get("open_access") or raw.get("Open_Access") or "").strip(),
        subject_areas=areas,
        sub_categories=_as_str_tuple(raw.get("sub_category")),
    )


# ---------------------------------------------------------------------- #
# Loading (cached)
# ---------------------------------------------------------------------- #

_cache: Dict[Tuple[str, int, int], Tuple[ScimagoJournal, ...]] = {}
_cache_lock = threading.Lock()


def load_journals(path: str | Path) -> Tuple[ScimagoJournal, ...]:
    """Load and normalize a SCImago JSON file.

    Results are cached per (path, mtime, size), so several components in one
    command share a single parse of the ~12 MB bundled file.

    Raises:
        FileNotFoundError: the file does not exist.
        ValueError: the file is not valid JSON.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"SCImago JSON not found: {p}")

    st = p.stat()
    key = (str(p.resolve()), st.st_mtime_ns, st.st_size)
    with _cache_lock:
        cached = _cache.get(key)
        if cached is not None:
            return cached

    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"SCImago JSON is not valid JSON ({p}): {e}") from e

    journals: List[ScimagoJournal] = []
    if isinstance(data, list):
        for j in data:
            if isinstance(j, dict):
                journals.append(parse_journal(j))
    elif isinstance(data, dict):
        # Dict keyed by subject area: {area: [journal, ...]}
        for area, entries in data.items():
            if isinstance(entries, list):
                for j in entries:
                    if isinstance(j, dict):
                        journals.append(parse_journal(j, default_area=str(area)))

    result = tuple(journals)
    with _cache_lock:
        _cache.clear()  # keep at most one file in memory
        _cache[key] = result
    return result


def clear_cache() -> None:
    """Drop cached SCImago data (mainly for tests)."""
    with _cache_lock:
        _cache.clear()


def build_issn_index(journals: Iterable[ScimagoJournal]) -> Dict[str, ScimagoJournal]:
    """Map every ISSN (print AND electronic) to its journal. First entry wins on conflict."""
    index: Dict[str, ScimagoJournal] = {}
    for j in journals:
        for issn in j.issns:
            index.setdefault(issn, j)
    return index


def default_scimago_path() -> Optional[Path]:
    """Locate the SCImago JSON: user data dir first, then the bundled copy."""
    from find_references_scopus.config.defaults import get_data_dir, get_user_data_dir

    for c in (
        get_user_data_dir() / "scimagojr.json",
        get_user_data_dir() / "scimagojr_2025.json",
        get_data_dir() / "scimagojr_2025.json",
    ):
        if c.is_file():
            return c
    return None
