"""Step 10: Pilih subset artikel berdasarkan daftar DOI.

Input  : data/07_with_journal_info.json  (output step 07)
         config.yaml (selected_dois)
Output : data/10_selected.json

Perilaku:
   - Bangun index DOI -> artikel dari file input
   - Ambil artikel-artikel yang DOI-nya ada di config.selected_dois
   - Laporkan DOI yang tidak ditemukan (warning)
   - Tampilkan ringkasan: judul, tahun, author pertama

Catatan: Daftar DOI tidak lagi hard-coded di source code. Edit di config.yaml
di bagian `selected_dois`. Bisa juga override via flag --dois-file.

Setara dengan script lama: selected_article.py
"""

from __future__ import annotations

import argparse
import os
from typing import Dict, List

from ..config import get_config, PROJECT_ROOT
from ..utils import load_json, load_lines, print_done, print_header, save_json, setup_logging


DESCRIPTION = "Pilih subset artikel berdasarkan daftar DOI dari config"

# Tag untuk find-refs list (M13: auto-derived dari module attribute)
MANUAL_OR_AUTO = "MANUAL"


def build_doi_index(data: Dict[str, List[dict]]) -> Dict[str, dict]:
    """Bangun index DOI -> artikel dari struktur {kategori: [artikel, ...]}.

    DOI dinormalisasi ke lowercase karena DOI case-insensitive per spesifikasi
    Crossref. Lookup juga harus lowercase.

    Args:
        data: Mapping kategori -> list artikel.

    Returns:
        Mapping doi_lowercase -> artikel. Jika DOI duplikat antar kategori,
        artikel pertama yang ditemukan yang dipakai.
    """
    doi_to_paper: Dict[str, dict] = {}
    for category, papers in data.items():
        for paper in papers:
            doi = paper.get("doi")
            if doi:
                doi_to_paper[doi.lower()] = paper
    return doi_to_paper


def run(input_file: str | None = None, output_file: str | None = None,
        dois_file: str | None = None) -> int:
    """Entry point step 10.

    Args:
        input_file: Path JSON sumber. None = pakai config (step_07_with_journal_info).
        output_file: Path JSON output. None = pakai config (step_10_selected).
        dois_file: Path file txt berisi DOI (satu per baris). Jika None,
            pakai config.selected_dois.

    Returns:
        Jumlah artikel yang berhasil ditemukan.
    """
    log = setup_logging()
    cfg = get_config()
    input_path = input_file or cfg["paths"]["step_07_with_journal_info"]
    output_path = output_file or cfg["paths"]["step_10_selected"]

    # Sumber daftar DOI:
    # 1. Flag CLI --dois-file
    # 2. config.yaml `selected_dois` (bisa list atau string path)
    # 3. config.yaml `paths.selected_dois` (file data/selected_dois.txt)
    doi_list: List[str] = []
    if dois_file:
        doi_list = load_lines(dois_file)
        log.info(f"Memuat DOI dari file CLI: {dois_file} ({len(doi_list)} DOI)")
    else:
        cfg_selected = cfg.get("selected_dois")
        if isinstance(cfg_selected, str) and cfg_selected.strip():
            # Jika berupa path ke file
            doi_path = cfg_selected if os.path.isabs(cfg_selected) else os.path.join(str(PROJECT_ROOT), cfg_selected)
            if os.path.isfile(doi_path):
                doi_list = load_lines(doi_path)
                log.info(f"Memuat DOI dari file config ({doi_path}): {len(doi_list)} DOI")
        elif isinstance(cfg_selected, list) and cfg_selected:
            # Jika berupa list DOI
            doi_list = [str(d).strip() for d in cfg_selected if str(d).strip() and not str(d).strip().startswith("#")]
            log.info(f"Memuat DOI dari list config.yaml ({len(doi_list)} DOI)")
        
        # Fallback ke paths.selected_dois jika list masih kosong
        if not doi_list and "selected_dois" in cfg.get("paths", {}):
            selected_dois_path = cfg["paths"]["selected_dois"]
            if os.path.isfile(selected_dois_path):
                doi_list = load_lines(selected_dois_path)
                if doi_list:
                    log.info(f"Memuat DOI dari {selected_dois_path} ({len(doi_list)} DOI)")

    if not doi_list:
        log.error(
            "Daftar DOI kosong. Tulis DOI di data/selected_dois.txt, "
            "isi `selected_dois` di config.yaml, atau gunakan opsi --dois-file."
        )
        return 0

    print_header("Step 10: Pilih Artikel Berdasarkan DOI")
    log.info(f"Input  : {input_path}")
    log.info(f"Output : {output_path}")
    log.info(f"DOIs   : {len(doi_list)} DOI dicari")

    try:
        data = load_json(input_path)
    except FileNotFoundError:
        log.error(f"File input tidak ditemukan: {input_path}")
        return 0

    doi_to_paper = build_doi_index(data)
    log.info(f"Index DOI dari input: {len(doi_to_paper)} DOI unik")

    found: List[dict] = []
    not_found: List[str] = []
    for doi in doi_list:
        # Normalisasi lookup ke lowercase (case-insensitive)
        paper = doi_to_paper.get(doi.lower())
        if paper:
            found.append(paper)
        else:
            not_found.append(doi)

    if not_found:
        print(f"\nWarning: {len(not_found)} DOI tidak ditemukan:")
        for doi in not_found:
            print(f"  - {doi}")

    save_json(found, output_path)

    print(f"\nDitemukan: {len(found)} dari {len(doi_list)} DOI")
    print(f"Disimpan ke: {output_path}")

    if found:
        print("\nRingkasan artikel yang ditemukan:")
        for i, paper in enumerate(found, 1):
            title = paper.get("title", "No title") or "No title"
            authors = paper.get("authors", [])
            author_str = f"{authors[0]} et al." if authors else "Unknown"
            year = paper.get("year", "n.d.")
            print(f"  {i}. {title} ({year}) - {author_str}")

    print_done(f"Step 10 selesai — {len(found)} artikel terpilih")
    return len(found)


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register subcommand untuk step 10."""
    parser = subparsers.add_parser(
        "select-articles",
        help=DESCRIPTION,
        description=DESCRIPTION,
    )
    parser.add_argument("-i", "--input", default=None, help="File JSON input (default: step 07)")
    parser.add_argument("-o", "--output", default=None, help="File JSON output (default: step 10)")
    parser.add_argument(
        "-d", "--dois-file",
        default=None,
        help="File txt berisi DOI (satu per baris). Default: pakai config.selected_dois",
    )
    parser.set_defaults(func=lambda args: run(
        input_file=args.input,
        output_file=args.output,
        dois_file=args.dois_file,
    ))
