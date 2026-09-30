"""CSV exporter (good for manual review in Excel)."""

from __future__ import annotations

import csv
import io
from typing import List

from find_references_scopus.core.models import Paper
from find_references_scopus.exporters.base import Exporter, PaperSource


class CSVExporter(Exporter):
    format_name = "csv"
    file_extension = ".csv"

    COLUMNS = [
        "doi", "title", "authors", "journal", "year", "publisher",
        "volume", "issue", "pages", "issn",
        "cited_by_count", "is_open_access", "open_access_url",
        "scopus_indexed", "quartile", "language", "source", "url",
        "keywords", "abstract_truncated",
    ]

    def export(self, source: PaperSource) -> str:
        papers = self._flatten(source)
        buf = io.StringIO()
        writer = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\n")
        writer.writerow(self.COLUMNS)
        for p in papers:
            writer.writerow(self._row(p))
        return buf.getvalue()

    def _row(self, p: Paper) -> List[str]:
        return [
            p.doi,
            p.title,
            "; ".join(p.authors),
            p.journal,
            str(p.year or ""),
            p.publisher,
            p.volume,
            p.issue,
            p.pages,
            p.issn_electronic or p.issn_print,
            str(p.cited_by_count),
            str(p.is_open_access).lower(),
            p.open_access_url,
            str(p.scopus_indexed).lower(),
            p.quartile,
            p.language,
            p.source,
            p.url,
            "; ".join(p.keywords),
            (p.abstract[:200] + "...") if len(p.abstract) > 200 else p.abstract,
        ]
