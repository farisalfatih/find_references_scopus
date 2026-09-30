"""Tests for BibTeX DOI extraction in the validate command.

Regression coverage: the project pins ``bibtexparser>=2.0.0b7`` (a v2 release,
whose API dropped ``bibtexparser.bparser.BibTexParser``), but the extraction
code used to import that removed v1 class, so `findref validate -i file.bib`
always fell through to the regex fallback (or crashed) instead of actually
using bibtexparser.
"""

import bibtexparser

from find_references_scopus.commands.validate import _extract_dois_from_bib


def test_bibtexparser_installed_is_v2():
    """Guard: if this ever regresses to v1, the extraction code must be revisited too."""
    major = int(bibtexparser.__version__.split(".")[0])
    assert major >= 2


def test_extract_dois_from_bib_basic(tmp_path):
    bib = tmp_path / "refs.bib"
    bib.write_text(
        """
@article{smith2024,
  doi = {10.1000/xyz},
  title = {Something},
}
@article{jones2020,
  DOI = {10.1000/ABC},
  title = {Something Else},
}
""",
        encoding="utf-8",
    )
    dois = _extract_dois_from_bib(bib)
    assert dois == ["10.1000/xyz", "10.1000/ABC"]


def test_extract_dois_from_bib_is_case_insensitive_on_field_name(tmp_path):
    """bibtexparser v2 keeps field keys as written; DOI/doi/Doi must all be found."""
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{a, Doi = {10.1/case-test}}\n", encoding="utf-8")
    dois = _extract_dois_from_bib(bib)
    assert dois == ["10.1/case-test"]


def test_extract_dois_from_bib_dedupes_case_insensitively(tmp_path):
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@article{a, doi = {10.1/DUP}}\n@article{b, doi = {10.1/dup}}\n",
        encoding="utf-8",
    )
    dois = _extract_dois_from_bib(bib)
    assert dois == ["10.1/DUP"]


def test_extract_dois_from_bib_skips_entries_without_doi(tmp_path):
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@article{a, title = {No DOI here}}\n@article{b, doi = {10.1/has-doi}}\n",
        encoding="utf-8",
    )
    dois = _extract_dois_from_bib(bib)
    assert dois == ["10.1/has-doi"]


def test_extract_dois_from_bib_no_entries_for_non_bibtex_text(tmp_path):
    """bibtexparser v2 is lenient: text with no BibTeX entries parses to zero entries
    (no exception), so no DOIs are extracted from it - regardless of what the raw text
    contains. Only a genuine parse failure (see the next test) engages the regex fallback.
    """
    bib = tmp_path / "not_bibtex.bib"
    bib.write_text("this is not bibtex at all, but 10.1000/regexfallback is in here", encoding="utf-8")
    dois = _extract_dois_from_bib(bib)
    assert dois == []


def test_extract_dois_from_bib_falls_back_to_regex_on_decode_error(tmp_path):
    """A genuine parse failure (e.g. an undecodable file) must fall back to the regex extractor."""
    bib = tmp_path / "broken.bib"
    bib.write_bytes(b"\xff\xfe not valid utf-8, but 10.1000/regexfallback is in here")
    dois = _extract_dois_from_bib(bib)
    assert "10.1000/regexfallback" in dois
