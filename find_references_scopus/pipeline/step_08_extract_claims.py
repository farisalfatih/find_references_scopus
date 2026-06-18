"""Step 08: Ekstrak kalimat berisi DOI dari file Markdown.

Input  : file Markdown (CLI argumen --input, default: data/draft.md)
Output : data/08_claims.json

Perilaku:
   - Baca file Markdown (mis. draf latar belakang penelitian)
   - Hapus baris heading (# Title, ## Subtitle, dst.)
   - Hapus baris numbering heading (mis. "1.1 Latar Belakang")
   - Tokenisasi per paragraf -> per kalimat (Punkt dari NLTK)
   - Untuk setiap kalimat, cek apakah mengandung DOI (pola regex 10.xxxx/...)
   - Kumpulkan semua kalimat dengan DOI + daftar DOI unik

Setara dengan script lama: extract_claims.py
"""

from __future__ import annotations

import argparse
import os
import re
from typing import List

# nltk adalah dependency opsional — import di sini agar error jelas kalau belum install
try:
    from nltk.tokenize.punkt import PunktParameters, PunktSentenceTokenizer
except ImportError as e:
    raise ImportError(
        "Package 'nltk' belum terinstall. Jalankan: pip install nltk"
    ) from e


from ..config import get_config
from ..utils import print_done, print_header, save_json, setup_logging


DESCRIPTION = "Ekstrak kalimat berisi DOI dari file Markdown"

# Tag untuk find-refs list (M13: auto-derived dari module attribute)
MANUAL_OR_AUTO = "MANUAL"


# Pola regex DOI (Crossref-compliant, case-insensitive)
# - Registrant code 4-9 digit: 10\.\d{4,9}/
# - Suffix: greedy match karakter yang valid di DOI (alfanumerik + -.~_/()+=;:)
# - Trailing punctuation (.,;:)]}""') di-strip di post-processing
#   via _strip_doi_punctuation(), BUKAN di regex (lebih reliable)
DOI_PATTERN = r"10\.\d{4,9}/[^\s\"<>{}|\\^`]+"

# Karakter trailing yang harus di-strip dari DOI yang ke-ekstrak
# (punctuation yang biasanya merupakan akhir kalimat, bukan bagian DOI)
_DOI_TRAILING_PUNCT = ".,;:)]}\"'"

# Singkatan yang sering membingungkan tokenizer kalimat.
# CATATAN: Punkt butuh abbreviation TANPA trailing period, tapi dengan internal
# period utk singkatan seperti "e.g." -> harus didaftarkan sebagai "e.g" (dengan
# titik internal, TANPA titik trailing).
CUSTOM_ABBREVIATIONS = [
    # English academic — dengan titik internal untuk singkatan multi-kata
    "e.g", "i.e", "et al", "vs", "etc", "cf", "approx",
    "dept", "ed", "vol", "no", "pp", "fig", "eq", "dr", "prof", "inc", "ltd",
    # Indonesian
    "dkk", "dll", "dsb", "dst", "sda", "yb", "nrb", "hp", "jl", "rt", "rw",
]


def _build_tokenizer() -> PunktSentenceTokenizer:
    """Bangun tokenizer kalimat dengan singkatan kustom.

    Returns:
        PunktSentenceTokenizer yang sudah dikonfigurasi.
    """
    punkt_params = PunktParameters()
    punkt_params.abbrev_types = set(CUSTOM_ABBREVIATIONS)
    return PunktSentenceTokenizer(punkt_params)


def _strip_doi_punctuation(doi: str) -> str:
    """Strip trailing punctuation dari DOI yang ke-ekstrak.

    DOI valid tidak boleh diakhiri .,;:)]}"' (punctuation kalimat).
    Tapi titik di tengah DOI (mis. 10.1000/xyz.123) harus dipertahankan.

    Args:
        doi: String DOI hasil regex.

    Returns:
        DOI dengan trailing punctuation di-strip.
    """
    return doi.rstrip(_DOI_TRAILING_PUNCT)


