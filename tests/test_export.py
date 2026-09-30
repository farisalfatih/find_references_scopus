"""Tests for exporters."""

import json
from pathlib import Path

import pytest

from find_references_scopus.core.models import Paper, ReferenceList
from find_references_scopus.exporters import (
    BibTeXExporter,
    CSVExporter,
    JSONLExporter,
    MarkdownExporter,
    RISExporter,
    get_exporter,
)


@pytest.fixture
def sample_papers():
    """A small set of test papers covering various scenarios."""
    return [
        Paper(
            doi="10.1000/paper1",
            title="First paper on deep learning",
            authors=["Smith J.", "Jones A."],
            journal="Journal of ML",
            year=2024,
            volume="10",
            issue="2",
            first_page="100",
            last_page="120",
            cited_by_count=42,
            scopus_indexed=True,
            quartile="Q1",
            is_open_access=True,
            abstract="A novel approach to deep learning.",
            keywords=["deep learning", "neural networks"],
        ),
        Paper(
            doi="10.1000/paper2",
            title="Second paper (no Scopus)",
            authors=["Doe R."],
            journal="Workshop Proc",
            year=2023,
            scopus_indexed=False,
            abstract="Preprint version.",
        ),
    ]


def test_get_exporter_bibtex():
    e = get_exporter("bibtex")
    assert isinstance(e, BibTeXExporter)
    assert e.file_extension == ".bib"


def test_get_exporter_ris():
    assert isinstance(get_exporter("ris"), RISExporter)


def test_get_exporter_csv():
    assert isinstance(get_exporter("csv"), CSVExporter)


def test_get_exporter_jsonl():
    assert isinstance(get_exporter("jsonl"), JSONLExporter)


def test_get_exporter_markdown():
    assert isinstance(get_exporter("md"), MarkdownExporter)


def test_get_exporter_unknown():
    with pytest.raises(ValueError):
        get_exporter("unknown-format")


def test_bibtex_export_contains_scopus_flag(sample_papers):
    out = BibTeXExporter().export(sample_papers)
    assert "scopus_indexed = {true}" in out
    assert "scopus_indexed = {false}" in out
    assert "@article{" in out


def test_bibtex_export_citation_key_stable(sample_papers):
    """Citation key should be deterministic — based on DOI hash."""
    out1 = BibTeXExporter().export(sample_papers)
    out2 = BibTeXExporter().export(sample_papers)
    # Extract citation keys
    keys1 = [line.split("{")[1].split(",")[0] for line in out1.splitlines() if line.startswith("@article{")]
    keys2 = [line.split("{")[1].split(",")[0] for line in out2.splitlines() if line.startswith("@article{")]
    assert keys1 == keys2


def test_ris_export(sample_papers):
    out = RISExporter().export(sample_papers)
    assert "TY  - JOUR" in out
    assert "ER  -" in out
    assert "scopus_indexed=true" in out
    assert "scopus_indexed=false" in out


def test_csv_export_headers(sample_papers):
    out = CSVExporter().export(sample_papers)
    first_line = out.splitlines()[0]
    assert "scopus_indexed" in first_line
    assert "quartile" in first_line
    assert "doi" in first_line


def test_jsonl_export_valid_json(sample_papers):
    out = JSONLExporter().export(sample_papers)
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 2
    for ln in lines:
        d = json.loads(ln)
        assert "doi" in d
        assert "scopus_indexed" in d


def test_markdown_export_has_headers(sample_papers):
    out = MarkdownExporter().export(sample_papers)
    assert "# References" in out
    assert "[Scopus Q1]" in out  # First paper has Scopus Q1 badge


def test_export_to_file_writes_to_disk(sample_papers, tmp_path):
    out_path = tmp_path / "test.bib"
    BibTeXExporter().export_to_file(sample_papers, out_path)
    assert out_path.is_file()
    content = out_path.read_text(encoding="utf-8")
    assert "@article{" in content


def test_export_handles_reference_list(sample_papers):
    rl = ReferenceList(groups={"group1": sample_papers})
    out = BibTeXExporter().export(rl)
    assert "@article{" in out
    assert "10.1000/paper1" in out
