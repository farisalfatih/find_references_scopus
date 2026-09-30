"""Exporters: BibTeX, RIS, CSV, JSONL."""

from __future__ import annotations

from find_references_scopus.exporters.base import Exporter
from find_references_scopus.exporters.bibtex import BibTeXExporter
from find_references_scopus.exporters.ris import RISExporter
from find_references_scopus.exporters.csv_exp import CSVExporter
from find_references_scopus.exporters.jsonl import JSONLExporter
from find_references_scopus.exporters.markdown import MarkdownExporter

__all__ = [
    "Exporter",
    "BibTeXExporter",
    "RISExporter",
    "CSVExporter",
    "JSONLExporter",
    "MarkdownExporter",
    "get_exporter",
]


def get_exporter(format_name: str) -> Exporter:
    """Factory: get exporter by name (bibtex / ris / csv / jsonl / md)."""
    f = format_name.lower().strip()
    if f in {"bib", "bibtex", ".bib"}:
        return BibTeXExporter()
    if f in {"ris", ".ris"}:
        return RISExporter()
    if f in {"csv", ".csv"}:
        return CSVExporter()
    if f in {"jsonl", "json", ".jsonl"}:
        return JSONLExporter()
    if f in {"md", "markdown", ".md"}:
        return MarkdownExporter()
    raise ValueError(f"Unknown export format: {format_name}")