def extract_sentences_with_doi(text: str, tokenizer: PunktSentenceTokenizer) -> List[dict]:
    """Ekstrak kalimat yang mengandung DOI dari teks Markdown.

    Args:
        text: Isi file Markdown.
        tokenizer: Tokenizer kalimat yang sudah dikonfigurasi.

    Returns:
        List dict {"sentence": str, "dois": list[str]} untuk setiap kalimat
        yang mengandung minimal 1 DOI. DOI sudah di-strip trailing punctuation
        dan dinormalisasi ke lowercase untuk konsistensi lookup.
    """
    # Hapus baris markdown heading (# Title, ## Subtitle, dst.)
    # Hanya baris yang MULAI dengan # (bukan # di tengah kalimat)
    text = re.sub(r"^#{1,6}\s+.*$", "", text, flags=re.MULTILINE)

    # Hapus baris numbering heading (mis. "1.1 Latar Belakang").
    # Hanya baris yang polanya: angka.titik.angka... diikuti SPASI + huruf besar
    # + sisanya tidak terlalu panjang (untuk hindari false positive pada kalimat
    # biasa seperti "10 Articles were reviewed").
    # Syarat tambahan: setelah heading, baris berikutnya biasanya kosong.
    text = re.sub(
        r"^\d+(\.\d+){0,3}\s+[A-Z][^\n.]{0,80}$",
        "",
        text,
        flags=re.MULTILINE,
    )

    # Split per paragraf dulu (kalimat di paragraf berbeda tidak digabung)
    paragraphs = re.split(r"\n\s*\n", text)
    results: List[dict] = []

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        sentences = tokenizer.tokenize(para)
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            doi_list_raw = re.findall(DOI_PATTERN, sent, flags=re.IGNORECASE)
            if not doi_list_raw:
                continue
            # Strip trailing punctuation + normalize ke lowercase untuk lookup
            doi_list = [_strip_doi_punctuation(d).lower() for d in doi_list_raw]
            # Hilangkan duplikat dalam kalimat yang sama, pertahankan urutan
            seen = set()
            doi_list_unique: List[str] = []
            for d in doi_list:
                if d not in seen:
                    seen.add(d)
                    doi_list_unique.append(d)
            results.append({
                "sentence": sent,
                "dois": doi_list_unique,
            })
    return results


def run(input_file: str | None = None, output_file: str | None = None) -> int:
    """Entry point step 08.

    Args:
        input_file: Path file Markdown input. None = pakai config (data/draft.md).
        output_file: Path JSON output. None = pakai config (step_08_claims).

    Returns:
        Jumlah kalimat yang mengandung DOI.
    """
    log = setup_logging()
    cfg = get_config()

    # Default input: data/draft.md (jika tidak ada di config, fallback)
    if input_file:
        input_path = input_file
    elif "step_08_input_md" in cfg.get("paths", {}):
        input_path = cfg["paths"]["step_08_input_md"]
    else:
        input_path = "data/draft.md"

    output_path = output_file or cfg["paths"]["step_08_claims"]

    print_header("Step 08: Ekstrak Kalimat Berisi DOI dari Markdown")
    log.info(f"Input  : {input_path}")
    log.info(f"Output : {output_path}")

    if not os.path.isfile(input_path):
        log.error(
            f"File Markdown tidak ditemukan: {input_path}\n"
            f"Gunakan --input untuk menentukan path file Markdown."
        )
        return 0

    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()

    tokenizer = _build_tokenizer()
    hasil = extract_sentences_with_doi(text, tokenizer)

    # Kumpulkan DOI unik dari semua kalimat (sudah lowercase + stripped di extract)
    all_dois: List[str] = []
    seen: set[str] = set()
    for item in hasil:
        for doi in item["dois"]:
            # doi sudah di-lowercase + stripped di extract_sentences_with_doi
            if doi not in seen:
                seen.add(doi)
                all_dois.append(doi)

    output = {
        "results": hasil,
        "doi_list": all_dois,
    }

    save_json(output, output_path)

    print(f"\nTotal kalimat dengan DOI: {len(hasil)}")
    print(f"Total DOI unik: {len(all_dois)}")

    print_done(f"Step 08 selesai — {len(hasil)} kalimat, {len(all_dois)} DOI unik")
    return len(hasil)


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register subcommand untuk step 08."""
    parser = subparsers.add_parser(
        "extract-claims",
        help=DESCRIPTION,
        description=DESCRIPTION,
    )
    parser.add_argument(
        "-i", "--input",
        default=None,
        help="File Markdown input (default: data/draft.md)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="File JSON output (default: step 08)",
    )
    parser.set_defaults(func=lambda args: run(input_file=args.input, output_file=args.output))
