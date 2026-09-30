"""JSONL exporter (one paper per line — agent-friendly)."""

from __future__ import annotations

import json
from typing import List

from find_references_scopus.core.models import Paper
from find_references_scopus.exporters.base import Exporter, PaperSource


class JSONLExporter(Exporter):
    format_name = "jsonl"
    file_extension = ".jsonl"

    def export(self, source: PaperSource) -> str:
        papers = self._flatten(source)
        lines: List[str] = []
        for p in papers:
            lines.append(json.dumps(p.to_dict(), ensure_ascii=False, default=str))
        return "\n".join(lines) + ("\n" if lines else "")
