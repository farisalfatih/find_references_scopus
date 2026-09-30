"""Tests for the core models (Paper, ReferenceList, extract_dois)."""

import pytest

from find_references_scopus.core.models import (
    Paper,
    ReferenceList,
    extract_dois,
    DOI_REGEX,
)


def test_paper_defaults():
    p = Paper()
    assert p.doi == ""
    assert p.title == ""
    assert p.authors == []
    assert p.scopus_indexed is False
    assert p.year is None


def test_paper_from_dict_roundtrip():
    data = {
        "doi": "10.1000/abc",
        "title": "Test",
        "authors": ["Smith J."],
        "year": 2024,
    }
    p = Paper.from_dict(data)
    assert p.doi == "10.1000/abc"
    assert p.title == "Test"
    assert p.authors == ["Smith J."]
    assert p.year == 2024
    # raw preserved
    assert p.raw["doi"] == "10.1000/abc"


def test_paper_citation_key_stable():
    """Same DOI -> same citation key."""
    p1 = Paper(doi="10.1000/abc", title="A", authors=["Smith J."], year=2024)
    p2 = Paper(doi="10.1000/abc", title="B", authors=["Smith J."], year=2024)
    assert p1.citation_key() == p2.citation_key()


def test_paper_citation_key_different_dois():
    p1 = Paper(doi="10.1000/abc", authors=["Smith"], year=2024)
    p2 = Paper(doi="10.1000/xyz", authors=["Smith"], year=2024)
    assert p1.citation_key() != p2.citation_key()


def test_paper_short_authors():
    p = Paper(authors=["Smith J."])
    assert p.short_authors == "Smith"

    p = Paper(authors=["Smith J.", "Jones A."])
    assert p.short_authors == "Smith and Jones"

    p = Paper(authors=["Smith J.", "Jones A.", "Doe R."])
    assert p.short_authors == "Smith et al."

    p = Paper(authors=[])
    assert p.short_authors == "Unknown"


def test_paper_pages():
    p = Paper(first_page="100", last_page="120")
    assert p.pages == "100--120"

    p = Paper(first_page="100", last_page="100")
    assert p.pages == "100"

    p = Paper(first_page="100", last_page="")
    assert p.pages == "100"

    p = Paper()
    assert p.pages == ""


def test_paper_matches_doi():
    p = Paper(doi="10.1000/Test")
    assert p.matches_doi("10.1000/test")  # case-insensitive
    assert p.matches_doi("10.1000/Test")
    assert not p.matches_doi("10.1000/other")


def test_reference_list_add_and_flatten():
    rl = ReferenceList()
    p1 = Paper(doi="10.1/a", title="A")
    p2 = Paper(doi="10.1/b", title="B")
    rl.add("group1", p1)
    rl.add("group1", p2)
    rl.add("group2", Paper(doi="10.1/c", title="C"))

    assert rl.total() == 3
    flat = rl.flatten()
    assert len(flat) == 3
    assert {p.doi for p in flat} == {"10.1/a", "10.1/b", "10.1/c"}


def test_reference_list_to_dict_roundtrip():
    rl = ReferenceList()
    rl.add("g1", Paper(doi="10.1/a", title="A", authors=["X"]))
    rl.add("g2", Paper(doi="10.1/b", title="B", authors=["Y"]))

    d = rl.to_dict()
    rl2 = ReferenceList.from_dict(d)
    assert rl2.total() == 2


def test_extract_dois_from_text():
    text = """
    Some text with DOI 10.1000/abc123 here.
    And another one: 10.1038/nature12373.
    A third one in URL form: https://doi.org/10.1234/test.5678.
    """
    dois = extract_dois(text)
    assert "10.1000/abc123" in dois
    assert "10.1038/nature12373" in dois
    # URL form may include extra chars — just check the prefix
    assert any(d.startswith("10.1234/test") for d in dois)


def test_extract_dois_dedup():
    text = "10.1000/abc and 10.1000/abc again"
    dois = extract_dois(text)
    assert len(dois) == 1


def test_extract_dois_empty():
    assert extract_dois("no dois here") == []
    assert extract_dois("") == []
