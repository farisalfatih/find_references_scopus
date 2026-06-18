"""Package pipeline berisi 11 step yang dijalankan secara berurutan.

Setiap step adalah modul Python dengan struktur konsisten:
    - DESCRIPTION: str       -> deskripsi singkat untuk help CLI
    - add_parser(subparsers) -> register subcommand argparse
    - run(**kwargs) -> int   -> entry point yang dijalankan CLI

Urutan eksekusi standar:
    01 get-issn              -> ekstrak ISSN dari SCImago
    02 fetch                 -> ambil artikel dari OpenAlex
    03 filter                -> filter berdasar keyword di judul+abstrak
    04 deduplicate           -> hapus duplikat antar group berdasar hierarki query
    05 remove-excluded       -> hapus DOI yang ada di excluded_dois.txt
    06 distribution          -> tampilkan distribusi artikel per kategori
    07 merge-journal         -> tambah info quartile & open_access dari SCImago
    08 extract-claims        -> ekstrak kalimat berisi DOI dari Markdown
    09 extract-references    -> format artikel jadi Markdown ringkas
    10 select-articles       -> ambil subset artikel berdasar daftar DOI
    11 convert-bib           -> konversi JSON ke BibTeX untuk LaTeX
"""

from __future__ import annotations

from typing import Callable, Dict, List, Tuple

# Import semua step untuk registrasi otomatis di registry
from . import (
    step_01_get_issn,
    step_02_openalex_fetch,
    step_03_filter_keywords,
    step_04_deduplicate,
    step_05_remove_excluded,
    step_06_check_distribution,
    step_07_merge_journal,
    step_08_extract_claims,
    step_09_extract_references,
    step_10_select_articles,
    step_11_convert_bib,
)


# Registry berisi (command_name, module) berurutan
STEPS: List[Tuple[str, object]] = [
    ("get-issn", step_01_get_issn),
    ("fetch", step_02_openalex_fetch),
    ("filter", step_03_filter_keywords),
    ("deduplicate", step_04_deduplicate),
    ("remove-excluded", step_05_remove_excluded),
    ("distribution", step_06_check_distribution),
    ("merge-journal", step_07_merge_journal),
    ("extract-claims", step_08_extract_claims),
    ("extract-references", step_09_extract_references),
    ("select-articles", step_10_select_articles),
    ("convert-bib", step_11_convert_bib),
]


def get_step_map() -> Dict[str, object]:
    """Mapping command_name -> module."""
    return {cmd: mod for cmd, mod in STEPS}
