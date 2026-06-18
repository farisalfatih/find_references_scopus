"""Utility bersama yang dipakai semua step pipeline.

Tujuan: hilangkan duplikasi fungsi load_json/save_json/format_authors
yang sebelumnya ada di banyak file. Semua fungsi di sini sekali didefinisikan
dan di-impor ulang oleh setiap step.

Isi:
    - load_json / save_json    : baca/tulis JSON dengan encoding konsisten
    - format_authors_full      : format "Last1 and Last2" atau "Last1 et al."
    - format_authors_bib       : format BibTeX "Author1 and Author2 and ..."
    - normalize_name           : kapitalisasi nama yang sebelumnya ALL CAPS
    - setup_logging            : konfigurasi logging terpusat
    - print_header / print_done: banner konsisten untuk output CLI
"""

from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any, Dict, Iterable, List

from .config import get_config


# =============================================================================
# JSON helpers
# =============================================================================

def load_json(file_path: str) -> Any:
    """Baca file JSON dengan encoding UTF-8.

    Args:
        file_path: Path absolut ke file JSON.

    Returns:
        Data Python hasil parse (dict / list / scalar).

    Raises:
        FileNotFoundError: jika file tidak ada.
        json.JSONDecodeError: jika format JSON tidak valid.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: Any, file_path: str, indent: int = 2) -> None:
    """Tulis data ke file JSON dengan ensure_ascii=False (preserve Unicode).

    Otomatis membuat direktori parent jika belum ada.

    Args:
        data: Data Python yang akan di-serialize.
        file_path: Path absolut tujuan.
        indent: Jumlah spasi indentasi (default 2).
    """
    from .config import ensure_parent_dir
    ensure_parent_dir(file_path)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def load_text(file_path: str) -> str:
    """Baca file teks biasa (UTF-8)."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def save_text(text: str, file_path: str) -> None:
    """Tulis teks ke file (UTF-8). Otomatis buat direktori parent."""
    from .config import ensure_parent_dir
    ensure_parent_dir(file_path)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(text)


def load_lines(file_path: str) -> List[str]:
    """Baca file teks per baris, kembalikan list baris non-kosong (di-strip)."""
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


# =============================================================================
# Format nama author
# =============================================================================

def normalize_name(name: str) -> str:
    """Kapitalisasi nama yang sebelumnya ALL CAPS.

    Contoh: "SMITH" -> "Smith", "O'BRIEN" -> "O'Brien",
    "VAN DER BERG" -> "Van Der Berg".

    H3 (apostrofik): Handle apostrophe di nama seperti O'BRIEN, O'NEILL.
    Sebelumnya re.split(r"([-\\s]+)") tidak memecah apostrophe, sehingga
    "O'BRIEN".capitalize() menghasilkan "O'brien" (salah). Fix: pisahkan
    apostrophe sebagai boundary juga.

    Args:
        name: Nama yang mungkin all-caps.

    Returns:
        Nama dengan kapitalisasi title-case jika sebelumnya all-caps,
        nama asli jika tidak.
    """
    if not name:
        return ""
    if name.isupper():
        # Pisahkan berdasarkan whitespace, dash, ATAU apostrophe
        # Pertahankan delimiter di hasil split
        parts = re.split(r"([-\s']+)", name)
        normalized_parts = []
        for part in parts:
            if part and part[0].isalpha():
                # Untuk bagian setelah apostrophe (mis. "BRIEN" di "O'BRIEN"),
                # capitalize jadi "Brien"
                normalized_parts.append(part.capitalize())
            else:
                normalized_parts.append(part)
        return "".join(normalized_parts)
    return name


def extract_last_name(full_name: str) -> str:
    """Ambil last name (kata terakhir) dari nama lengkap.

    Bersihkan koma/titik di akhir, lalu normalize kapitalisasi.

    L10 (suffix): Handle nama dengan suffix generasi (Jr., Sr., III, dll).
    Jika kata terakhir adalah suffix umum, ambil kata sebelum suffix.

    Args:
        full_name: Nama lengkap, mis. "John Ronald Reuel Tolkien".

    Returns:
        Last name yang sudah dinormalisasi, mis. "Tolkien".
    """
    parts = full_name.strip().split()
    if not parts:
        return ""
    # Suffix umum yang BUKAN last name sebenarnya
    suffixes = {"jr.", "jr", "sr.", "sr", "ii", "iii", "iv", "v", "phd", "ph.d.", "md", "dr"}
    # Buang suffix dari akhir
    while parts and parts[-1].lower().rstrip(",.") in suffixes and len(parts) > 1:
        parts.pop()
    last = parts[-1].rstrip(",.")
    return normalize_name(last)


