"""Konversi SCImago CSV ke JSON terstruktur.

SCImago membagi file CSV dengan delimiter `;` dan kolom:
    Title, Issn, Open Access, Open Access Diamond, SJR Best Quartile,
    Categories (Q1);(Q2);..., Areas;...

Fungsi ini membaca CSV, mem-parsing field ISSN (bisa 1 atau 2 ISSN
dipisah koma), dan menulis JSON terstruktur:
    {
        "journal": str,
        "issn_print": str,
        "issn_electronic": str,
        "quartile": str,
        "open_access": "Yes" | "No" | "Diamond OA",
        "subject_area": [str, ...],
        "sub_category": [str, ...]
    }

Setara dengan script lama: journal-lists/csv_to_json.py
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import List, Tuple

from ..config import get_config
from ..utils import print_done, print_header, save_json, setup_logging


DESCRIPTION = "Konversi SCImago CSV ke JSON terstruktur"


# =============================================================================
# Helper parsing
# =============================================================================

def format_issn(issn_str: str) -> str:
    """Lengkapi ISSN ke format XXXX-XXXX.

    Menerima ISSN tanpa dash ("12345678") dan mengembalikannya dengan dash
    ("1234-5678"). Jika panjang bukan 8 digit, kembalikan apa adanya.

    Args:
        issn_str: ISSN mungkin tanpa dash.

    Returns:
        ISSN dengan dash, atau input asli jika tidak sesuai pola.
    """
    if not issn_str:
        return ""
    digits = issn_str.strip().replace("-", "")
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:]}"
    return digits


def parse_issns(issn_field: str) -> Tuple[str, str]:
    """Parse field Issn dari SCImago CSV.

    Format SCImago: "Issn_print,Issn_electronic" (dipisah koma).
    M12: Sebelumnya, jika hanya 1 ISSN, dianggap sebagai issn_electronic.
    Padahal SCImago bisa beri 1 ISSN yang sebenarnya print. Fix: jika hanya
    1 ISSN, kita tidak bisa tahu apakah print atau electronic — set sebagai
    issn_print (konservatif, agar step 01 tahu ini bukan electronic pasti).
    Step 01 hanya ambil issn_electronic, jadi jurnal ini akan ter-skip
    (yang merupakan behavior yang benar).

    Args:
        issn_field: String field Issn dari CSV.

    Returns:
        Tuple (issn_print, issn_electronic). Kosong jika tidak ada.
    """
    if not issn_field:
        return ("", "")

    parts = [p.strip() for p in issn_field.split(",")]
    if len(parts) == 1:
        # M12: Hanya 1 ISSN — tidak bisa tentukan print/electronic.
        # Set sebagai issn_print (konservatif). issn_electronic kosong.
        # Step 01 (yang ambil issn_electronic) akan skip jurnal ini,
        # yang lebih aman daripada salah klasifikasi.
        return (format_issn(parts[0]), "")
    if len(parts) >= 2:
        return (format_issn(parts[0]), format_issn(parts[1]))
    return ("", "")


def determine_open_access(oa_value: str, oa_diamond_value: str) -> str:
    """Tentukan label Open Access dari dua kolom SCImago.

    Prioritas: Diamond OA > Yes > No.

    Args:
        oa_value: Nilai kolom "Open Access" ("Yes"/"No"/"").
        oa_diamond_value: Nilai kolom "Open Access Diamond" ("Yes"/"No"/"").

    Returns:
        "Diamond OA" | "Yes" | "No".
    """
    oa = (oa_value or "").strip()
    oa_diamond = (oa_diamond_value or "").strip()
    if oa_diamond.upper() == "YES":
        return "Diamond OA"
    if oa.upper() == "YES":
        return "Yes"
    return "No"


def extract_sub_categories(categories_field: str) -> List[str]:
    """Parse kolom Categories SCImago.

    Format SCImago: "Cat1 (Q1); Cat2 (Q2); Cat3 (Q3)".
    Fungsi menghapus label quartile (Q1..Q4) dan mengembalikan list kategori.

    Args:
        categories_field: String field Categories.

    Returns:
        List nama kategori tanpa label quartile.
    """
    if not categories_field:
        return []
    categories = [c.strip() for c in categories_field.split(";")]
    result: List[str] = []
    for cat in categories:
        cleaned = cat
        for q in [" (Q1)", " (Q2)", " (Q3)", " (Q4)", " (Q0)", " (Not covered)"]:
            cleaned = cleaned.replace(q, "")
        cleaned = cleaned.strip()
        if cleaned:
            result.append(cleaned)
    return result


def extract_subject_areas(areas_field: str) -> List[str]:
    """Parse kolom Areas SCImago.

    Format SCImago: "Area1; Area2; Area3" (dipisah titik koma).

    Args:
        areas_field: String field Areas.

    Returns:
        List subject area non-kosong.
    """
    if not areas_field:
        return []
    areas = [a.strip() for a in areas_field.split(";")]
    return [a for a in areas if a]


# =============================================================================
# Proses CSV utuh
# =============================================================================

def process_csv_to_json(csv_filepath: str, json_filepath: str) -> int:
    """Baca SCImago CSV dan tulis JSON terstruktur.

    Args:
        csv_filepath: Path file CSV SCImago.
        json_filepath: Path file JSON output.

    Returns:
        Jumlah entri jurnal yang berhasil dikonversi.

    Raises:
        SystemExit: jika file CSV tidak ditemukan atau header tidak valid.
    """
    if not os.path.exists(csv_filepath):
        print(f"Error: File CSV tidak ditemukan: {csv_filepath}")
        sys.exit(1)

    with open(csv_filepath, "r", encoding="utf-8") as f:
        # Baca header manual karena SCImago pakai delimiter `;` di seluruh baris
        header_line = f.readline()
        headers = [h.strip() for h in header_line.strip().split(";")]

        # Mapping kolom yang dibutuhkan
        expected_fields = {
            "Title": None,
            "Issn": None,
            "Open Access": None,
            "Open Access Diamond": None,
            "SJR Best Quartile": None,
            "Categories": None,
            "Areas": None,
        }
        for idx, h in enumerate(headers):
            if h in expected_fields:
                expected_fields[h] = idx

        missing = [k for k, v in expected_fields.items() if v is None]
        if missing:
            print(f"Warning: Kolom berikut tidak ditemukan di CSV: {missing}")
            print(f"Header yang tersedia: {headers}")

        idx_title = expected_fields["Title"]
        idx_issn = expected_fields["Issn"]
        idx_oa = expected_fields["Open Access"]
        idx_oa_diamond = expected_fields["Open Access Diamond"]
        idx_quartile = expected_fields["SJR Best Quartile"]
        idx_categories = expected_fields["Categories"]
        idx_areas = expected_fields["Areas"]

        reader = csv.reader(f, delimiter=";")
        result: List[dict] = []

        for row in reader:
            if not row or all(cell.strip() == "" for cell in row):
                continue

            def get(idx: int | None) -> str:
                if idx is None or idx >= len(row):
                    return ""
                return row[idx].strip('"').strip()

            title = get(idx_title)
            issn_field = get(idx_issn)
            oa_value = get(idx_oa)
            oa_diamond_value = get(idx_oa_diamond)
            quartile_value = get(idx_quartile)
            categories_field = get(idx_categories)
            areas_field = get(idx_areas)

            issn_print, issn_electronic = parse_issns(issn_field)
            open_access = determine_open_access(oa_value, oa_diamond_value)
            sub_categories = extract_sub_categories(categories_field)
            subject_areas = extract_subject_areas(areas_field)

            entry = {
                "journal": title,
                "issn_print": issn_print,
                "issn_electronic": issn_electronic,
                "quartile": quartile_value,
                "open_access": open_access,
                "subject_area": subject_areas,
                "sub_category": sub_categories,
            }
            result.append(entry)

    save_json(result, json_filepath)
    return len(result)


# =============================================================================
# Entry point
# =============================================================================

def run(csv_path: str | None = None, json_path: str | None = None) -> int:
    """Entry point untuk konversi CSV -> JSON.

    Args:
        csv_path: Path CSV input. None = pakai config (scimago_csv).
        json_path: Path JSON output. None = pakai config (scimago_json).

    Returns:
        Jumlah entri yang dikonversi.
    """
    log = setup_logging()
    cfg = get_config()
    csv_filepath = csv_path or cfg["paths"]["scimago_csv"]
    json_filepath = json_path or cfg["paths"]["scimago_json"]

    print_header("Konversi SCImago CSV ke JSON")
    print(f"  Input  CSV : {csv_filepath}")
    print(f"  Output JSON: {json_filepath}")
    print()

    total = process_csv_to_json(csv_filepath, json_filepath)
    print(f"\nBerhasil! {total} entri jurnal telah dikonversi.")
    print(f"Output disimpan di: {json_filepath}")

    print_done(f"Konversi selesai — {total} entri")
    return total


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register subcommand untuk csv-to-json."""
    parser = subparsers.add_parser(
        "csv-to-json",
        help=DESCRIPTION,
        description=DESCRIPTION,
    )
    parser.add_argument("csv_path", nargs="?", default=None, help="Path CSV input")
    parser.add_argument("json_path", nargs="?", default=None, help="Path JSON output")
    parser.set_defaults(func=lambda args: run(csv_path=args.csv_path, json_path=args.json_path))
