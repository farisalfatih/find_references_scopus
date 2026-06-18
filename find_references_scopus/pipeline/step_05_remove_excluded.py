"""Step 05: Hapus DOI yang ada di daftar exclude.

Input  : data/04_deduplicated.json   (output step 04)
         data/excluded_dois.txt      (DOI yang ingin di-exclude, satu per baris)
Output : data/05_cleaned.json

Perilaku:
   - Baca daftar DOI exclude (satu per baris, abaikan baris kosong)
   - Hapus setiap artikel yang DOI-nya ada di daftar exclude
   - Tampilkan statistik per kategori (sebelum -> sesudah -> dihapus)

Setara dengan script lama: remove_doi_list.py
"""

from __future__ import annotations

import argparse
from typing import Dict, List, Set

from ..config import get_config
from ..utils import load_json, load_lines, print_done, print_header, save_json, setup_logging


DESCRIPTION = "Hapus DOI yang ada di daftar exclude dari hasil deduplikasi"

# Tag untuk find-refs list (M13: auto-derived dari module attribute)
MANUAL_OR_AUTO = "MANUAL"


def run(input_file: str | None = None, output_file: str | None = None,
        excluded_file: str | None = None) -> int:
    """Entry point step 05.

    Args:
        input_file: Path JSON hasil step 04. None = pakai config.
        output_file: Path JSON output. None = pakai config (step_05_cleaned).
        excluded_file: Path file DOI exclude. None = pakai config (excluded_dois).

    Returns:
        Jumlah total artikel setelah exclude.
    """
    log = setup_logging()
    cfg = get_config()
    input_path = input_file or cfg["paths"]["step_04_deduplicated"]
    output_path = output_file or cfg["paths"]["step_05_cleaned"]
    excluded_path = excluded_file or cfg["paths"]["excluded_dois"]

    print_header("Step 05: Hapus DOI yang Ada di Daftar Exclude")
    log.info(f"Input  : {input_path}")
    log.info(f"Exclude: {excluded_path}")
    log.info(f"Output : {output_path}")

    try:
        data = load_json(input_path)
    except FileNotFoundError:
        log.error(f"File input tidak ditemukan: {input_path}")
        return 0

    try:
        excluded_dois: Set[str] = set(load_lines(excluded_path))
    except FileNotFoundError:
        log.error(f"File exclude tidak ditemukan: {excluded_path}")
        return 0

    log.info(f"Jumlah DOI di daftar exclude: {len(excluded_dois)}")

    cleaned_data: Dict[str, List[dict]] = {}
    total_removed = 0

    for category, papers in data.items():
        original_count = len(papers)
        filtered_papers = [p for p in papers if p.get("doi") not in excluded_dois]
        removed_count = original_count - len(filtered_papers)
        total_removed += removed_count
        cleaned_data[category] = filtered_papers
        print(f"  Kategori '{category}': {original_count} -> {len(filtered_papers)} (dihapus {removed_count})")

    save_json(cleaned_data, output_path)

    total_kept = sum(len(papers) for papers in cleaned_data.values())
    print(f"\nTotal paper dihapus: {total_removed}")
    print(f"Total paper tersisa: {total_kept}")

    print_done(f"Step 05 selesai — {total_kept} artikel tersisa")
    return total_kept


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register subcommand untuk step 05."""
    parser = subparsers.add_parser(
        "remove-excluded",
        help=DESCRIPTION,
        description=DESCRIPTION,
    )
    parser.add_argument("-i", "--input", default=None, help="File JSON input (default: step 04)")
    parser.add_argument("-o", "--output", default=None, help="File JSON output (default: step 05)")
    parser.add_argument(
        "-e", "--excluded",
        default=None,
        help="File daftar DOI exclude (default: data/excluded_dois.txt)",
    )
    parser.set_defaults(func=lambda args: run(
        input_file=args.input,
        output_file=args.output,
        excluded_file=args.excluded,
    ))
