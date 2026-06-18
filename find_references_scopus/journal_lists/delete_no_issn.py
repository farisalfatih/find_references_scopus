"""Hapus jurnal tanpa ISSN electronic dari SCImago JSON.

Input  : data/scimagojr_2025.json       (default)
Output : data/scimagojr_2025_ok.json    (default)

Perilaku:
   - Filter jurnal yang PUNYA issn_electronic non-kosong
   - Cetak statistik: total awal, dihapus, akhir
   - Cetak daftar record yang dihapus (judul jurnalnya)

Setara dengan script lama: journal-lists/delete_no_issn.py
"""

from __future__ import annotations

import argparse
from typing import List, Tuple

from ..config import get_config
from ..utils import load_json, print_done, print_header, save_json, setup_logging


DESCRIPTION = "Hapus jurnal tanpa ISSN electronic dari SCImago JSON"


def filter_no_issn(data: List[dict]) -> Tuple[List[dict], List[Tuple[int, dict]]]:
    """Pisahkan jurnal yang punya ISSN electronic vs yang tidak.

    Args:
        data: List jurnal dari SCImago JSON.

    Returns:
        Tuple (jurnal_dengan_issn, [(idx, jurnal_tanpa_issn), ...]).
        Index dimulai dari 1 sesuai urutan input.
    """
    data_baru: List[dict] = []
    record_dihapus: List[Tuple[int, dict]] = []
    for idx, item in enumerate(data, start=1):
        issn_electronic = item.get("issn_electronic")
        ada_electronic = bool(issn_electronic and issn_electronic.strip())
        if ada_electronic:
            data_baru.append(item)
        else:
            record_dihapus.append((idx, item))
    return data_baru, record_dihapus


def run(input_path: str | None = None, output_path: str | None = None) -> int:
    """Entry point untuk delete-no-issn.

    Args:
        input_path: Path JSON input. None = pakai config (scimago_json).
        output_path: Path JSON output. None = pakai config (scimago_clean).

    Returns:
        Jumlah record setelah filtering.
    """
    log = setup_logging()
    cfg = get_config()
    in_path = input_path or cfg["paths"]["scimago_json"]
    out_path = output_path or cfg["paths"]["scimago_clean"]

    print_header("Hapus Jurnal Tanpa ISSN Electronic")
    log.info(f"Input  : {in_path}")
    log.info(f"Output : {out_path}")

    try:
        data = load_json(in_path)
    except FileNotFoundError:
        log.error(f"File tidak ditemukan: {in_path}")
        return 0
    except Exception as e:
        log.error(f"Gagal membaca {in_path}: {e}")
        return 0

    if not isinstance(data, list):
        log.error("Isi JSON harus berupa array (list) dari objek.")
        return 0

    total_awal = len(data)
    data_baru, record_dihapus = filter_no_issn(data)
    total_akhir = len(data_baru)
    jumlah_dihapus = total_awal - total_akhir

    save_json(data_baru, out_path)

    print()
    print(f"  Total record awal   : {total_awal}")
    print(f"  Total record dihapus: {jumlah_dihapus}")
    print(f"  Total record akhir  : {total_akhir}")
    print(f"  File bersih         : {out_path}")

    if record_dihapus:
        print("\nDaftar record yang dihapus:")
        for urutan, rec in record_dihapus:
            print(f"  - Record ke-{urutan}: {rec.get('journal', 'Tidak ada judul')}")

    print_done(f"Penghapusan selesai — {total_akhir} record tersisa")
    return total_akhir


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register subcommand untuk delete-no-issn."""
    parser = subparsers.add_parser(
        "delete-no-issn",
        help=DESCRIPTION,
        description=DESCRIPTION,
    )
    parser.add_argument("input_path", nargs="?", default=None, help="Path JSON input")
    parser.add_argument("output_path", nargs="?", default=None, help="Path JSON output")
    parser.set_defaults(func=lambda args: run(input_path=args.input_path, output_path=args.output_path))
