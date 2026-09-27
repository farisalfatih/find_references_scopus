"""Step 07a: Hapus artikel dari jurnal yang tidak terindeks Scopus.

Input  : data/07_with_journal_info.json  (output step 07)
Output : data/07a_scopus_only.json        (artikel terindeks Scopus saja)

Perilaku:
   - Memeriksa setiap artikel apakah memiliki quartile Scopus (Q1, Q2, Q3, Q4, atau -).
   - Jika quartile belum ada, memeriksa kecocokan issn_electronic dengan database SCImago
     (data/scimagojr_2025_ok.json atau scimagojr_2025.json).
   - Menghapus artikel yang tidak terdaftar di Scopus / SCImago.
   - Opsional: filter quartile tertentu (misal: -q Q1,Q2).
   - Menampilkan statistik per kategori: total awal, dihapus (non-Scopus), tersisa (Scopus).
   - Mendukung penyimpanan langsung menimpa input (--in-place / --overwrite-input).
"""

from __future__ import annotations

import argparse
import os
from collections import Counter
from typing import Any, Dict, List, Set, Tuple

from ..config import get_config
from ..utils import load_json, print_done, print_header, save_json, setup_logging


DESCRIPTION = "Hapus artikel dari jurnal yang tidak terindeks Scopus"

# Tag untuk find-refs list (M13: auto-derived dari module attribute)
MANUAL_OR_AUTO = "AUTO"

VALID_QUARTILES = {"Q1", "Q2", "Q3", "Q4", "-"}


