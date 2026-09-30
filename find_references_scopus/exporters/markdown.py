"""Markdown exporter — compact human-readable reference list."""

from __future__ import annotations

from typing import List

from find_references_scopus.core.models import Paper
from find_references_scopus.exporters.base import Exporter, PaperSource


class MarkdownExporter(Exporter):
    format_name = "markdown"
    file_extension = ".md"

    def export(self, source: PaperSource) -> str:
        papers = self._flatten(source)
        lines: List[str] = [
            "# References",
            "",
            f"Total: {len(papers)} entries  ",
            f"Scopus-indexed: {sum(1 for p in papers if p.scopus_indexed)}  ",
            f"Non-Scopus: {sum(1 for p in papers if not p.scopus_indexed)}",
            "",
            "---",
            "",
        ]
        for idx, p in enumerate(papers, 1):
            lines.append(self._format_entry(p, idx))
        return "\n".join(lines)

    def _format_entry(self, p: Paper, idx: int) -> str:
        out: List[str] = []
        # Header: number + DOI
        header = f"## {idx}. "
        if p.doi:
            header += f"`{p.doi}`"
        else:
            header += "_(no DOI)_"
        if p.scopus_indexed:
            header += "  `[Scopus"
            if p.quartile:
                header += f" {p.quartile}"
            header += "]`"
        out.append(header)
        out.append("")

        if p.title:
            out.append(f"**Title:** {p.title}")
        if p.authors:
            out.append(f"**Authors:** {p.short_authors}")
        if p.journal:
            out.append(f"**Journal:** *{p.journal}*")
        if p.year:
            out.append(f"**Year:** {p.year}")
        if p.cited_by_count:
            out.append(f"**Cited by:** {p.cited_by_count}")
        if p.is_open_access:
            out.append("**Open Access:** yes" + (f" — {p.open_access_url}" if p.open_access_url else ""))
        if p.abstract:
            abstr = p.abstract
            if len(abstr) > 500:
                abstr = abstr[:500] + "..."
            out.append("")
            out.append(f"> {abstr}")
        out.append("")
        return "\n".join(out)
