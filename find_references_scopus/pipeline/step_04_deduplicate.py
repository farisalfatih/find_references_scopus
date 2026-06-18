"""Step 04: Deduplikasi artikel antar search group.

Input  : data/03_filtered.json     (output step 03)
Output : data/04_deduplicated.json

Perilaku:
   - Artikel yang sama (sama DOI) muncul di beberapa group akan dipindahkan
     ke group yang paling "spesifik" (subset) berdasarkan hierarki query
   - Hierarki ditentukan dari token query: group A adalah subset dari group B
     jika semua token query A ada di token query B
     -> Group yang lebih spesifik (token lebih sedikit, lebih niche) akan
        "menang" dan menjadi target pemindahan DOI
   - Jika tidak ada hubungan subset, DOI akan diletakkan di group gabungan
     "Group1 + Group2" (nama group di-join dengan " + ")

Setara dengan script lama: clear_duplicate.py
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from typing import Dict, List, Set

from ..config import get_config
from ..utils import load_json, print_done, print_header, save_json, setup_logging


DESCRIPTION = "Deduplikasi artikel antar group berdasarkan hierarki query"

# Tag untuk find-refs list (M13: auto-derived dari module attribute)
MANUAL_OR_AUTO = "AUTO"


# =============================================================================
# Token extraction & hierarki
# =============================================================================

def extract_tokens(query: str) -> Set[str]:
    """Ekstrak token dari query boolean untuk perbandingan subset.

    Token = semua kata/phrase yang muncul di query, di-lowercase, kecuali
    operator AND/OR/NOT. Quoted phrase ("...") dihitung sebagai satu token.

    Args:
        query: Query boolean, mis. '"XGBoost" AND (MACD OR RSI)'.

    Returns:
        Set token lowercase. Contoh: {"xgboost", "macd", "rsi"}.
    """
    tokens: List[str] = []
    # Ambil quoted phrases dulu
    quoted = re.findall(r'"([^"]+)"', query)
    tokens.extend(quoted)
    # Hapus quoted phrases dari query, lalu ambil kata sisanya
    temp = re.sub(r'"[^"]+"', "", query)
    words = re.findall(r"\b[a-zA-Z0-9]+\b", temp)
    stop = {"and", "or", "not"}
    tokens.extend(w.lower() for w in words if w.lower() not in stop)
    # Normalize semua ke lowercase sekali di akhir (L2: cosmetic, sebelumnya double lower)
    return set(t.lower() for t in tokens)


def is_subset(query1: str, query2: str) -> bool:
    """Cek apakah token query1 adalah subset dari token query2.

    Args:
        query1: Query yang mungkin lebih spesifik (lebih sedikit token).
        query2: Query yang mungkin lebih umum (lebih banyak token).

    Returns:
        True jika semua token query1 ada di query2.
    """
    return extract_tokens(query1).issubset(extract_tokens(query2))


def build_hierarchy(groups_config: Dict[str, dict]) -> Dict[str, List[str]]:
    """Bangun mapping group -> list superset-nya.

    Definisi:
      - Group A adalah SUBSET dari group B jika semua token A ada di B.
      - Artinya A lebih SPESIFIK (lebih sedikit token, lebih niche).
      - Sebaliknya B adalah SUPERSET dari A (lebih umum, lebih banyak token).

    Args:
        groups_config: Mapping nama_group -> {"query": "..."}.

    Returns:
        Mapping nama_group -> list group yang merupakan superset-nya
        (yaitu group yang query-nya lebih umum/lebih banyak token).
    """
    names = list(groups_config.keys())
    subset_relations: Dict[str, List[str]] = {}
    for i, name1 in enumerate(names):
        q1 = groups_config[name1]["query"]
        subset_relations[name1] = []
        for j, name2 in enumerate(names):
            if i == j:
                continue
            q2 = groups_config[name2]["query"]
            # Jika token name1 adalah subset dari name2 -> name2 adalah superset dari name1
            if is_subset(q1, q2):
                subset_relations[name1].append(name2)
    return subset_relations


# =============================================================================
# Deduplikasi inti
# =============================================================================

def deduplicate_based_on_hierarchy(
    data: Dict[str, List[dict]],
    groups_config: Dict[str, dict],
) -> Dict[str, List[dict]]:
    """Pindahkan DOI duplikat ke group yang paling spesifik.

    Algoritma:
      1. Bangun peta DOI -> list group tempat DOI itu muncul
      2. Untuk DOI yang muncul di >1 group:
         - Cari group yang merupakan superset dari semua group lain
           (group yang query-nya paling umum / token paling banyak)
           -> Artinya: group yang "mencakup" semua group lain
         - Pilih group dengan token paling sedikit (paling spesifik)
           sebagai target pemindahan
         - Jika tidak ditemukan superset tunggal -> gabungkan nama group
           dengan " + " (mis. "GroupA + GroupB")

    Catatan M2: Group hasil gabungan "A + B" TIDAK ada di search_groups config.
    Ini bisa menyebabkan step 03 memberi warning "group tidak dikenal" kalau
    pipeline dijalankan ulang dari step 02 dengan group combined ini. Untuk
    menghindari ini, jalankan step 02-04 secara berurutan tanpa modifikasi
    search_groups di tengah.

    Args:
        data: Mapping group -> list artikel (dengan duplikasi antar group).
        groups_config: Mapping nama_group -> {"query": "..."}.

    Returns:
        Mapping group -> list artikel TANPA duplikasi antar group.
    """
    subset_map = build_hierarchy(groups_config)
    print("Relasi subset (group -> superset-nya, yaitu group yang lebih umum):")
    for g, supers in subset_map.items():
        print(f"  {g} -> {supers if supers else '(tidak ada)'}")

    # Peta DOI -> list group tempat DOI muncul, dan DOI -> artikel
    doi_to_groups: Dict[str, List[str]] = defaultdict(list)
    doi_to_article: Dict[str, dict] = {}
    for group, articles in data.items():
        for art in articles:
            doi = art.get("doi")
            if not doi:
                continue
            if doi not in doi_to_article:
                doi_to_article[doi] = art
            if group not in doi_to_groups[doi]:
                doi_to_groups[doi].append(group)

    # Tentukan group final untuk setiap DOI
    final_group_for_doi: Dict[str, str] = {}
    for doi, groups in doi_to_groups.items():
        if len(groups) == 1:
            final_group_for_doi[doi] = groups[0]
            continue

        # Cari group yang merupakan superset dari semua group lain
        superset_candidates: List[str] = []
        for g in groups:
            is_superset_of_all = True
            for other in groups:
                if other == g:
                    continue
                if g not in subset_map.get(other, []):
                    is_superset_of_all = False
                    break
            if is_superset_of_all:
                superset_candidates.append(g)

        if superset_candidates:
            # Pilih group dengan token paling sedikit (paling umum)
            best = min(
                superset_candidates,
                key=lambda x: len(extract_tokens(groups_config[x]["query"])),
            )
            final_group_for_doi[doi] = best
        else:
            # Tidak ada hubungan subset -> gabungkan nama group
            sorted_groups = sorted(groups)
            combined_name = " + ".join(sorted_groups)
            final_group_for_doi[doi] = combined_name

    # Bangun data baru berdasarkan group final
    new_data: Dict[str, List[dict]] = defaultdict(list)
    for doi, target_group in final_group_for_doi.items():
        new_data[target_group].append(doi_to_article[doi])

    return dict(new_data)


# =============================================================================
# Entry point
# =============================================================================

def run(input_file: str | None = None, output_file: str | None = None) -> int:
    """Entry point step 04.

    Args:
        input_file: Path input JSON. None = pakai config (step_03_filtered).
        output_file: Path output JSON. None = pakai config (step_04_deduplicated).

    Returns:
        Jumlah total artikel setelah deduplikasi.
    """
    log = setup_logging()
    cfg = get_config()
    input_path = input_file or cfg["paths"]["step_03_filtered"]
    output_path = output_file or cfg["paths"]["step_04_deduplicated"]
    search_groups = cfg.get("search_groups", {})

    print_header("Step 04: Deduplikasi Antar Group")
    log.info(f"Input  : {input_path}")
    log.info(f"Output : {output_path}")

    try:
        data = load_json(input_path)
    except FileNotFoundError:
        log.error(f"File input tidak ditemukan: {input_path}")
        return 0

    print("\nData awal:")
    for g, arts in data.items():
        print(f"  {g}: {len(arts)} artikel")

    cleaned_data = deduplicate_based_on_hierarchy(data, search_groups)

    print("\nSetelah deduplikasi berbasis hierarki:")
    for g, arts in cleaned_data.items():
        print(f"  {g}: {len(arts)} artikel")

    save_json(cleaned_data, output_path)

    total = sum(len(arts) for arts in cleaned_data.values())
    print(f"\nTotal artikel unik: {total}")

    print_done(f"Step 04 selesai — {total} artikel unik")
    return total


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register subcommand untuk step 04."""
    parser = subparsers.add_parser(
        "deduplicate",
        help=DESCRIPTION,
        description=DESCRIPTION,
    )
    parser.add_argument("-i", "--input", default=None, help="File JSON input (default: step 03)")
    parser.add_argument("-o", "--output", default=None, help="File JSON output (default: step 04)")
    parser.set_defaults(func=lambda args: run(input_file=args.input, output_file=args.output))
