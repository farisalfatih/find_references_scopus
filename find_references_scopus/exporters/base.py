"""Base exporter interface."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Union

from find_references_scopus.core.models import Paper, ReferenceList


PaperSource = Union[Iterable[Paper], ReferenceList, Dict[str, List[Paper]], List[Paper]]


class Exporter:
    """Base class for all exporters.

    Subclasses must implement ``export(papers) -> str`` and set ``format_name``.
    """

    format_name: str = "base"
    file_extension: str = ".txt"

    def export(self, source: PaperSource) -> str:  # pragma: no cover
        raise NotImplementedError

    def export_to_file(self, source: PaperSource, path: str | Path) -> Path:
        """Export to ``path``. Returns the path (parent dirs auto-created)."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        text = self.export(source)
        p.write_text(text, encoding="utf-8")
        return p

    @staticmethod
    def _flatten(source: PaperSource) -> List[Paper]:
        """Convert any supported source into a flat ``List[Paper]``."""
        if isinstance(source, ReferenceList):
            return source.flatten()
        if isinstance(source, list):
            return [p if isinstance(p, Paper) else Paper.from_dict(p) for p in source]
        if isinstance(source, dict):
            # Could be {group: [paper, ...]} or a single paper dict
            out: List[Paper] = []
            for v in source.values():
                if isinstance(v, list):
                    out.extend(p if isinstance(p, Paper) else Paper.from_dict(p) for p in v)
                elif isinstance(v, dict):
                    out.append(Paper.from_dict(v))
                elif isinstance(v, Paper):
                    out.append(v)
            return out
        # Iterable fallback
        return list(source)
