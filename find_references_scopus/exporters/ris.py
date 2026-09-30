"""RIS exporter (for EndNote / Covidence / Mendeley)."""

from __future__ import annotations

from typing import List

from find_references_scopus.core.models import Paper
from find_references_scopus.exporters.base import Exporter, PaperSource


class RISExporter(Exporter):
    format_name = "ris"
    file_extension = ".ris"

    def export(self, source: PaperSource) -> str:
        papers = self._flatten(source)
        lines: List[str] = []
        for p in papers:
            lines.extend(self._format_entry(p))
            lines.append("ER  -")
            lines.append("")
        return "\n".join(lines)

    def _format_entry(self, p: Paper) -> List[str]:
        out: List[str] = ["TY  - JOUR"]  # Default to journal article
        if p.authors:
            for a in p.authors:
                out.append(f"AU  - {a}")
        if p.title:
            out.append(f"TI  - {p.title}")
        if p.journal:
            out.append(f"JO  - {p.journal}")
        if p.publisher:
            out.append(f"PB  - {p.publisher}")
        if p.year:
            out.append(f"PY  - {p.year}")
        if p.volume:
            out.append(f"VL  - {p.volume}")
        if p.issue:
            out.append(f"IS  - {p.issue}")
        if p.first_page:
            out.append(f"SP  - {p.first_page}")
        if p.last_page:
            out.append(f"EP  - {p.last_page}")
        if p.doi:
            out.append(f"DO  - {p.doi}")
        if p.abstract:
            # RIS abstracts can be multi-line; use single line for safety
            abstr = p.abstract.replace("\n", " ").strip()
            if len(abstr) > 2000:
                abstr = abstr[:2000] + "..."
            out.append(f"AB  - {abstr}")
        if p.issn_electronic:
            out.append(f"SN  - {p.issn_electronic}")
        if p.url:
            out.append(f"UR  - {p.url}")
        if p.keywords:
            for k in p.keywords:
                out.append(f"KW  - {k}")
        # Custom scopus flag — appended as a note
        out.append(f"N1  - scopus_indexed={str(p.scopus_indexed).lower()}; quartile={p.quartile or 'N/A'}")
        return out
