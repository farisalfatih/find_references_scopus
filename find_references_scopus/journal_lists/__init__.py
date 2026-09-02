"""Package journal_lists berisi utilitas untuk preprocessing data SCImago.

Modul-modul di sini TIDAK termasuk pipeline utama (step 01-11), melainkan
utilitas pendukung untuk mempersiapkan data SCImago sebelum pipeline berjalan:

    - csv_to_json         : konversi SCImago CSV -> JSON terstruktur
    - check_issn          : inspeksi kelengkapan ISSN print/electronic
    - delete_no_issn      : hapus jurnal tanpa ISSN electronic
    - split_by_subject_area: pecah JSON per subject area

CLI:
    find-refs csv-to-json      <csv> <json>
    find-refs check-issn       [json]
    find-refs delete-no-issn   [input_json] [output_json]
    find-refs split-subject    [input_json] [output_dir]
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

# Registry subcommand journal-lists
JOURNAL_LISTS_STEPS: List[Tuple[str, Any]] = []

# Import dilakukan di __init__ untuk registrasi
from . import csv_to_json, check_issn, delete_no_issn, split_by_subject_area

JOURNAL_LISTS_STEPS = [
    ("csv-to-json", csv_to_json),
    ("check-issn", check_issn),
    ("delete-no-issn", delete_no_issn),
    ("split-subject", split_by_subject_area),
]


def get_journal_lists_step_map() -> Dict[str, Any]:
    """Mapping command_name -> module untuk journal-lists."""
    return {cmd: mod for cmd, mod in JOURNAL_LISTS_STEPS}
