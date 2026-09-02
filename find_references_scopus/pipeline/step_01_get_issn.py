"""Step 01: Ekstrak daftar ISSN electronic dari SCImago JSON.

Input  : data/scimagojr_2025.json          (SCImago full — default)
         data/scimago_split/subject_area_*.json  (per subject area, jika --subject dipakai)
Output : data/01_issn_list.txt             (satu ISSN per baris)

Perilaku:
   - Filter jurnal berdasarkan quartile (Q1/Q2/Q3/Q4 atau "semua")
   - Hanya ambil issn_electronic yang non-kosong
   - Tulis hasil ke file txt (satu ISSN per baris) supaya mudah di-reuse

Mode sumber data:
   1. SCImago full (default): pakai data/scimagojr_2025.json
   2. Subject area pilihan: pakai file di data/scimago_split/subject_area_*.json
      - --subject list         : tampilkan daftar subject area tersedia
      - --subject 1,3,5        : ambil ISSN dari subject area nomor 1, 3, 5
      - --subject Computer     : ambil ISSN dari subject area yang namanya
                                  mengandung "Computer" (case-insensitive)
      - --subject all          : gabungkan semua subject area (sama dengan full)
      - --subject "Computer Science,Mathematics"  : multi-name (pisah koma)

Setara dengan script lama:
   - get_issn_electronic.py
   - journal-lists/delete_no_issn.py (sebagian logika)
"""

from __future__ import annotations

import argparse
import os
from typing import Dict, List, Optional, Set

from ..config import get_config
from ..utils import load_json, print_done, print_header, save_text, setup_logging


DESCRIPTION = "Ekstrak ISSN electronic dari SCImago JSON berdasarkan quartile + subject area"

# Tag untuk find-refs list (M13: auto-derived dari module attribute)
MANUAL_OR_AUTO = "MANUAL"


# =============================================================================
# Load subject area index
# =============================================================================

def load_subject_area_index(split_dir: str) -> List[Dict]:
    """Load _index.json dari folder scimago_split.

    Args:
        split_dir: Path ke folder data/scimago_split/.

    Returns:
        List dict {subject_area, file, total_journals} berurutan.
        List kosong jika _index.json tidak ada.
    """
    index_path = os.path.join(split_dir, "_index.json")
    if not os.path.isfile(index_path):
        return []
    try:
        return load_json(index_path)
    except Exception:
        return []


def list_subject_areas(split_dir: str) -> None:
    """Cetak daftar subject area tersedia di scimago_split.

    Args:
        split_dir: Path ke folder data/scimago_split/.
    """
    index = load_subject_area_index(split_dir)
    if not index:
        print(f"Folder scimago_split tidak ditemukan atau kosong: {split_dir}")
        print("Jalankan dulu: find-refs split-subject")
        return

    print(f"Daftar subject area tersedia ({len(index)} area):\n")
    print(f"  {'No.':<5} {'Subject Area':<60} {'Jurnal':<10} File")
    print("  " + "-" * 110)
    for i, item in enumerate(index, 1):
        print(f"  {i:<5} {item['subject_area']:<60} {item['total_journals']:<10} {item['file']}")
    print()
    print("Cara pakai:")
    print("  find-refs get-issn --subject 1,3,5            # pilih nomor 1, 3, 5")
    print("  find-refs get-issn --subject Computer         # semua area yg namanya ada 'Computer'")
    print("  find-refs get-issn --subject all              # gabung semua area")
    print('  find-refs get-issn --subject "Computer Science,Mathematics"  # multi-name')


def resolve_subject_areas(
    subject_input: str,
    split_dir: str,
) -> List[str]:
    """Resolve input --subject jadi list nama file subject_area_*.json.

    Format input yang didukung:
      - "list"          : raise RuntimeError agar caller tahu untuk cetak daftar
      - "all"           : semua subject area
      - "1,3,5"         : pilih nomor urut di _index.json
      - "Computer"      : semua area yang namanya mengandung "Computer"
      - "A,B,C"         : multi-name (pisah koma, masing-masing dicocokkan)

    Args:
        subject_input: String input dari --subject.
        split_dir: Path ke folder data/scimago_split/.

    Returns:
        List path absolut ke file subject_area_*.json yang dipilih.

    Raises:
        RuntimeError: jika input == "list".
        ValueError: jika nomor tidak valid atau tidak ada match.
    """
    if subject_input.strip().lower() == "list":
        raise RuntimeError("LIST_REQUESTED")

    index = load_subject_area_index(split_dir)
    if not index:
        raise ValueError(
            f"Folder scimago_split belum ada atau kosong: {split_dir}\n"
            f"Jalankan dulu: find-refs split-subject"
        )

    selected_files: List[str] = []
    input_lower = subject_input.strip().lower()

    if input_lower == "all":
        # Semua subject area
        for item in index:
            selected_files.append(os.path.join(split_dir, item["file"]))
        return selected_files

    # Coba parse sebagai nomor (1,3,5)
    if all(p.strip().isdigit() for p in subject_input.split(",")):
        nums = [int(p.strip()) for p in subject_input.split(",")]
        for num in nums:
            if num < 1 or num > len(index):
                raise ValueError(
                    f"Nomor subject area {num} tidak valid. "
                    f"Rentang valid: 1-{len(index)}. Jalankan --subject list untuk lihat daftar."
                )
            selected_files.append(os.path.join(split_dir, index[num - 1]["file"]))
        return selected_files

    # Match berdasarkan nama (case-insensitive substring)
    keywords = [k.strip().lower() for k in subject_input.split(",") if k.strip()]
    for item in index:
        name_lower = item["subject_area"].lower()
        if any(kw in name_lower for kw in keywords):
            selected_files.append(os.path.join(split_dir, item["file"]))

    if not selected_files:
        raise ValueError(
            f"Tidak ada subject area yang namanya cocok dengan: {subject_input}\n"
            f"Jalankan --subject list untuk lihat daftar subject area tersedia."
        )

    return selected_files


