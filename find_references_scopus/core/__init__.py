"""Core subpackage — models, Scopus checker, filter engine, dedup."""

from __future__ import annotations

from find_references_scopus.core.models import (
    Paper,
    ReferenceList,
    extract_dois,
    DOI_REGEX,
)
from find_references_scopus.core.scopus_checker import (
    ScopusChecker,
    is_valid_quartile,
)
from find_references_scopus.core.filter_rules import (
    FilterEngine,
    Rule,
    YearFilter,
    CitationFilter,
    ScopusOnlyFilter,
    QuartileFilter,
    KeywordBlacklist,
    KeywordWhitelist,
    OpenAccessFilter,
    LanguageFilter,
    DOIBlacklist,
    DOIWhitelist,
    build_engine_from_cli,
)
from find_references_scopus.core.deduplication import (
    deduplicate,
    deduplicate_groups,
    find_duplicates,
)
from find_references_scopus.core.mailto_pool import MailtoPool
from find_references_scopus.core.issn_filter import (
    IssnFilter,
    build_filter_from_defaults,
    list_subject_areas,
    list_quartiles,
)

__all__ = [
    "Paper",
    "ReferenceList",
    "extract_dois",
    "DOI_REGEX",
    "ScopusChecker",
    "is_valid_quartile",
    "FilterEngine",
    "Rule",
    "YearFilter",
    "CitationFilter",
    "ScopusOnlyFilter",
    "QuartileFilter",
    "KeywordBlacklist",
    "KeywordWhitelist",
    "OpenAccessFilter",
    "LanguageFilter",
    "DOIBlacklist",
    "DOIWhitelist",
    "build_engine_from_cli",
    "deduplicate",
    "deduplicate_groups",
    "find_duplicates",
    "MailtoPool",
    "IssnFilter",
    "build_filter_from_defaults",
    "list_subject_areas",
    "list_quartiles",
]
