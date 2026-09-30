"""Deduplication engine: detect same-paper across groups (by DOI, then fuzzy title)."""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Tuple

from find_references_scopus.core.models import Paper


def _normalize_title(title: str) -> str:
    """Aggressive normalization for fuzzy title comparison.

    Lowercase, NFKC, drop punctuation, collapse whitespace.
    """
    if not title:
        return ""
    title = unicodedata.normalize("NFKC", title).lower()
    title = re.sub(r"[\-_/]+", " ", title)
    title = re.sub(r"[^a-z0-9\s]", " ", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def _similarity(a: str, b: str) -> float:
    """Jaccard similarity on 3-char shingles — robust for slight title variations."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    sa = {a[i : i + 3] for i in range(len(a) - 2)}
    sb = {b[i : i + 3] for i in range(len(b) - 2)}
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def find_duplicates(papers: List[Paper], *, threshold: float = 0.92) -> List[Tuple[Paper, Paper, float]]:
    """Find duplicates within a list.

    Returns list of ``(p1, p2, similarity_score)`` pairs where similarity >= threshold.
    """
    pairs: List[Tuple[Paper, Paper, float]] = []
    n = len(papers)
    for i in range(n):
        for j in range(i + 1, n):
            p1, p2 = papers[i], papers[j]
            # 1) Same DOI → guaranteed duplicate
            if p1.doi and p2.doi and p1.doi.lower() == p2.doi.lower():
                pairs.append((p1, p2, 1.0))
                continue
            # 2) Fuzzy title
            s = _similarity(_normalize_title(p1.title), _normalize_title(p2.title))
            if s >= threshold:
                pairs.append((p1, p2, s))
    return pairs


def deduplicate(papers: List[Paper], *, threshold: float = 0.92, keep_first: bool = True) -> Tuple[List[Paper], List[Paper]]:
    """Return ``(unique, removed)`` lists.

    When a duplicate pair is found, the first paper in ``papers`` is kept
    (or the second if ``keep_first=False``).
    """
    seen_dois: Dict[str, int] = {}  # doi_lower -> first index
    seen_titles: List[Tuple[str, int]] = []  # (normalized_title, first index)
    keep_indices: set[int] = set()
    removed: List[Paper] = []

    for idx, p in enumerate(papers):
        # DOI check
        if p.doi:
            doi_l = p.doi.lower().strip()
            if doi_l in seen_dois:
                removed.append(p)
                continue
            seen_dois[doi_l] = idx

        # Title check
        norm_title = _normalize_title(p.title)
        if norm_title:
            dup_idx: Optional[int] = None
            for t, i in seen_titles:
                if _similarity(t, norm_title) >= threshold:
                    dup_idx = i
                    break
            if dup_idx is not None:
                removed.append(p)
                continue
            seen_titles.append((norm_title, idx))

        keep_indices.add(idx)

    unique = [papers[i] for i in sorted(keep_indices)]
    return unique, removed


def deduplicate_groups(
    groups: Dict[str, List[Paper]],
    *,
    threshold: float = 0.92,
) -> Tuple[Dict[str, List[Paper]], List[Paper]]:
    """Deduplicate across groups, keeping each paper in its original group.

    The FIRST group to claim a paper wins; subsequent duplicates are removed
    from their groups.

    Returns ``(new_groups, all_removed)``.
    """
    new_groups: Dict[str, List[Paper]] = {g: [] for g in groups}
    seen_dois: set[str] = set()
    seen_titles: List[str] = []
    all_removed: List[Paper] = []

    for group, papers in groups.items():
        for p in papers:
            # DOI check
            if p.doi:
                doi_l = p.doi.lower().strip()
                if doi_l in seen_dois:
                    all_removed.append(p)
                    continue
                seen_dois.add(doi_l)

            # Title check
            norm = _normalize_title(p.title)
            if norm:
                if any(_similarity(norm, t) >= threshold for t in seen_titles):
                    all_removed.append(p)
                    continue
                seen_titles.append(norm)

            new_groups[group].append(p)

    return new_groups, all_removed
