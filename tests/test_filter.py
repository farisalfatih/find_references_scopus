"""Tests for the filter engine."""

from find_references_scopus.core.filter_rules import (
    FilterEngine,
    YearFilter,
    CitationFilter,
    ScopusOnlyFilter,
    QuartileFilter,
    KeywordBlacklist,
    KeywordWhitelist,
    OpenAccessFilter,
    LanguageFilter,
    DOIBlacklist,
    build_engine_from_cli,
)
from find_references_scopus.core.models import Paper


def make_paper(**kwargs):
    """Helper: build a Paper with sensible defaults."""
    defaults = {
        "doi": "10.1000/test",
        "title": "Test paper",
        "authors": ["Smith J."],
        "year": 2023,
    }
    defaults.update(kwargs)
    return Paper(**defaults)


# ---------------------------------------------------------------------- #
# YearFilter
# ---------------------------------------------------------------------- #

def test_year_filter_min():
    f = YearFilter(min_year=2020)
    assert f.keep(make_paper(year=2024)) is True
    assert f.keep(make_paper(year=2019)) is False
    assert f.keep(make_paper(year=None)) is False  # unknown year dropped


def test_year_filter_max():
    f = YearFilter(max_year=2025)
    assert f.keep(make_paper(year=2025)) is True
    assert f.keep(make_paper(year=2026)) is False


# ---------------------------------------------------------------------- #
# CitationFilter
# ---------------------------------------------------------------------- #

def test_citation_filter():
    f = CitationFilter(min_citations=10)
    assert f.keep(make_paper(cited_by_count=15)) is True
    assert f.keep(make_paper(cited_by_count=5)) is False
    assert f.keep(make_paper(cited_by_count=0)) is False


# ---------------------------------------------------------------------- #
# ScopusOnlyFilter
# ---------------------------------------------------------------------- #

def test_scopus_only_filter():
    f = ScopusOnlyFilter()
    assert f.keep(make_paper(scopus_indexed=True)) is True
    assert f.keep(make_paper(scopus_indexed=False)) is False


# ---------------------------------------------------------------------- #
# QuartileFilter
# ---------------------------------------------------------------------- #

def test_quartile_filter_q1q2():
    f = QuartileFilter(allowed={"Q1", "Q2"}, include_unranked=False)
    assert f.keep(make_paper(quartile="Q1")) is True
    assert f.keep(make_paper(quartile="Q2")) is True
    assert f.keep(make_paper(quartile="Q3")) is False
    assert f.keep(make_paper(quartile="-")) is False  # unranked excluded
    assert f.keep(make_paper(quartile="")) is False  # no quartile


def test_quartile_filter_include_unranked():
    f = QuartileFilter(allowed={"Q1", "Q2"}, include_unranked=True)
    assert f.keep(make_paper(quartile="-")) is True


# ---------------------------------------------------------------------- #
# KeywordBlacklist / Whitelist
# ---------------------------------------------------------------------- #

def test_keyword_blacklist():
    f = KeywordBlacklist(keywords=["preprint", "survey"])
    assert f.keep(make_paper(title="A novel ML method", abstract="...")) is True
    assert f.keep(make_paper(title="A preprint on ML", abstract="...")) is False
    assert f.keep(make_paper(title="...", abstract="This is a survey of...")) is False


def test_keyword_whitelist():
    f = KeywordWhitelist(keywords=["neural network"])
    assert f.keep(make_paper(title="Neural network approaches", abstract="...")) is True
    assert f.keep(make_paper(title="Bayesian methods", abstract="...")) is False


# ---------------------------------------------------------------------- #
# Engine
# ---------------------------------------------------------------------- #

def test_engine_apply_all_rules():
    eng = FilterEngine()
    eng.add(YearFilter(min_year=2020))
    eng.add(CitationFilter(min_citations=5))
    eng.add(ScopusOnlyFilter())

    good = make_paper(year=2024, cited_by_count=10, scopus_indexed=True)
    bad_year = make_paper(year=2019, cited_by_count=10, scopus_indexed=True)
    bad_cites = make_paper(year=2024, cited_by_count=1, scopus_indexed=True)
    bad_scopus = make_paper(year=2024, cited_by_count=10, scopus_indexed=False)

    kept, removed = eng.apply([good, bad_year, bad_cites, bad_scopus])
    assert len(kept) == 1
    assert kept[0] is good
    assert len(removed) == 3


def test_build_engine_from_cli_scopus_only():
    eng = build_engine_from_cli(scopus_only=True, min_year=2020)
    rule_names = [r.name for r in eng.rules]
    assert "scopus_only" in rule_names
    assert "year" in rule_names


def test_build_engine_from_cli_quartile():
    eng = build_engine_from_cli(quartile="Q1,Q2", include_unranked=False)
    q_rules = [r for r in eng.rules if r.name == "quartile"]
    assert len(q_rules) == 1
    assert q_rules[0].allowed == {"Q1", "Q2"}
    assert q_rules[0].include_unranked is False
