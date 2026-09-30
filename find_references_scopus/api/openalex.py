"""OpenAlex API client with multi-mailto rotation support.

OpenAlex is a free, open scholarly graph. The "polite pool" requires a
mailto in the User-Agent (or as ``mailto=`` param) — and per-mailto rate limits
apply. By passing a :class:`MailtoPool` with multiple mailtos, this client
automatically rotates between them and reacts to HTTP 429 by switching to the
next available mailto.

Docs: https://docs.openalex.org/
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from find_references_scopus import __version__
from find_references_scopus.api.base import BaseClient, NotFoundError, RateLimitError
from find_references_scopus.config.defaults import DEFAULT_OPENALEX_MAILTO
from find_references_scopus.core.mailto_pool import MailtoPool
from find_references_scopus.core.models import Paper
from find_references_scopus.core.scimago import split_issns

# OpenAlex allows at most 100 values joined with "|" inside one filter.
MAX_OR_VALUES = 100


log = logging.getLogger("findref.api.openalex")


class OpenAlexClient(BaseClient):
    """OpenAlex API client with optional multi-mailto rotation.

    Two modes:

    1. **Single mailto** (backward-compatible): pass ``mailto="alice@x.edu"``
       to the constructor. Every request uses this mailto.

    2. **Multi-mailto pool** (new): pass ``mailto_pool=MailtoPool([...])``.
       The client picks the next mailto from the pool on each request (round-robin
       if ``auto_rotate=True``, or stick-until-429 if ``auto_rotate=False``).
    """

    name = "openalex"
    base_url = "https://api.openalex.org"

    def __init__(
        self,
        *,
        mailto: Optional[str] = None,
        mailto_pool: Optional[MailtoPool] = None,
        rate_limit_delay: float = 1.0,
        max_retries_on_429: int = 3,
    ) -> None:
        super().__init__(mailto=mailto, rate_limit_delay=rate_limit_delay)

        # If a pool is given, use it. Otherwise build a single-element pool
        # from the mailto (or the default placeholder) so the rest of the
        # code can uniformly call self._pool.next().
        if mailto_pool is not None:
            self._pool = mailto_pool
        elif mailto:
            self._pool = MailtoPool([mailto], auto_rotate=False)
        else:
            self._pool = MailtoPool([DEFAULT_OPENALEX_MAILTO], auto_rotate=False)

        self._max_retries_on_429 = max_retries_on_429
        # Track which mailto was used for the current request (for retry logic)
        self._current_mailto: Optional[str] = None
        # Counters of the last search() call: scanned / matched / scan_capped
        self.last_search_stats: Dict[str, Any] = {}

    # ------------------------------------------------------------------ #
    # Pool introspection
    # ------------------------------------------------------------------ #

    @property
    def pool(self) -> MailtoPool:
        return self._pool

    def pool_stats(self) -> Dict[str, Dict[str, object]]:
        return self._pool.stats()

    # ------------------------------------------------------------------ #
    # Override BaseClient.request to swap mailto per request
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
        """Wrap BaseClient.request with mailto rotation + 429 retry.

        Strategy:
          1. Pick next mailto from the pool (skip cooldowns).
          2. Inject it as ``params['mailto']`` and into User-Agent.
          3. Try the request.
          4. On 429: mark the mailto as rate-limited (cooldown), pick next mailto, retry.
          5. After ``max_retries_on_429`` attempts, give up (raise RateLimitError).
        """
        params = dict(params or {})
        headers = dict(headers or {})

        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries_on_429 + 1):
            # Pick next mailto
            mailto = self._pool.next()
            if not mailto:
                mailto = DEFAULT_OPENALEX_MAILTO
            self._current_mailto = mailto

            # Inject mailto into request
            params["mailto"] = mailto
            headers["User-Agent"] = f"findref/{__version__} (mailto:{mailto})"

            try:
                result = super().request(
                    method, path,
                    params=params, headers=headers, json_body=json_body,
                    retries=retries,
                )
                # Success — mark this mailto as healthy
                self._pool.mark_ok(mailto)
                return result
            except RateLimitError as e:
                # Mark this mailto as rate-limited
                retry_after = _extract_retry_after(e)
                log.warning(
                    "OpenAlex 429 on mailto=%s — marking cooldown (%.1fs), retrying (%d/%d)",
                    mailto, retry_after or self._pool.cooldown_seconds,
                    attempt + 1, self._max_retries_on_429,
                )
                self._pool.mark_rate_limited(mailto, retry_after=retry_after)
                last_error = e
                # Brief pause before retrying with next mailto
                time.sleep(1.0)
                continue
            except Exception:
                raise

        # Exhausted retries
        if last_error:
            raise last_error
        raise RateLimitError("OpenAlex: exhausted all mailtos in pool after rate-limit retries")

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #

    def search(
        self,
        query: str,
        *,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        language: str = "en",
        per_page: int = 200,
        max_results: int = 0,
        issn_filter: Optional[List[str]] = None,
        accept: Optional[Callable[[Paper], bool]] = None,
        max_scan: int = 0,
        search_field: str = "abstract.search",
    ) -> List[Paper]:
        """Search OpenAlex works by query string.

        Restricting results to a set of journals (by ISSN) works in two ways:

        * ``issn_filter`` - up to 100 ISSNs sent to OpenAlex as a single
          ``primary_location.source.issn`` filter (exact, done by OpenAlex).
        * ``accept`` - a predicate applied locally to every result. Use this for
          more than 100 ISSNs: OpenAlex is scanned page by page and only accepted
          papers are kept, until ``max_results`` are found or ``max_scan``
          works have been scanned (0 = no cap).

        After the call, ``self.last_search_stats`` holds ``scanned``, ``matched``
        and ``scan_capped`` (True when ``max_scan`` stopped the scan early).

        Raises:
            ValueError: more than 100 ISSNs given in ``issn_filter``.
        """
        issns = split_issns(issn_filter) if issn_filter else []
        if len(issns) > MAX_OR_VALUES:
            raise ValueError(
                f"OpenAlex accepts at most {MAX_OR_VALUES} ISSNs per filter "
                f"(got {len(issns)}); pass `accept=` to filter locally instead."
            )

        papers: List[Paper] = []
        cursor = "*"
        scanned = 0
        capped = False
        self.last_search_stats = {"scanned": 0, "matched": 0, "scan_capped": False}

        def _finish() -> List[Paper]:
            self.last_search_stats = {
                "scanned": scanned,
                "matched": len(papers),
                "scan_capped": capped,
            }
            return papers

        while True:
            filters: List[str] = []
            if year_from or year_to:
                yf = year_from or 1900
                yt = year_to or 9999
                filters.append(f"from_publication_date:{yf}-01-01")
                filters.append(f"to_publication_date:{yt}-12-31")
            if language:
                filters.append(f"language:{language}")
            filters.append("has_doi:true")
            filters.append("has_abstract:true")
            if issns:
                filters.append("primary_location.source.issn:" + "|".join(issns))
            elif accept is not None:
                # Local ISSN matching only makes sense for works whose journal has an ISSN.
                filters.append("primary_location.source.has_issn:true")
            if search_field and query:
                filters.append(f"{search_field}:{query}")

            params: Dict[str, Any] = {
                "search": query if not search_field else None,
                "filter": ",".join(filters),
                "per-page": min(per_page, 200),
                "cursor": cursor,
                "select": ",".join([
                    "id", "doi", "title", "publication_date", "authorships",
                    "primary_location", "abstract_inverted_index", "language",
                    "cited_by_count", "open_access", "concepts", "topics", "keywords",
                ]),
            }
            # mailto is injected by self.request() based on pool
            params = {k: v for k, v in params.items() if v is not None}

            data = self.request("GET", "/works", params=params)
            results = data.get("results", [])
            if not results:
                break

            for r in results:
                scanned += 1
                paper = _normalize_openalex(r)
                if accept is None or accept(paper):
                    papers.append(paper)
                    if max_results > 0 and len(papers) >= max_results:
                        return _finish()
                if max_scan > 0 and scanned >= max_scan:
                    capped = True
                    return _finish()

            meta = data.get("meta", {})
            cursor = meta.get("next_cursor")
            if not cursor:
                break
            time.sleep(self.rate_limit_delay)

        return _finish()

    def fetch_by_doi(self, doi: str) -> Optional[Paper]:
        """Fetch a single work by DOI."""
        doi = doi.lower().strip()
        if not doi.startswith("10."):
            return None
        try:
            data = self.request("GET", f"/works/https://doi.org/{doi}")
        except NotFoundError:
            return None
        return _normalize_openalex(data)


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #

def _extract_retry_after(err: Exception) -> Optional[float]:
    """Try to extract Retry-After value from a RateLimitError."""
    # BaseClient.request raises RateLimitError with a message; we don't have
    # direct access to headers here, so just return None and let pool use its
    # default cooldown. Could be enhanced by passing headers through.
    return None


# ---------------------------------------------------------------------- #
# Normalization
# ---------------------------------------------------------------------- #

def _normalize_openalex(r: Dict[str, Any]) -> Paper:
    """Convert OpenAlex work JSON to a Paper."""
    doi = (r.get("doi") or "").replace("https://doi.org/", "").replace("http://doi.org/", "")
    title = r.get("title") or ""
    pub_date = r.get("publication_date") or ""

    authors: List[str] = []
    for a in r.get("authorships", []):
        name = (a.get("author") or {}).get("display_name") or ""
        if name:
            authors.append(name)

    loc = r.get("primary_location") or {}
    source = loc.get("source") or {}
    journal = source.get("display_name") or ""
    # ``source.issn`` lists every ISSN of the journal in no fixed order (it
    # includes the linking ISSN), so keep them all and do not assume which is
    # print and which is electronic.
    issn_all = split_issns(source.get("issn") or [])
    issn_l = split_issns(source.get("issn_l") or "")
    issn_all = list(dict.fromkeys([*issn_all, *issn_l]))
    issn_e = issn_all[0] if len(issn_all) > 0 else ""
    issn_p = issn_all[1] if len(issn_all) > 1 else ""

    biblio = loc.get("biblio") or {}
    volume = biblio.get("volume") or ""
    issue = biblio.get("issue") or ""
    first_page = biblio.get("first_page") or ""
    last_page = biblio.get("last_page") or ""

    abstract = _reconstruct_abstract(r.get("abstract_inverted_index"))

    oa = r.get("open_access") or {}
    is_oa = bool(oa.get("is_oa"))
    oa_url = oa.get("oa_url") or ""
    oa_status = oa.get("oa_status") or ""

    year: Optional[int] = None
    if pub_date:
        try:
            year = int(pub_date[:4])
        except ValueError:
            year = None

    subjects: List[str] = []
    for c in (r.get("topics") or [])[:5]:
        if isinstance(c, dict) and c.get("display_name"):
            subjects.append(c["display_name"])
    keywords: List[str] = [k.get("display_name") or "" for k in (r.get("keywords") or [])[:10] if k.get("display_name")]

    return Paper(
        doi=doi,
        title=title,
        authors=authors,
        journal=journal,
        year=year,
        pub_date=pub_date,
        volume=volume,
        issue=issue,
        first_page=first_page,
        last_page=last_page,
        issn_electronic=issn_e,
        issn_print=issn_p,
        issn_l=issn_l[0] if issn_l else "",
        issns=issn_all,
        abstract=abstract,
        language=r.get("language") or "en",
        cited_by_count=int(r.get("cited_by_count") or 0),
        is_open_access=is_oa,
        open_access_url=oa_url,
        open_access_status=oa_status,
        subjects=subjects,
        keywords=keywords,
        source="openalex",
        url=r.get("id") or "",
        raw=r,
    )


def _reconstruct_abstract(inverted: Optional[Dict[str, List[int]]]) -> str:
    """Reconstruct abstract from OpenAlex's inverted-index representation."""
    if not inverted:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idx_list in inverted.items():
        for i in idx_list:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions)