def build_journal_index(journals_data: list[dict]) -> Dict[str, Dict[str, Any]]:
    """Bangun index ISSN electronic -> info jurnal dari data SCImago.

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


def is_scopus_indexed(
    paper: dict,
    allowed_quartiles: Set[str] | None = None,
    journal_index: Dict[str, Dict[str, Any]] | None = None,
    include_unranked: bool = True,
) -> bool:
    """Cek apakah sebuah artikel terindeks di Scopus / SCImago.

    Args:
        paper: Dict artikel.
        allowed_quartiles: Set quartile yang diizinkan (misal {"Q1", "Q2"}).
            Jika None, semua artikel terindeks Scopus diizinkan.
        journal_index: Index SCImago opsional untuk lookup jika quartile belum ada.
        include_unranked: Apakah menyertakan jurnal Scopus dengan quartile '-'.

    Returns:
        True jika artikel terindeks Scopus (dan memenuhi allowed_quartiles jika ada).
    """
    quartile = paper.get("quartile")

    # Jika belum ada quartile tapi journal_index tersedia, coba lookup via ISSN
    if not quartile and journal_index:
        issn = paper.get("issn_electronic")
        if issn and issn in journal_index:
            info = journal_index[issn]
            quartile = info.get("quartile")
            paper["quartile"] = quartile
            if info.get("open_access"):
                paper["open_access"] = info["open_access"]

    if not quartile:
        return False

    q_str = str(quartile).strip().upper()

    if q_str == "-":
        if not include_unranked:
            return False
        if allowed_quartiles is not None:
            return "-" in allowed_quartiles
        return True

    if allowed_quartiles is not None:
        return q_str in allowed_quartiles

    return q_str in {"Q1", "Q2", "Q3", "Q4"} or len(q_str) > 0


def filter_articles(
    articles_data: Any,
    allowed_quartiles: Set[str] | None = None,
    journal_index: Dict[str, Dict[str, Any]] | None = None,
    include_unranked: bool = True,
) -> Tuple[Any, Dict[str, int], Counter]:
    """Filter artikel dalam struktur data JSON.

    Args:
        articles_data: Data artikel (Dict[kategori, List[paper]] atau List[paper]).
        allowed_quartiles: Quartile yang diizinkan (None = semua Scopus).
        journal_index: Index SCImago opsional untuk fallback lookup.
        include_unranked: Apakah jurnal dengan quartile '-' disertakan.

    Returns:
        Tuple (filtered_data, stats_dict, quartile_counter).
    """
    stats = {
        "total_initial": 0,
        "total_kept": 0,
        "total_removed": 0,
    }
    quartile_counts: Counter = Counter()

    if isinstance(articles_data, dict):
        filtered_dict: Dict[str, List[dict]] = {}
        for category, papers in articles_data.items():
            if not isinstance(papers, list):
                filtered_dict[category] = papers
                continue

            init_len = len(papers)
            stats["total_initial"] += init_len
            kept_papers: List[dict] = []

            for paper in papers:
                if isinstance(paper, dict) and is_scopus_indexed(
                    paper, allowed_quartiles, journal_index, include_unranked
                ):
                    kept_papers.append(paper)
                    q = paper.get("quartile", "Unknown")
                    quartile_counts[q] += 1

            removed_len = init_len - len(kept_papers)
            stats["total_removed"] += removed_len
            stats["total_kept"] += len(kept_papers)
            filtered_dict[category] = kept_papers

            print(f"  Kategori '{category}': {init_len} -> {len(kept_papers)} (dihapus {removed_len} non-Scopus)")

        return filtered_dict, stats, quartile_counts

    elif isinstance(articles_data, list):
        stats["total_initial"] = len(articles_data)
        kept_list: List[dict] = []
        for paper in articles_data:
            if isinstance(paper, dict) and is_scopus_indexed(
                paper, allowed_quartiles, journal_index, include_unranked
            ):
                kept_list.append(paper)
                q = paper.get("quartile", "Unknown")
                quartile_counts[q] += 1

        stats["total_kept"] = len(kept_list)
        stats["total_removed"] = len(articles_data) - len(kept_list)
        return kept_list, stats, quartile_counts

    return articles_data, stats, quartile_counts


def run(
    input_file: str | None = None,
    output_file: str | None = None,
    journals_file: str | None = None,
    quartiles: str | None = None,
    in_place: bool = False,
    include_unranked: bool = True,
) -> int:
    """Entry point step 07a.

    Args:
        input_file: Path JSON artikel input (default: step_07_with_journal_info).
        output_file: Path JSON output (default: step_07a_scopus_only).
        journals_file: Path JSON SCImago (opsional).
        quartiles: Filter quartile yang diizinkan, misal "Q1,Q2" (None = semua Scopus).
        in_place: Jika True, timpa langsung file input.
        include_unranked: Apakah menyertakan jurnal tanpa quartile ('-').

    Returns:
        Jumlah total artikel yang terindeks Scopus.
    """
    log = setup_logging()
    cfg = get_config()

    # Tentukan input path
    if input_file:
        input_path = input_file
    else:
        step_07_path = cfg.get("paths", {}).get("step_07_with_journal_info")
        step_05_path = cfg.get("paths", {}).get("step_05_cleaned")
        if step_07_path and os.path.isfile(step_07_path):
            input_path = step_07_path
        elif step_05_path and os.path.isfile(step_05_path):
            input_path = step_05_path
        else:
            input_path = step_07_path or "data/07_with_journal_info.json"

    # Tentukan output path
    if in_place:
        output_path = input_path
    elif output_file:
        output_path = output_file
    else:
        output_path = cfg.get("paths", {}).get(
            "step_07a_scopus_only", "data/07a_scopus_only.json"
        )

    # Parsing allowed quartiles jika diberikan
    allowed_q: Set[str] | None = None
    if quartiles:
        parts = [q.strip().upper() for q in quartiles.split(",") if q.strip()]
        if parts and "ALL" not in parts:
            allowed_q = set(parts)

    print_header("Step 07a: Filter & Hapus Jurnal Non-Scopus")
    log.info(f"Input   : {input_path}")
    log.info(f"Output  : {output_path}")
    if allowed_q:
        log.info(f"Filter Quartile: {', '.join(sorted(allowed_q))}")
    else:
        log.info("Filter Quartile: Semua Scopus (Q1, Q2, Q3, Q4, -)")

    try:
        data = load_json(input_path)
    except FileNotFoundError:
        log.error(f"File artikel tidak ditemukan: {input_path}")
        return 0

    # Siapkan index SCImago sebagai fallback jika diperlukan
    journal_index = None
    scimago_candidates = []
    if journals_file:
        scimago_candidates.append(journals_file)
    clean_path = cfg.get("paths", {}).get("scimago_clean")
    json_path = cfg.get("paths", {}).get("scimago_json")
    if clean_path:
        scimago_candidates.append(clean_path)
    if json_path:
        scimago_candidates.append(json_path)

    for cand in scimago_candidates:
        if os.path.isfile(cand):
            try:
                journals_data = load_json(cand)
                journal_index = build_journal_index(journals_data)
                log.info(f"Loaded SCImago index ({len(journal_index)} ISSN) dari: {cand}")
                break
            except Exception as e:
                log.warning(f"Gagal memuat index SCImago dari {cand}: {e}")

    filtered_data, stats, quartile_counts = filter_articles(
        data,
        allowed_quartiles=allowed_q,
        journal_index=journal_index,
        include_unranked=include_unranked,
    )

    save_json(filtered_data, output_path)

    print("\n--- Ringkasan Filter Scopus ---")
    print(f"Total artikel awal    : {stats['total_initial']}")
    print(f"Artikel non-Scopus dihapus : {stats['total_removed']}")
    print(f"Artikel Scopus tersisa     : {stats['total_kept']}")

    if quartile_counts:
        print("\nDistribusi Quartile Artikel Tersisa:")
        for q in ["Q1", "Q2", "Q3", "Q4", "-"]:
            if q in quartile_counts:
                print(f"  {q:<4}: {quartile_counts[q]} artikel")
        for q, count in quartile_counts.items():
            if q not in ["Q1", "Q2", "Q3", "Q4", "-"]:
                print(f"  {q:<4}: {count} artikel")

    print_done(
        f"Step 07a selesai — {stats['total_kept']} artikel terindeks Scopus disimpan ke {output_path}"
    )
    return stats["total_kept"]


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register subcommand untuk step 07a."""
    parser = subparsers.add_parser(
        "filter-scopus",
        aliases=["remove-non-scopus"],
        help=DESCRIPTION,
        description=DESCRIPTION,
    )
    parser.add_argument(
        "-i", "--input",
        default=None,
        help="File JSON artikel input (default: data/07_with_journal_info.json)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="File JSON output (default: data/07a_scopus_only.json)",
    )
    parser.add_argument(
        "-j", "--journals",
        default=None,
        help="File JSON SCImago (opsional untuk verifikasi tambahan)",
    )
    parser.add_argument(
        "-q", "--quartile",
        default=None,
        help="Filter hanya quartile tertentu, pisahkan koma (contoh: Q1,Q2 atau Q1). Default: semua Scopus.",
    )
    parser.add_argument(
        "--in-place", "--overwrite-input",
        dest="in_place",
        action="store_true",
        help="Simpan hasil langsung menimpa file input.",
    )
    parser.add_argument(
        "--no-unranked",
        dest="include_unranked",
        action="store_false",
        default=True,
        help="Jangan sertakan jurnal Scopus yang quartile-nya '-' (unranked).",
    )
    parser.set_defaults(
        func=lambda args: run(
            input_file=args.input,
            output_file=args.output,
            journals_file=args.journals,
            quartiles=args.quartile,
            in_place=args.in_place,
            include_unranked=args.include_unranked,
        )
    )
