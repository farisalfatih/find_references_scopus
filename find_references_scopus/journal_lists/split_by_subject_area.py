"""Pecah SCImago JSON per subject area.

Input  : data/scimagojr_2025.json       (default)
Output : data/scimago_split/             (direktori berisi file per subject area)
         + _index.json                   (ringkasan jumlah per area)

Perilaku:
   - Klasifikasikan setiap jurnal ke subject area-nya (bisa >1 per jurnal)
   - Tulis satu file JSON per subject area: subject_area_<Nama_Area>.json
   - Tulis _index.json berisi ringkasan {subject_area, file, total_journals}
   - Nama file di-sanitize (koma dihapus, slash jadi underscore, spasi jadi underscore)

Setara dengan script lama: journal-lists/split_by_subject_area.py
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Dict, List

from ..config import get_config
from ..utils import load_json, print_done, print_header, save_json, setup_logging


DESCRIPTION = "Pecah SCImago JSON per subject area"


def sanitize_filename(name: str) -> str:
    """Bersihkan string agar aman dipakai sebagai nama file.

    Aturan:
      - Koma (,) dihapus
      - Slash (/ dan \\) jadi underscore (_)
      - Spasi ganda/whitespace jadi underscore tunggal

    Args:
        name: Nama subject area mentah.

    Returns:
        Nama file yang sudah di-sanitize.
    """
    sanitized = re.sub(r"[,]", "", name)
    sanitized = re.sub(r"[/\\]", "_", sanitized)
    sanitized = re.sub(r"\s+", "_", sanitized.strip())
    return sanitized


def split_by_subject_area(journals: List[dict], output_dir: str) -> List[dict]:
    """Tulis file JSON per subject area dan kembalikan ringkasan index.

    Args:
        journals: List jurnal dari SCImago JSON.
        output_dir: Direktori output (akan dibuat jika belum ada).

    Returns:
        List dict {subject_area, file, total_journals} untuk _index.json.
    """
    print(f"Total jurnal: {len(journals)}")

    # Kelompokkan jurnal per subject_area
    area_dict: Dict[str, List[dict]] = {}
    area_count: Dict[str, int] = {}
    for journal in journals:
        subject_areas = journal.get("subject_area", [])
        for area in subject_areas:
            if area not in area_dict:
                area_dict[area] = []
                area_count[area] = 0
            area_dict[area].append(journal)
            area_count[area] += 1

    os.makedirs(output_dir, exist_ok=True)

    # Tulis satu file per area — pakai save_json dari utils (L3: konsistensi)
    for area, journal_list in sorted(area_dict.items()):
        safe_name = sanitize_filename(area)
        filename = f"subject_area_{safe_name}.json"
        filepath = os.path.join(output_dir, filename)
        save_json(journal_list, filepath)

    # Bangun ringkasan index
    summary: List[dict] = []
    for area in sorted(area_dict.keys()):
        safe_name = sanitize_filename(area)
        summary.append({
            "subject_area": area,
            "file": f"subject_area_{safe_name}.json",
            "total_journals": area_count[area],
        })

    return summary


def run(input_path: str | None = None, output_dir: str | None = None) -> int:
    """Entry point untuk split-subject.

    Args:
        input_path: Path JSON SCImago. None = pakai config (scimago_json).
        output_dir: Direktori output. None = pakai config (scimago_split_dir).

    Returns:
        Jumlah subject area yang ditemukan.
    """
    log = setup_logging()
    cfg = get_config()
    in_path = input_path or cfg["paths"]["scimago_json"]
    out_dir = output_dir or cfg["paths"]["scimago_split_dir"]

    print_header("Pecah SCImago JSON per Subject Area")
    log.info(f"Input  : {in_path}")
    log.info(f"Output : {out_dir}")

    if not os.path.exists(in_path):
        log.error(f"File JSON tidak ditemukan: {in_path}")
        sys.exit(1)

    try:
        journals = load_json(in_path)
    except Exception as e:
        log.error(f"Gagal membaca {in_path}: {e}")
        sys.exit(1)

    summary = split_by_subject_area(journals, out_dir)

    # Tulis _index.json
    summary_path = os.path.join(out_dir, "_index.json")
    save_json(summary, summary_path)

    print(f"\nTotal subject_area ditemukan: {len(summary)}")
    print(f"File JSON disimpan di: {os.path.abspath(out_dir)}\n")

    print(f"{'No.':<5} {'Subject Area':<60} {'Jumlah':<10} {'File'}")
    print("-" * 140)
    for idx, item in enumerate(summary, 1):
        print(f"{idx:<5} {item['subject_area']:<60} {item['total_journals']:<10} {item['file']}")

    print(f"\nFile index: {summary_path}")
    print(f"Total {len(summary)} file JSON + 1 file index berhasil dibuat.")

    print_done(f"Split selesai — {len(summary)} subject area")
    return len(summary)


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register subcommand untuk split-subject."""
    parser = subparsers.add_parser(
        "split-subject",
        help=DESCRIPTION,
        description=DESCRIPTION,
    )
    parser.add_argument("input_path", nargs="?", default=None, help="Path JSON SCImago")
    parser.add_argument("output_dir", nargs="?", default=None, help="Direktori output")
    parser.set_defaults(func=lambda args: run(input_path=args.input_path, output_dir=args.output_dir))