def format_authors_full(authors_list: Iterable[str]) -> str:
    """Format daftar author menjadi "Last1", "Last1 and Last2", atau "Last1 et al."

    Dipakai di output Markdown (step_09_extract_references).

    Args:
        authors_list: List nama lengkap author.

    Returns:
        String yang sudah diformat. "Unknown" jika list kosong.
    """
    authors_list = list(authors_list or [])
    if not authors_list:
        return "Unknown"
    last_names = [extract_last_name(a) for a in authors_list]
    if len(last_names) == 1:
        return last_names[0]
    if len(last_names) == 2:
        return f"{last_names[0]} and {last_names[1]}"
    return f"{last_names[0]} et al."


def format_authors_bib(authors_list: Iterable[str]) -> str:
    """Format daftar author untuk BibTeX: "Author1 and Author2 and ...".

    BibTeX memakai " and " sebagai separator antar author (bukan koma).
    Dipakai di step_11_convert_bib.

    Args:
        authors_list: List nama lengkap author.

    Returns:
        String format BibTeX. "" jika list kosong.
    """
    authors_list = list(authors_list or [])
    if not authors_list:
        return ""
    return " and ".join(authors_list)


# =============================================================================
# Logging & CLI helpers
# =============================================================================

def setup_logging(level: str | None = None, log_format: str | None = None,
                  date_format: str | None = None) -> logging.Logger:
    """Konfigurasi logging root berdasarkan config.yaml.

    L4: Sebelumnya panggil basicConfig tiap call. basicConfig idempotent
    (no-op setelah root configured), TAPI jika level berbeda antar call,
    di-ignore. Fix: gunakan flag global _LOGGING_CONFIGURED + force=True
    kalau config berubah.

    Args:
        level: Override level (DEBUG/INFO/WARNING/ERROR). None = pakai config.
        log_format: Override format. None = pakai config.
        date_format: Override date format. None = pakai config.

    Returns:
        Logger root yang sudah dikonfigurasi.
    """
    try:
        cfg = get_config()
        log_cfg = cfg.get("logging", {})
        new_level = (level or log_cfg.get("level", "INFO")).upper()
        new_format = log_format or log_cfg.get("format", "%(asctime)s [%(levelname)s] %(message)s")
        new_date_format = date_format or log_cfg.get("date_format", "%Y-%m-%d %H:%M:%S")
    except Exception:
        new_level = (level or "INFO").upper()
        new_format = log_format or "%(asctime)s [%(levelname)s] %(message)s"
        new_date_format = date_format or "%Y-%m-%d %H:%M:%S"

    # Hanya konfigurasi ulang kalau belum pernah dikonfigurasi ATAU level berubah
    global _LOGGING_CONFIGURED, _LOGGING_LEVEL
    if not _LOGGING_CONFIGURED or _LOGGING_LEVEL != new_level:
        logging.basicConfig(
            level=getattr(logging, new_level, logging.INFO),
            format=new_format,
            datefmt=new_date_format,
            stream=sys.stdout,
            force=True,  # Override konfigurasi sebelumnya
        )
        _LOGGING_CONFIGURED = True
        _LOGGING_LEVEL = new_level

    return logging.getLogger("find_references_scopus")


# Flag global untuk tracking konfigurasi logging (L4)
_LOGGING_CONFIGURED = False
_LOGGING_LEVEL: str | None = None


def print_header(title: str, width: int = 60) -> None:
    """Cetak banner header konsisten di awal setiap step.

    Args:
        title: Judul step.
        width: Lebar banner (default 60).
    """
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def print_done(message: str, width: int = 60) -> None:
    """Cetak footer penutup konsisten di akhir setiap step."""
    print()
    print("=" * width)
    print(f"  {message}")
    print("=" * width)


def print_summary(rows: Dict[str, int], label: str = "artikel") -> None:
    """Cetak ringkasan jumlah per kategori dalam format tabel rapi.

    Args:
        rows: Mapping nama kategori -> jumlah.
        label: Satuan label, mis. "artikel" atau "jurnal".
    """
    if not rows:
        print("  (tidak ada data)")
        return
    max_name = max(len(name) for name in rows.keys())
    for name, count in rows.items():
        print(f"  {name:<{max_name}}  : {count} {label}")
    print(f"\n  Total: {sum(rows.values())} {label}")
