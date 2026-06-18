"""Inspeksi kelengkapan ISSN print & electronic di SCImago JSON.

Input  : data/scimagojr_2025.json  (default)
Output : (hanya cetak ke stdout)

Perilaku:
   - Hitung berapa jurnal yang punya ISSN print saja, ISSN electronic saja,
     keduanya, atau tidak ada sama sekali
   - Cetak daftar record yang tidak punya ISSN sama sekali
   - Berguna untuk audit kualitas data sebelum pipeline

Setara dengan script lama: journal-lists/cek_issn.py
"""

from __future__ import annotations

import argparse
import json
from typing import List, Tuple

from ..config import get_config
from ..utils import load_json, print_done, print_header, setup_logging


DESCRIPTION = "Inspeksi kelengkapan ISSN print & electronic di SCImago JSON"


def inspect_issn(data: List[dict], verbose: bool = False) -> None:
    """Cetak laporan inspeksi ISSN ke stdout.

    M11: Sebelumnya cetak SETIAP record ke stdout (32k+ baris untuk SCImago full).
    Fix: default hanya cetak ringkasan + daftar record tanpa ISSN.
    Set verbose=True untuk cetak semua record.

    Args:
        data: List jurnal dari SCImago JSON.
        verbose: Jika True, cetak setiap record ISSN print/electronic.
    """
    total_data = len(data)
    total_issn_print = 0
    total_issn_electronic = 0
    hanya_print = 0
    hanya_electronic = 0
    tidak_ada_keduanya = 0
    data_tanpa_issn: List[Tuple[int, dict]] = []

    if verbose:
        print("Daftar ISSN Print dan ISSN Electronic:")
        print("-" * 50)

    for idx, item in enumerate(data, start=1):
        issn_print = item.get("issn_print")
        issn_electronic = item.get("issn_electronic")

        ada_print = bool(issn_print and issn_print.strip())
        ada_electronic = bool(issn_electronic and issn_electronic.strip())

        if ada_print:
            total_issn_print += 1
        if ada_electronic:
            total_issn_electronic += 1

        if ada_print and not ada_electronic:
            hanya_print += 1
        elif ada_electronic and not ada_print:
            hanya_electronic += 1
        elif not ada_print and not ada_electronic:
            tidak_ada_keduanya += 1
            data_tanpa_issn.append((idx, item))

        if verbose:
            print(f"{idx}. ISSN Print: {issn_print or 'Tidak ada'} | "
                  f"ISSN Electronic: {issn_electronic or 'Tidak ada'}")

    print("\n" + "=" * 50)
    print("RINGKASAN TOTAL:")
    print(f"  Total record                                     : {total_data}")
    print(f"  Record dengan ISSN print                        : {total_issn_print}")
    print(f"  Record dengan ISSN electronic                   : {total_issn_electronic}")
    print(f"  Record dengan ISSN print SAJA                   : {hanya_print}")
    print(f"  Record dengan ISSN electronic SAJA              : {hanya_electronic}")
    print(f"  Record TANPA ISSN print & electronic sama sekali: {tidak_ada_keduanya}")
    print("=" * 50)

    if data_tanpa_issn:
        print(f"\nDETAIL {len(data_tanpa_issn)} RECORD TANPA ISSN:")
        print("=" * 50)
        for urutan, record in data_tanpa_issn:
            print(f"\n--- Record ke-{urutan} ---")
            print(json.dumps(record, indent=2, ensure_ascii=False))
    else:
        print("\nTidak ada record tanpa ISSN.")


def run(json_path: str | None = None, verbose: bool = False) -> int:
    """Entry point untuk inspeksi ISSN.

    Args:
        json_path: Path JSON SCImago. None = pakai config.
        verbose: Jika True, cetak setiap record ISSN (bukan hanya ringkasan).

    Returns:
        1 jika sukses, 0 jika gagal.
    """
    log = setup_logging()
    cfg = get_config()
    path = json_path or cfg["paths"]["scimago_json"]

    print_header("Inspeksi ISSN SCImago")
    log.info(f"Input: {path}")
    if verbose:
        log.info("Mode: verbose (cetak semua record)")
    else:
        log.info("Mode: ringkasan (gunakan --verbose untuk lihat semua record)")

    try:
        data = load_json(path)
    except FileNotFoundError:
        log.error(f"File tidak ditemukan: {path}")
        return 0
    except Exception as e:
        log.error(f"Gagal membaca {path}: {e}")
        return 0

    if not isinstance(data, list):
        log.error("Isi JSON harus berupa array (list) dari objek.")
        return 0

    inspect_issn(data, verbose=verbose)

    print_done("Inspeksi ISSN selesai")
    return 1


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register subcommand untuk check-issn."""
    parser = subparsers.add_parser(
        "check-issn",
        help=DESCRIPTION,
        description=DESCRIPTION,
    )
    parser.add_argument("json_path", nargs="?", default=None, help="Path JSON SCImago")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Cetak setiap record ISSN (bukan hanya ringkasan)",
    )
    parser.set_defaults(func=lambda args: run(json_path=args.json_path, verbose=args.verbose))
