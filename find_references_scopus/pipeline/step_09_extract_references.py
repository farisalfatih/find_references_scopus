"""Step 09: Format artikel jadi Markdown ringkas (DOI, author, abstrak).

Input  : data/07_with_journal_info.json  (output step 07)
Output : data/09_references.md

Perilaku:
   - Untuk setiap artikel, cetak format:
       # <DOI>
       ## <Author formatted>
       ### <Abstrak>
   - Format author: "Last1", "Last1 and Last2", atau "Last1 et al."
   - Output bisa di-pakai sebagai input untuk LLM saat verifikasi klaim

Setara dengan script lama: extract_references.py
"""

from __future__ import annotations

import argparse
from typing import Dict, List

from ..config import get_config
from ..utils import (
    format_authors_full,
    load_json,
    print_done,
    print_header,
    save_text,
    setup_logging,
)


DESCRIPTION = "Format artikel jadi Markdown ringkas (DOI, author, abstrak)"

# Tag untuk find-refs list (M13: auto-derived dari module attribute)
MANUAL_OR_AUTO = "AUTO"


def _escape_markdown(text: str) -> str:
    """Escape karakter khusus Markdown di teks field.

    L9: Jika title/abstract mengandung #, *, _, [, ], dll — bisa merusak
    struktur Markdown output. Escape dengan backslash.

    Args:
        text: String input.

    Returns:
        String yang sudah di-escape untuk Markdown.
    """
    if not text:
        return ""
    # Escape karakter yang punya arti khusus di Markdown
    chars_to_escape = ["\\", "*", "_", "`", "#"]
    for ch in chars_to_escape:
        text = text.replace(ch, "\\" + ch)
    return text


def build_references_markdown(data: Dict[str, List[dict]]) -> str:
    """Bangun dokumen Markdown dari struktur {kategori: [artikel, ...]}.

    Args:
        data: Mapping kategori -> list artikel.

    Returns:
        String Markdown siap ditulis ke file.
    """
    lines: List[str] = []
    for category, papers in data.items():
        lines.append(f"# Kategori: {category}")
        lines.append("")
        lines.append(f"Total: {len(papers)} artikel")
        lines.append("")
        lines.append("---")
        lines.append("")

        for paper in papers:
            doi = paper.get("doi", "No DOI") or "No DOI"
            authors = paper.get("authors", [])
            abstract = paper.get("abstract", "No abstract") or "No abstract"
            year = paper.get("year", "")
            journal = paper.get("journal", "")

            formatted_authors = format_authors_full(authors)

            # L9: escape karakter Markdown di field agar tidak rusak struktur
            lines.append(f"## {doi}")
            if year or journal:
                meta = " | ".join(str(x) for x in [year, journal] if x)
                lines.append(f"**{_escape_markdown(str(meta))}**")
            lines.append(f"### {_escape_markdown(formatted_authors)}")
            lines.append("")
            lines.append(_escape_markdown(abstract))
            lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines)


def run(input_file: str | None = None, output_file: str | None = None) -> int:
    """Entry point step 09.

    Args:
        input_file: Path JSON input. None = pakai config (step_07_with_journal_info).
        output_file: Path Markdown output. None = pakai config (step_09_references_md).

    Returns:
        Jumlah total artikel yang diformat.
    """
    log = setup_logging()
    cfg = get_config()
    input_path = input_file or cfg["paths"]["step_07_with_journal_info"]
    output_path = output_file or cfg["paths"]["step_09_references_md"]

    print_header("Step 09: Format Artikel ke Markdown Ringkas")
    log.info(f"Input  : {input_path}")
    log.info(f"Output : {output_path}")

    try:
        data = load_json(input_path)
    except FileNotFoundError:
        log.error(f"File input tidak ditemukan: {input_path}")
        return 0

    markdown = build_references_markdown(data)
    save_text(markdown, output_path)

    total = sum(len(papers) for papers in data.values() if isinstance(papers, list))
    print(f"\nTotal artikel diformat: {total}")

    print_done(f"Step 09 selesai — {total} artikel dijadikan Markdown")
    return total


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register subcommand untuk step 09."""
    parser = subparsers.add_parser(
        "extract-references",
        help=DESCRIPTION,
        description=DESCRIPTION,
    )
    parser.add_argument("-i", "--input", default=None, help="File JSON input (default: step 07)")
    parser.add_argument("-o", "--output", default=None, help="File Markdown output (default: step 09)")
    parser.set_defaults(func=lambda args: run(input_file=args.input, output_file=args.output))
