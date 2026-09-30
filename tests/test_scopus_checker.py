"""Tests for ScopusChecker.

The most important case here is regression coverage for a real bug: the old
checker only indexed a journal's ``issn_electronic``, so any journal known to
SCImago only by its print ISSN (about a third of the bundled dataset) could
never be matched.
"""

import json

import pytest

from find_references_scopus.core.models import Paper
from find_references_scopus.core.scimago import clear_cache
from find_references_scopus.core.scopus_checker import ScopusChecker, is_valid_quartile


@pytest.fixture(autouse=True)
def _clear_scimago_cache():
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def scimago_path(tmp_path):
    data = [
        {"journal": "Dual ISSN Journal", "issn_electronic": "1111-1111", "issn_print": "2222-2222", "quartile": "Q1"},
        {"journal": "Print Only Journal", "issn_print": "3333-3333", "quartile": "Q2"},
        {"journal": "Electronic Only Journal", "issn_electronic": "4444-4444", "quartile": "Q3"},
    ]
    p = tmp_path / "scimago.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def test_lookup_by_electronic_issn(scimago_path):
    checker = ScopusChecker(scimago_path=scimago_path)
    j = checker.lookup_issn("1111-1111")
    assert j is not None and j.title == "Dual ISSN Journal"


def test_lookup_by_print_issn_of_dual_issn_journal(scimago_path):
    """Regression: the print ISSN of a journal that also has an electronic ISSN."""
    checker = ScopusChecker(scimago_path=scimago_path)
    j = checker.lookup_issn("2222-2222")
    assert j is not None and j.title == "Dual ISSN Journal"


def test_lookup_print_only_journal(scimago_path):
    """Regression: a journal that ONLY has a print ISSN must still be found."""
    checker = ScopusChecker(scimago_path=scimago_path)
    j = checker.lookup_issn("3333-3333")
    assert j is not None and j.title == "Print Only Journal"
    assert j.quartile == "Q2"


def test_lookup_unknown_issn_returns_none(scimago_path):
    checker = ScopusChecker(scimago_path=scimago_path)
    assert checker.lookup_issn("9999-9999") is None


def test_lookup_accepts_unhyphenated_issn(scimago_path):
    checker = ScopusChecker(scimago_path=scimago_path)
    assert checker.lookup_issn("33333333") is not None


def test_annotate_paper_with_print_issn_only(scimago_path):
    """A Paper carrying only issn_print must still be recognized as Scopus-indexed."""
    checker = ScopusChecker(scimago_path=scimago_path)
    paper = Paper(doi="10.1/x", title="t", issn_print="3333-3333", issn_electronic="")
    checker.annotate(paper)
    assert paper.scopus_indexed is True
    assert paper.quartile == "Q2"


def test_annotate_paper_with_issns_list(scimago_path):
    """A Paper carrying the full `issns` list (as OpenAlexClient populates it now)."""
    checker = ScopusChecker(scimago_path=scimago_path)
    paper = Paper(doi="10.1/y", title="t2", issns=["1111-1111", "2222-2222"])
    checker.annotate(paper)
    assert paper.scopus_indexed is True
    assert paper.quartile == "Q1"


def test_annotate_paper_not_in_scimago(scimago_path):
    checker = ScopusChecker(scimago_path=scimago_path)
    paper = Paper(doi="10.1/z", title="t3", issns=["0000-0000"])
    checker.annotate(paper)
    assert paper.scopus_indexed is False


def test_annotate_trusts_existing_valid_quartile(scimago_path):
    """If the paper already carries a valid quartile, don't second-guess it with a lookup."""
    checker = ScopusChecker(scimago_path=scimago_path)
    paper = Paper(doi="10.1/w", title="t4", quartile="Q4", issns=["0000-0000"])
    checker.annotate(paper)
    assert paper.scopus_indexed is True
    assert paper.quartile == "Q4"


def test_annotate_all_stats(scimago_path):
    checker = ScopusChecker(scimago_path=scimago_path)
    papers = [
        Paper(doi="a", title="a", issns=["1111-1111"]),
        Paper(doi="b", title="b", issns=["3333-3333"]),
        Paper(doi="c", title="c", issns=["0000-0000"]),
    ]
    stats = checker.annotate_all(papers)
    assert stats["total"] == 3
    assert stats["scopus"] == 2
    assert stats["non_scopus"] == 1
    assert stats["with_quartile"] == 2


def test_is_valid_quartile():
    assert is_valid_quartile("Q1")
    assert is_valid_quartile("q1")
    assert is_valid_quartile("-")
    assert not is_valid_quartile("Q5")