def load_journals_from_subject_files(files: List[str]) -> List[dict]:
    """Load & gabungkan jurnal dari beberapa file subject_area_*.json.

    Jurnal yang sama (sama ISSN electronic) di multiple subject area akan
    di-dedup.

    Args:
        files: List path file subject_area_*.json.

    Returns:
        List jurnal unik (gabungan dari semua file).
    """
    journals: List[dict] = []
    seen_issn: Set[str] = set()
    for filepath in files:
        try:
            data = load_json(filepath)
        except Exception as e:
            print(f"  Warning: gagal load {filepath}: {e}")
            continue
        if not isinstance(data, list):
            continue
        for journal in data:
            issn = journal.get("issn_electronic")
            # Dedup berdasarkan ISSN electronic (kalau ada), kalau tidak ada pakai journal+issn_print
            key = issn if issn else f"{journal.get('journal', '')}|{journal.get('issn_print', '')}"
            if key in seen_issn:
                continue
            seen_issn.add(key)
            journals.append(journal)
    return journals


# =============================================================================
# ISSN extraction
# =============================================================================

def extract_issn_by_quartile(
    journals: List[dict],
    quartiles: Optional[Set[str]] = None,
) -> List[str]:
    """Filter ISSN electronic dari list jurnal SCImago.

    Args:
        journals: List dict jurnal, masing-masing punya key issn_electronic & quartile.
        quartiles: Set quartile yang diinginkan (mis. {"Q1", "Q2"}).
            None artinya ambil semua quartile.

    Returns:
        List ISSN electronic unik yang non-kosong, urutan sesuai input.
    """
    issn_list: List[str] = []
    seen: Set[str] = set()
    for item in journals:
        issn = item.get("issn_electronic")
        if not (issn and isinstance(issn, str) and issn.strip()):
            continue

        if quartiles is not None:
            quartile = item.get("quartile")
            if not quartile:
                continue
            q_clean = quartile.strip().upper()
            if q_clean not in quartiles:
                continue

        issn_clean = issn.strip()
        if issn_clean not in seen:
            seen.add(issn_clean)
            issn_list.append(issn_clean)
    return issn_list


def parse_quartile_input(pilihan: str) -> Optional[Set[str]]:
    """Parse input quartile dari user ("semua" | "Q1,Q2" | "q1, q3").

    Args:
        pilihan: String input user.

    Returns:
        Set quartile uppercase, atau None jika user pilih "semua".

    Raises:
        ValueError: jika input tidak valid.
    """
    pilihan = pilihan.strip().lower()
    if pilihan == "semua":
        return None
    parts = [p.strip().upper() for p in pilihan.split(",")]
    valid = all(p in {"Q1", "Q2", "Q3", "Q4"} for p in parts)
    if not valid:
        raise ValueError(
            "Pilihan tidak valid. Gunakan: 'semua', atau kombinasi Q1,Q2,Q3,Q4 (pisah koma)"
        )
    return set(parts)


# =============================================================================
# Entry point
# =============================================================================

