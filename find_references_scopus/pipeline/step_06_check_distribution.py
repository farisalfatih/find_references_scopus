"""Step 06: Tampilkan distribusi artikel per kategori.

Input  : data/05_cleaned.json        (output step 05)
Output : data/06_distribution.txt    (laporan teks distribusi)

Perilaku:
   - Hitung jumlah artikel per kategori (group)
   - Tampilkan ke stdout dan simpan ke file .txt
   - Sertakan total keseluruhan

Setara dengan script lama: cek_distribusi_artikel.py
"""

from __future__ import annotations

import argparse
from typing import Dict

from ..config import get_config
from ..utils import load_json, print_done, print_header, save_text, setup_logging


DESCRIPTION = "Tampilkan distribusi artikel per kategori"

# Tag untuk find-refs list (M13: auto-derived dari module attribute)
MANUAL_OR_AUTO = "AUTO"


def build_distribution_report(data: Dict[str, list]) -> str:
    """Bangun laporan teks distribusi artikel per kategori.

    L6: Handle data kosong/non-dict dengan gracefully — sebelumnya akan crash
    kalau input adalah {} atau nilai bukan list.

    Args:
        data: Mapping kategori -> list artikel.

    Returns:
        String laporan siap ditulis ke file atau dicetak.
    """
    lines: list[str] = []
    lines.append("Distribusi jumlah artikel per kategori:")
    lines.append("")

    # L6: Handle input yang bukan dict atau kosong
    if not isinstance(data, dict):
        lines.append(f"  (input bukan dict: {type(data).__name__})")
        lines.append("")
        lines.append("Total semua artikel: 0")
        return "\n".join(lines) + "\n"

    if not data:
        lines.append("  (tidak ada kategori)")
        lines.append("")
        lines.append("Total semua artikel: 0")
        return "\n".join(lines) + "\n"

    for category, articles in data.items():
        # L6: Handle value yang bukan list
        count = len(articles) if isinstance(articles, list) else 0
        lines.append(f"  {category}: {count} artikel")
    total = sum(
        len(articles) for articles in data.values() if isinstance(articles, list)
    )
    lines.append("")
    lines.append(f"Total semua artikel: {total}")
    return "\n".join(lines) + "\n"


def run(input_file: str | None = None, output_file: str | None = None) -> int:
    """Entry point step 06.

    Args:
        input_file: Path JSON. None = pakai config (step_05_cleaned).
        output_file: Path output .txt. None = pakai config (step_06_distribution).

    Returns:
        Total artikel.
    """
    log = setup_logging()
    cfg = get_config()
    input_path = input_file or cfg["paths"]["step_05_cleaned"]
    output_path = output_file or cfg["paths"]["step_06_distribution"]

    print_header("Step 06: Distribusi Artikel per Kategori")
    log.info(f"Input  : {input_path}")
    log.info(f"Output : {output_path}")

    try:
        data = load_json(input_path)
    except FileNotFoundError:
        log.error(f"File input tidak ditemukan: {input_path}")
        return 0

    report = build_distribution_report(data)
    print()
    print(report)

    save_text(report, output_path)
    total = sum(len(articles) for articles in data.values())

    print_done(f"Step 06 selesai — distribusi {total} artikel")
    return total


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register subcommand untuk step 06."""
    parser = subparsers.add_parser(
        "distribution",
        help=DESCRIPTION,
        description=DESCRIPTION,
    )
    parser.add_argument("-i", "--input", default=None, help="File JSON input (default: step 05)")
    parser.add_argument("-o", "--output", default=None, help="File .txt output (default: step 06)")
    parser.set_defaults(func=lambda args: run(input_file=args.input, output_file=args.output))
