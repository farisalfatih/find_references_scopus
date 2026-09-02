"""Step 07: Tambah informasi quartile & open_access dari SCImago.

Input  : data/05_cleaned.json        (output step 05)
         data/scimagojr_2025.json    (data jurnal SCImago)
Output : data/07_with_journal_info.json

Perilaku:
   - Bangun index ISSN -> {quartile, open_access} dari SCImago JSON
   - Rekursif telusuri struktur JSON artikel (dict of list of dict)
   - Untuk setiap artikel yang punya issn_electronic, tambahkan field
     `quartile` dan `open_access` (timpa nilai lama jika ada)

Setara dengan script lama: marge_article_journal.py
"""

from __future__ import annotations

import argparse
import os
from typing import Any, Dict

from ..config import get_config
from ..utils import load_json, print_done, print_header, save_json, setup_logging


DESCRIPTION = "Tambah info quartile & open_access dari SCImago ke artikel"

# Tag untuk find-refs list (M13: auto-derived dari module attribute)
MANUAL_OR_AUTO = "AUTO"


def build_journal_index(journals_data: list[dict]) -> Dict[str, Dict[str, Any]]:
    """Bangun index ISSN electronic -> info jurnal.

    Args:
        journals_data: List jurnal dari SCImago JSON.

    Returns:
        Mapping issn_electronic -> {"quartile": ..., "open_access": ...}.
    """
    index: Dict[str, Dict[str, Any]] = {}
    for journal in journals_data:
        issn = journal.get("issn_electronic")
        if not issn:
            continue
        index[issn] = {
            "quartile": journal.get("quartile"),
            "open_access": journal.get("open_access"),
        }
    return index


def merge_articles(articles_data: Any, journal_index: Dict[str, Dict[str, Any]]) -> Any:
    """Rekursif tambahkan quartile & open_access ke setiap artikel.

    Mendeteksi "artikel" sebagai dict yang punya key 'issn_electronic'
    DAN ('doi' atau 'title'). Struktur lain (dict of list of dict) akan
    ditelusuri rekursif.

    H9: Jangan overwrite quartile/open_access dengan None jika ISSN tidak
    match di SCImago. Artinya:
      - Jika ISSN match di SCImago -> SET quartile & open_access dari SCImago
      - Jika ISSN tidak match -> JANGAN sentuh field yang sudah ada
        (pertahankan info OpenAlex yang mungkin lebih granular, mis. "Partial")

    M8: Fungsi ini memutasi input secara in-place. Untuk menghindari surprise,
    kita tidak membuat shallow copy (data bisa besar). Dokumentasikan eksplisit
    bahwa input akan dimutasi.

    Args:
        articles_data: Struktur data artikel (bisa dict, list, atau artikel tunggal).
            CATATAN: struktur ini akan dimutasi in-place.
        journal_index: Index dari build_journal_index().

    Returns:
        Struktur data yang sama (reference ke input yang sudah dimutasi).
    """
    if isinstance(articles_data, dict):
        # Deteksi: ini artikel atau container?
        if "issn_electronic" in articles_data and ("doi" in articles_data or "title" in articles_data):
            issn = articles_data.get("issn_electronic")
            # Hanya set quartile/open_access jika ISSN non-kosong DAN match di SCImago
            # (H9: jangan overwrite dengan None)
            if issn:  # None atau "" -> skip
                info = journal_index.get(issn)
                if info is not None:
                    articles_data["quartile"] = info["quartile"]
                    articles_data["open_access"] = info["open_access"]
            # Jika ISSN kosong atau tidak match di SCImago:
            # pertahankan field yang sudah ada (mis. "open_access" dari OpenAlex)
        else:
            for key, value in articles_data.items():
                articles_data[key] = merge_articles(value, journal_index)
    elif isinstance(articles_data, list):
        for i, item in enumerate(articles_data):
            articles_data[i] = merge_articles(item, journal_index)
    return articles_data


def run(articles_file: str | None = None, journals_file: str | None = None,
        output_file: str | None = None) -> int:
    """Entry point step 07.

    Args:
        articles_file: Path JSON artikel. None = pakai config (step_05_cleaned).
        journals_file: Path JSON SCImago. None = pakai config (scimago_json).
        output_file: Path output. None = pakai config (step_07_with_journal_info).

    Returns:
        1 jika sukses, 0 jika gagal.
    """
    log = setup_logging()
    cfg = get_config()
    articles_path = articles_file or cfg["paths"]["step_05_cleaned"]
    
    if journals_file:
        journals_path = journals_file
    else:
        clean_path = cfg.get("paths", {}).get("scimago_clean")
        json_path = cfg.get("paths", {}).get("scimago_json")
        if clean_path and os.path.isfile(clean_path):
            journals_path = clean_path
        elif json_path and os.path.isfile(json_path):
            journals_path = json_path
        else:
            journals_path = json_path or clean_path

    output_path = output_file or cfg["paths"]["step_07_with_journal_info"]

    print_header("Step 07: Merge Info Quartile & Open Access")
    log.info(f"Articles : {articles_path}")
    log.info(f"Journals : {journals_path}")
    log.info(f"Output   : {output_path}")

    try:
        articles = load_json(articles_path)
    except FileNotFoundError:
        log.error(f"File artikel tidak ditemukan: {articles_path}")
        return 0

    try:
        journals = load_json(journals_path)
    except FileNotFoundError:
        log.error(f"File SCImago tidak ditemukan: {journals_path}\nJalankan `find-refs csv-to-json` terlebih dahulu.")
        return 0

    journal_index = build_journal_index(journals)
    log.info(f"Index jurnal: {len(journal_index)} ISSN terindeks")

    merged = merge_articles(articles, journal_index)

    save_json(merged, output_path)

    # Statistik ringkas
    total = 0
    matched = 0
    if isinstance(merged, dict):
        for arts in merged.values():
            if isinstance(arts, list):
                for art in arts:
                    if isinstance(art, dict) and "doi" in art:
                        total += 1
                        if art.get("quartile"):
                            matched += 1

    print(f"\nTotal artikel diproses: {total}")
    print(f"Artikel dengan info jurnal ditemukan: {matched}")
    print(f"Artikel tanpa info jurnal: {total - matched}")

    print_done(f"Step 07 selesai — info jurnal ditambahkan ke {total} artikel")
    return 1


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register subcommand untuk step 07."""
    parser = subparsers.add_parser(
        "merge-journal",
        help=DESCRIPTION,
        description=DESCRIPTION,
    )
    parser.add_argument(
        "-a", "--articles",
        default=None,
        help="File JSON artikel (default: step 05)",
    )
    parser.add_argument(
        "-j", "--journals",
        default=None,
        help="File JSON SCImago (default: data/scimagojr_2025.json)",
    )
    parser.add_argument("-o", "--output", default=None, help="File JSON output (default: step 07)")
    parser.set_defaults(func=lambda args: run(
        articles_file=args.articles,
        journals_file=args.journals,
        output_file=args.output,
    ))