def run(
    quartile: str = "semua",
    interactive: bool = False,
    subject: Optional[str] = None,
) -> int:
    """Entry point step 01.

    Args:
        quartile: String quartile ("semua" | "Q1,Q2" | dst).
        interactive: Jika True, prompt user lewat input() (kompatibilitas lama).
        subject: Jika diisi, ambil ISSN dari subject area pilihan di scimago_split.
            Format: "list" | "all" | "1,3,5" | "Computer" | "Computer Science,Math".

    Returns:
        Jumlah ISSN yang berhasil diekstrak.
    """
    log = setup_logging()
    cfg = get_config()
    output_path = cfg["paths"]["step_01_issn_list"]
    split_dir = cfg["paths"]["scimago_split_dir"]

    print_header("Step 01: Ekstrak ISSN Electronic dari SCImago")

    # Mode 1: --subject list -> tampilkan daftar subject area, lalu exit
    if subject and subject.strip().lower() == "list":
        list_subject_areas(split_dir)
        return 0

    # Mode 2: --subject <pilihan> -> load dari scimago_split
    if subject:
        try:
            subject_files = resolve_subject_areas(subject, split_dir)
        except ValueError as e:
            log.error(str(e))
            return 0

        log.info(f"Mode subject area: {len(subject_files)} file dipilih")
        for f in subject_files:
            log.info(f"  - {os.path.basename(f)}")
        print()

        # Load & gabung jurnal dari file-file subject area
        journals = load_journals_from_subject_files(subject_files)
        source_label = f"scimago_split ({len(subject_files)} subject area)"
        log.info(f"Total jurnal unik (gabungan): {len(journals)}")
    else:
        # Mode default: pakai SCImago full (prioritas: scimago_clean -> scimago_json)
        clean_path = cfg.get("paths", {}).get("scimago_clean")
        json_path = cfg.get("paths", {}).get("scimago_json")
        
        input_path = None
        if clean_path and os.path.isfile(clean_path):
            input_path = clean_path
        elif json_path and os.path.isfile(json_path):
            input_path = json_path
        else:
            input_path = json_path or clean_path

        log.info(f"Mode: SCImago full")
        log.info(f"Input  : {input_path}")
        try:
            journals = load_json(input_path)
        except FileNotFoundError:
            log.error(f"File SCImago tidak ditemukan: {input_path}\nJalankan `find-refs csv-to-json` terlebih dahulu.")
            return 0
        except Exception as e:
            log.error(f"Gagal membaca {input_path}: {e}")
            return 0
        source_label = "SCImago full"

    log.info(f"Output : {output_path}")

    if not isinstance(journals, list):
        log.error("Isi SCImago JSON harus berupa list.")
        return 0

    # Jika mode interaktif, ambil input quartile dari user
    if interactive:
        print("\nPilihan quartile:")
        print("  - semua")
        print("  - Q1, Q2, Q3, Q4 (bisa lebih dari satu, pisahkan koma)")
        print("  Contoh: Q1,Q2  atau  Q1, Q3, Q4")
        quartile = input("Masukkan pilihan quartile: ").strip()

    try:
        quartiles = parse_quartile_input(quartile)
    except ValueError as e:
        log.error(str(e))
        return 0

    issn_list = extract_issn_by_quartile(journals, quartiles)

    # Tulis ke file (satu ISSN per baris)
    save_text("\n".join(issn_list) + "\n", output_path)

    q_label = "semua quartile" if quartiles is None else ",".join(sorted(quartiles))
    print(f"\nSumber data    : {source_label}")
    print(f"Quartile filter: {q_label}")
    print(f"Total jurnal diperiksa: {len(journals)}")
    print(f"Total ISSN electronic ditemukan: {len(issn_list)}")
    print(f"\nFile output: {output_path}")

    # Tampilkan preview 5 ISSN pertama
    if issn_list:
        print("\nPreview 5 ISSN pertama:")
        for issn in issn_list[:5]:
            print(f"  - {issn}")

    print_done(f"Step 01 selesai — {len(issn_list)} ISSN tersimpan")
    return len(issn_list)


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register subcommand untuk step 01."""
    parser = subparsers.add_parser(
        "get-issn",
        help=DESCRIPTION,
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Contoh pemakaian:\n"
            "  find-refs get-issn                                  # SCImago full, semua quartile\n"
            "  find-refs get-issn -q Q1,Q2                         # SCImago full, Q1+Q2\n"
            "  find-refs get-issn --subject list                   # lihat daftar subject area\n"
            '  find-refs get-issn --subject 1,3,5                 # pilih subject area nomor 1, 3, 5\n'
            '  find-refs get-issn --subject Computer              # semua area yg namanya ada "Computer"\n'
            '  find-refs get-issn --subject all                   # gabung semua subject area\n'
            '  find-refs get-issn --subject "Computer Science,Mathematics" -q Q1   # multi-name + Q1\n'
        ),
    )
    parser.add_argument(
        "-q", "--quartile",
        default="semua",
        help='Quartile filter: "semua" (default) atau kombinasi seperti "Q1,Q2"',
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Mode interaktif: prompt input quartile dari user",
    )
    parser.add_argument(
        "-s", "--subject",
        default=None,
        help=(
            "Pilih subject area dari scimago_split. Format: "
            "'list' (lihat daftar), 'all' (semua), '1,3,5' (nomor), "
            "'Computer' (nama/keyword), atau 'Name1,Name2' (multi)."
        ),
    )
    parser.set_defaults(func=lambda args: run(
        quartile=args.quartile,
        interactive=args.interactive,
        subject=args.subject,
    ))
