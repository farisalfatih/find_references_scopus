"""Step 11: Konversi JSON referensi ke file BibTeX (.bib).

Input  : data/07_with_journal_info.json  (output step 07)
         ATAU data/10_selected.json      (output step 10, jika --input di-set)
Output : data/11_references.bib

Perilaku:
   - Kumpulkan semua artikel dari struktur {kategori: [artikel, ...]}
   - Generate citation key: <lastname><year>_<index> (mis. "smith2023_1")
   - Escape karakter khusus BibTeX: & % $ # _ ^ ~ { } dan backslash
   - Tulis entry @article{...} dengan field standar:
     author, title, journal, year, month, volume, number, pages, doi, publisher

PERBAIKAN BUG: Versi lama (confert_bib.py) menulis "## article{...}" dengan
prefix "## " yang merusak parser BibTeX. Versi ini menulis "@article{...}".

Setara dengan script lama: confert_bib.py
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from typing import Any, List

from ..config import get_config
from ..utils import format_authors_bib, load_json, print_done, print_header, save_text, setup_logging


DESCRIPTION = "Konversi JSON referensi ke file BibTeX (.bib)"

# Tag untuk find-refs list (M13: auto-derived dari module attribute)
MANUAL_OR_AUTO = "AUTO"


# =============================================================================
# Escape karakter khusus BibTeX
# =============================================================================

def escape_bibtex(s: str) -> str:
    """Escape karakter khusus LaTeX/BibTeX di string.

    Karakter yang di-escape: backslash, { } & % $ # _ ^ ~
    Backslash di-handle terakhir via placeholder agar tidak double-escape.

    Args:
        s: String input.

    Returns:
        String yang sudah di-escape, aman untuk ditulis di field BibTeX.
    """
    if not isinstance(s, str):
        return str(s)
    # Placeholder untuk backslash agar brace escape tidak menimpanya
    s = s.replace("\\", "\x00BACKSLASH\x00")
    for ch in ["{", "}", "&", "%", "$", "#", "_"]:
        s = s.replace(ch, "\\" + ch)
    s = s.replace("^", "\\^{}")
    s = s.replace("~", "\\~{}")
    # Restore backslash terakhir (setelah brace escape selesai)
    s = s.replace("\x00BACKSLASH\x00", "\\textbackslash{}")
    return s


# =============================================================================
# Citation key generator
# =============================================================================

def _extract_last_name_from_author(author: str) -> str:
    """Ekstrak last name dari string nama author.

    Mendukung dua format umum:
      - "First Middle Last" -> "Last"
      - "Last, First Middle" -> "Last"  (bagian sebelum koma)

    Args:
        author: String nama lengkap.

    Returns:
        Last name yang sudah di-strip.
    """
    author = author.strip().rstrip(",.")
    if not author:
        return ""
    # Format "Last, First": ambil sebelum koma
    if "," in author:
        return author.split(",", 1)[0].strip().rstrip(",.")
    # Format "First Middle Last": ambil kata terakhir
    parts = author.split()
    return parts[-1].rstrip(",.") if parts else ""


def generate_citation_key(entry: dict, index: int) -> str:
    """Generate citation key BibTeX dari entry.

    Format: <lastname><year>_<hash5>
    Contoh: "smith2024_a1b2c"

    Hash 5 karakter pertama dari MD5(DOI) menjamin:
      - Key stabil meskipun dataset berubah urutan/ukuran
      - Tidak ada collision praktis untuk dataset < 1 juta entry

    Args:
        entry: Dict artikel dengan field `authors`, `year`, `pub_date`, `doi`.
        index: Urutan entry (dipakai sebagai fallback jika DOI kosong).

    Returns:
        Citation key string.
    """
    authors = entry.get("authors", [])
    if authors:
        first_author = authors[0].strip()
        last_name = _extract_last_name_from_author(first_author)
    else:
        last_name = ""

    # Year
    year = entry.get("year", "") or ""
    if not year and entry.get("pub_date"):
        year = entry["pub_date"][:4]
    if not year:
        year = "nodate"

    # Bersihkan last name: hanya huruf
    last_name_clean = re.sub(r"[^a-zA-Z]", "", last_name).lower() or "unknown"

    # Suffix: hash DOI (stabil) atau index (fallback)
    doi = (entry.get("doi") or "").strip()
    if doi:
        import hashlib
        suffix = hashlib.md5(doi.lower().encode("utf-8")).hexdigest()[:5]
    else:
        suffix = f"idx{index}"

    return f"{last_name_clean}{year}_{suffix}"


# =============================================================================
# Konverter utama
# =============================================================================

def convert_json_to_bib(data) -> str:
    """Konversi struktur data artikel ke string BibTeX.

    Menerima 2 bentuk input:
      - Dict: {kategori: [artikel, ...], ...}  (output step 07)
      - List: [artikel, ...]                    (output step 10 / selected)

    Args:
        data: Dict atau list berisi artikel.

    Returns:
        String BibTeX siap ditulis ke file .bib.
    """
    # Kumpulkan semua artikel (flatten) — handle dict ATAU list
    entries: List[dict] = []
    if isinstance(data, list):
        entries = [e for e in data if isinstance(e, dict)]
    elif isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                entries.extend(v for v in value if isinstance(v, dict))
            elif isinstance(value, dict):
                entries.append(value)
    # else: entries kosong

    bib_lines: List[str] = []
    bib_lines.append("% Di-generate otomatis oleh find_references_scopus")
    bib_lines.append("% Jangan edit manual — ubah JSON sumber lalu jalankan ulang step 11.")
    bib_lines.append("")

    for idx, entry in enumerate(entries):
        title = (entry.get("title") or "").strip()
        if not title:
            continue

        authors = entry.get("authors", [])
        journal = (entry.get("journal") or "").strip()
        year = entry.get("year", "") or ""
        pub_date = entry.get("pub_date", "") or ""
        volume = (entry.get("volume") or "").strip()
        issue = (entry.get("issue") or "").strip()
        first_page = (entry.get("first_page") or "").strip()
        last_page = (entry.get("last_page") or "").strip()
        doi = (entry.get("doi") or "").strip()
        publisher = (entry.get("publisher") or "").strip()

        # Year fallback dari pub_date
        if not year and pub_date:
            year = pub_date[:4]

        # Month dari pub_date (3-letter abbreviation, lower)
        month = ""
        if pub_date and len(pub_date) >= 7:
            month_num = pub_date[5:7]
            try:
                month = datetime(2000, int(month_num), 1).strftime("%b").lower()
            except (ValueError, IndexError):
                pass

        # Pages: "first--last" jika beda, atau "first" saja
        pages = ""
        if first_page and last_page and first_page != last_page:
            pages = f"{first_page}--{last_page}"
        elif first_page:
            pages = first_page

        cite_key = generate_citation_key(entry, idx)

        # Header entry — PERBAIKAN: pakai "@article{" bukan "## article{"
        bib_lines.append(f"@article{{{cite_key},")

        if authors:
            auth_str = format_authors_bib(authors)
            bib_lines.append(f"  author  = {{{escape_bibtex(auth_str)}}},")

        bib_lines.append(f"  title   = {{{escape_bibtex(title)}}},")

        if journal:
            bib_lines.append(f"  journal = {{{escape_bibtex(journal)}}},")

        if year:
            bib_lines.append(f"  year    = {{{year}}},")
        else:
            bib_lines.append(f"  year    = {{nodate}},")

        if month:
            bib_lines.append(f"  month   = {{{month}}},")

        if volume:
            bib_lines.append(f"  volume  = {{{volume}}},")

        if issue:
            bib_lines.append(f"  number  = {{{issue}}},")

        if pages:
            bib_lines.append(f"  pages   = {{{escape_bibtex(pages)}}},")

        if doi:
            bib_lines.append(f"  doi     = {{{doi}}},")

        if publisher:
            bib_lines.append(f"  publisher = {{{escape_bibtex(publisher)}}},")

        # Hapus koma trailing di baris terakhir field
        if bib_lines[-1].endswith(","):
            bib_lines[-1] = bib_lines[-1][:-1]

        bib_lines.append("}")
        bib_lines.append("")

    return "\n".join(bib_lines)


# =============================================================================
# Entry point
# =============================================================================

def run(input_file: str | None = None, output_file: str | None = None) -> int:
    """Entry point step 11.

    Args:
        input_file: Path JSON input. None = pakai config (step_07_with_journal_info).
            Bisa juga pakai output step 10 (selected) via --input.
        output_file: Path .bib output. None = pakai config (step_11_references_bib).

    Returns:
        Jumlah entry yang berhasil dikonversi.
    """
    log = setup_logging()
    cfg = get_config()
    input_path = input_file or cfg["paths"]["step_07_with_journal_info"]
    output_path = output_file or cfg["paths"]["step_11_references_bib"]

    print_header("Step 11: Konversi JSON ke BibTeX")
    log.info(f"Input  : {input_path}")
    log.info(f"Output : {output_path}")

    try:
        data = load_json(input_path)
    except FileNotFoundError:
        log.error(f"File input tidak ditemukan: {input_path}")
        return 0

    bib_content = convert_json_to_bib(data)
    save_text(bib_content, output_path)

    # Hitung entry
    total_entries = bib_content.count("@article{")
    print(f"\nTotal entry BibTeX di-generate: {total_entries}")
    print(f"File output: {output_path}")

    print_done(f"Step 11 selesai — {total_entries} entry BibTeX")
    return total_entries


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register subcommand untuk step 11."""
    parser = subparsers.add_parser(
        "convert-bib",
        help=DESCRIPTION,
        description=DESCRIPTION,
    )
    parser.add_argument(
        "-i", "--input",
        default=None,
        help="File JSON input (default: step 07. Bisa juga step 10 = selected)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="File .bib output (default: step 11)",
    )
    parser.set_defaults(func=lambda args: run(input_file=args.input, output_file=args.output))
