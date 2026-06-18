"""Step 02: Fetch artikel dari OpenAlex API berdasarkan ISSN + query.

Input  : config.yaml (issn_electronic + search_groups)
         data/01_issn_list.txt (alternatif: bisa pakai file hasil step 01)
Output : data/02_openalex_raw.json

Perilaku:
   - Untuk setiap search_group di config, kirim query ke OpenAlex API
   - Filter: ISSN di salah satu daftar, tahun antara year_from–year_to,
     has_doi=true, has_abstract=true, language di `language`
   - Pecah ISSN jadi batch (issn_batch_size) agar URL tidak terlalu panjang
   - Paginasi via cursor sampai habis atau mencapai max_results_per_group
   - Rekonstruksi abstrak dari inverted-index OpenAlex
   - Tulis output: { group_name: [article, ...], ... }

Setara dengan script lama: openalex_fetch.py
"""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Set, Tuple

import requests

from ..config import get_config
from ..utils import print_done, print_header, save_json, setup_logging
from ..utils import load_lines


DESCRIPTION = "Fetch artikel dari OpenAlex API per search group"

# Tag untuk find-refs list (M13: auto-derived dari module attribute)
MANUAL_OR_AUTO = "AUTO"


# =============================================================================
# Helpers: rekonstruksi abstrak & format tanggal
# =============================================================================

def reconstruct_abstract(abstract_inverted_index: Dict[str, List[int]] | None) -> str:
    """Rekonstruksi abstrak dari format inverted-index OpenAlex.

    OpenAlex menyimpan abstrak sebagai {word: [pos1, pos2, ...]}. Fungsi ini
    mengembalikannya ke string linear dengan mengurutkan berdasarkan posisi.

    Args:
        abstract_inverted_index: Mapping word -> list posisi.

    Returns:
        String abstrak utuh. "" jika input kosong/None.
    """
    if not abstract_inverted_index:
        return ""
    try:
        word_positions: List[Tuple[int, str]] = []
        for word, positions in abstract_inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort(key=lambda x: x[0])
        return " ".join(w for _, w in word_positions).strip()
    except Exception:
        return ""


def format_date(date_str: str) -> str:
    """Lengkapi date string ke format YYYY-MM-DD.

    OpenAlex kadang hanya memberi tahun ("2023") atau tahun-bulan ("2023-05").
    Fungsi ini melengkapi ke tanggal penuh dengan default "-01".

    Args:
        date_str: Date string parsial dari OpenAlex.

    Returns:
        Date string YYYY-MM-DD, atau input asli jika tidak dikenali.
    """
    if not date_str:
        return ""
    if len(date_str) >= 10:
        return date_str[:10]
    if len(date_str) >= 7:
        return date_str + "-01"
    if len(date_str) >= 4:
        return date_str + "-01-01"
    return date_str


# =============================================================================
# Extract satu artikel dari response OpenAlex
# =============================================================================

def extract_article_data(work: Dict[str, Any], issn_set: Set[str]) -> Dict[str, Any] | None:
    """Ekstrak field penting dari satu work object OpenAlex.

    Args:
        work: Satu entry dari response `results` OpenAlex.
        issn_set: Set ISSN yang dianggap valid (untuk identifikasi issn_electronic).

    Returns:
        Dict artikel dengan field terstandarisasi, atau None jika gagal.
    """
    try:
        doi = work.get("doi", "") or ""
        if doi:
            doi = doi.replace("https://doi.org/", "")

        biblio = work.get("biblio", {}) or {}
        primary_location = work.get("primary_location", {}) or {}
        source = primary_location.get("source", {}) or {}
        oa_status = work.get("open_access", {}) or {}

        # Cari ISSN source yang ada di set issn_electronic kita
        # M14: pakai None (bukan "") kalau tidak ketemu, agar step 07 bisa cek
        # "info is None" daripada harus handle empty string
        issn_electronic = None
        for src_issn in (source.get("issn") or []):
            if src_issn in issn_set:
                issn_electronic = src_issn
                break

        # Ambil daftar author
        authors: List[str] = []
        for authorship in (work.get("authorships") or []):
            display_name = (authorship.get("author") or {}).get("display_name", "")
            if display_name:
                authors.append(display_name)

        # Klasifikasi Open Access
        is_oa = oa_status.get("is_oa", False)
        oa_url = oa_status.get("oa_url", "")
        if is_oa:
            open_access = "Yes"
        elif oa_url:
            open_access = "Partial"
        else:
            open_access = "No"

        # Field bibliografi (volume, issue, halaman)
        volume = biblio.get("volume")
        issue = biblio.get("issue")
        first_page = biblio.get("first_page")
        last_page = biblio.get("last_page")

        return {
            "doi": doi,
            "title": work.get("title", "") or "",
            "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
            "authors": authors,
            "year": work.get("publication_year", "") or "",
            "pub_date": format_date(work.get("publication_date", "") or ""),
            "volume": "" if volume is None else str(volume),
            "issue": "" if issue is None else str(issue),
            "first_page": "" if first_page is None else str(first_page),
            "last_page": "" if last_page is None else str(last_page),
            "publisher": source.get("host_organization_name", "") or "",
            "journal": source.get("display_name", "") or "",
            # M14: None (bukan "") supaya step 07 bisa cek "if issn_electronic is not None"
            "issn_electronic": issn_electronic,
            "open_access": open_access,
        }
    except Exception as e:
        print(f"  Warning: Gagal extract data - {e}")
        return None


# =============================================================================
# Fetch satu search group
# =============================================================================

def fetch_group(
    group_name: str,
    search_query: str,
    issn_list: List[str],
    issn_set: Set[str],
    year_from: int,
    year_to: int,
    lang_list: List[str],
    per_page: int,
    delay: float,
    max_results: int,
    issn_batch_size: int,
) -> Tuple[List[Dict[str, Any]], int]:
    """Fetch semua artikel untuk satu search_group.

    Mengirim query ke OpenAlex dengan filter ISSN (dipecah per batch),
    lalu paginasi via cursor sampai habis.

    Robustness:
      - User-Agent header untuk masuk "polite pool" OpenAlex (rate limit lebih tinggi)
      - Retry dengan exponential backoff untuk HTTP 429 (rate limit) dan 503 (service unavailable)
      - Max retry count untuk Timeout (hindari infinite loop)

    Args:
        group_name: Nama group (untuk logging).
        search_query: Query boolean OpenAlex.
        issn_list: List ISSN electronic.
        issn_set: Set ISSN (versi set, sudah di-precompute di caller untuk efisiensi).
        year_from, year_to: Rentang tahun publikasi.
        lang_list: List bahasa yang diizinkan (mis. ["en"]).
        per_page: Jumlah hasil per halaman API.
        delay: Jeda antar request (detik).
        max_results: Batas total hasil (0 = tanpa batas).
        issn_batch_size: Ukuran batch ISSN per request.

    Returns:
        Tuple (list_artikel, total_artikel_diambil).
    """
    if not search_query:
        print(f"  Group '{group_name}' tidak memiliki query, dilewati.")
        return [], 0

    lang_filter = ""
    if lang_list:
        lang_filter = f",language:{'|'.join(lang_list)}"

    issn_batches = [issn_list[i:i + issn_batch_size] for i in range(0, len(issn_list), issn_batch_size)]

    base_url = "https://api.openalex.org/works"
    # User-Agent untuk masuk "polite pool" OpenAlex (rate limit lebih tinggi).
    # OpenAlex docs: https://docs.openalex.org/how-to-use-the-api/rate-limits-and-credentials
    headers = {
        "User-Agent": "find_references_scopus/1.0 (https://github.com/research-pipeline)",
    }

    all_articles: List[Dict[str, Any]] = []
    seen_dois: Set[str] = set()
    total_fetched = 0

    # Konstanta retry
    MAX_TIMEOUT_RETRIES = 5      # maksimal 5x retry untuk Timeout
    MAX_HTTP_RETRIES = 4         # maksimal 4x retry untuk 429/503

    for batch_idx, batch in enumerate(issn_batches):
        print(f"    Batch ISSN {batch_idx + 1}/{len(issn_batches)} ({len(batch)} ISSN)")

        params = {
            "filter": (
                f"primary_location.source.issn:{'|'.join(batch)},"
                f"from_publication_date:{year_from}-01-01,"
                f"to_publication_date:{year_to}-12-31,"
                f"has_doi:true,"
                f"has_abstract:true{lang_filter}"
            ),
            "search": search_query,
            "per_page": per_page,
        }

        cursor = "*"
        page = 0
        batch_fetched = 0
        timeout_retries = 0
        http_retries = 0

        while cursor:
            page += 1
            params["cursor"] = cursor

            try:
                response = requests.get(base_url, params=params, headers=headers, timeout=60)
                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])
                meta = data.get("meta", {})

                # Reset retry counters setelah sukses
                timeout_retries = 0
                http_retries = 0

                if page == 1:
                    estimated = meta.get("count", 0)
                    print(f"      Estimasi artikel: ~{estimated}")

                for work in results:
                    if max_results > 0 and total_fetched >= max_results:
                        break

                    doi = work.get("doi", "") or ""
                    if doi:
                        doi_clean = doi.replace("https://doi.org/", "")
                        if doi_clean in seen_dois:
                            continue
                        seen_dois.add(doi_clean)

                    entry = extract_article_data(work, issn_set)
                    if not entry:
                        continue

                    all_articles.append(entry)
                    total_fetched += 1
                    batch_fetched += 1

                next_cursor = meta.get("next_cursor")
                if not next_cursor or next_cursor == "null" or not results:
                    cursor = None
                else:
                    cursor = next_cursor

                print(f"      Page {page}: {len(results)} hasil, total group ini: {batch_fetched} artikel")
                if max_results > 0 and total_fetched >= max_results:
                    break

                if cursor:  # hanya sleep kalau masih ada halaman berikutnya
                    time.sleep(delay)

            except requests.exceptions.Timeout:
                timeout_retries += 1
                if timeout_retries > MAX_TIMEOUT_RETRIES:
                    print(f"      Timeout page {page} - {MAX_TIMEOUT_RETRIES}x retry gagal, skip batch.")
                    break
                backoff = delay * (2 ** (timeout_retries - 1))  # exponential backoff
                print(f"      Timeout page {page} (retry {timeout_retries}/{MAX_TIMEOUT_RETRIES}), tunggu {backoff}s...")
                time.sleep(backoff)
                page -= 1  # jangan increment page untuk retry
                continue
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response is not None else 0
                # Retry untuk 429 (rate limit) dan 503 (service unavailable)
                if status_code in (429, 503):
                    http_retries += 1
                    if http_retries > MAX_HTTP_RETRIES:
                        print(f"      HTTP {status_code} page {page} - {MAX_HTTP_RETRIES}x retry gagal, skip batch.")
                        break
                    backoff = delay * (2 ** http_retries)  # exponential backoff
                    # 429 biasanya kasih Retry-After header
                    retry_after = e.response.headers.get("Retry-After") if e.response else None
                    if retry_after:
                        try:
                            backoff = float(retry_after)
                        except ValueError:
                            pass
                    print(f"      HTTP {status_code} page {page} (retry {http_retries}/{MAX_HTTP_RETRIES}), tunggu {backoff}s...")
                    time.sleep(backoff)
                    page -= 1  # jangan increment page untuk retry
                    continue
                # HTTP error lain (4xx selain 429, 5xx selain 503) = tidak retryable
                print(f"      HTTP Error: {e}")
                if e.response is not None:
                    print(f"      Response: {e.response.text[:500]}")
                break
            except Exception as e:
                print(f"      Error: {e}")
                break

        print(f"    Batch {batch_idx + 1} selesai -> {batch_fetched} artikel untuk group ini")
        if max_results > 0 and total_fetched >= max_results:
            break
        # Jeda antar batch (bukan antar page)
        if batch_idx < len(issn_batches) - 1:
            time.sleep(delay)

    return all_articles, total_fetched


# =============================================================================
# Entry point
# =============================================================================

def run(issn_file: str | None = None) -> int:
    """Entry point step 02.

    Args:
        issn_file: Path opsional ke file ISSN (satu per baris). Jika None,
            pakai `issn_electronic` dari config.yaml.

    Returns:
        Total artikel yang berhasil di-fetch (dengan duplikasi antar group).
    """
    log = setup_logging()
    cfg = get_config()

    # Sumber ISSN: prioritaskan file dari step 01, fallback ke config.yaml
    if issn_file:
        issn_list = load_lines(issn_file)
        log.info(f"Memuat ISSN dari file: {issn_file} ({len(issn_list)} ISSN)")
    elif cfg.get("issn_electronic"):
        issn_list = list(cfg["issn_electronic"])
        log.info(f"Memuat ISSN dari config.yaml ({len(issn_list)} ISSN)")
    else:
        # Coba load otomatis dari output step 01
        step1_output = cfg["paths"]["step_01_issn_list"]
        if os.path.isfile(step1_output):
            issn_list = load_lines(step1_output)
            log.info(f"Memuat ISSN otomatis dari {step1_output} ({len(issn_list)} ISSN)")
        else:
            log.error(
                "ISSN kosong. Jalankan `find-refs get-issn` dulu, "
                "atau isi `issn_electronic` di config.yaml."
            )
            return 0

    if not issn_list:
        log.error("Daftar ISSN kosong. Tidak ada yang bisa di-fetch.")
        return 0

    # Pre-compute set ISSN sekali saja (M3: hoist set dari dalam fetch_group)
    # Sebelumnya set() di-rebuild di setiap call fetch_group -> N×O(N) untuk N group
    issn_set = set(issn_list)

    search_groups = cfg.get("search_groups", {})
    if not search_groups:
        log.error("search_groups kosong di config.yaml.")
        return 0

    output_path = cfg["paths"]["step_02_openalex_raw"]
    year_from = cfg.get("year_from", 2021)
    year_to = cfg.get("year_to", 2026)
    language = cfg.get("language", ["en"])
    per_page = cfg.get("per_page", 200)
    delay = cfg.get("request_delay", 1.0)
    max_results = cfg.get("max_results_per_group", 0)
    issn_batch_size = cfg.get("issn_batch_size", 50)

    print_header("Step 02: Fetch Artikel dari OpenAlex")
    print(f"  ISSN count       : {len(issn_list)}")
    print(f"  Year range       : {year_from} - {year_to}")
    print(f"  Language         : {language if language else '(semua)'}")
    print(f"  Output file      : {output_path}")
    print(f"  Max results/group: {max_results if max_results > 0 else 'tanpa batas'}")
    print(f"\nDaftar kelompok pencarian ({len(search_groups)} group):")
    for idx, (name, conf) in enumerate(search_groups.items(), 1):
        print(f"  {idx}. {name}")
        print(f"     query: {conf['query']}")
    print()

    grouped_results: Dict[str, List[Dict[str, Any]]] = {}
    group_counts: Dict[str, int] = {}

    for group_name, group_config in search_groups.items():
        print(f"\n>>> Memproses kelompok: {group_name}")
        articles, count = fetch_group(
            group_name=group_name,
            search_query=group_config.get("query", ""),
            issn_list=issn_list,
            issn_set=issn_set,
            year_from=year_from,
            year_to=year_to,
            lang_list=language,
            per_page=per_page,
            delay=delay,
            max_results=max_results,
            issn_batch_size=issn_batch_size,
        )
        grouped_results[group_name] = articles
        group_counts[group_name] = count
        print(f"  <<< Kelompok '{group_name}' selesai -> {count} artikel ditemukan.")
        time.sleep(delay)

    # Tulis output
    save_json(grouped_results, output_path)

    print()
    print_header("Ringkasan Hasil Step 02", width=60)
    for name, count in group_counts.items():
        print(f"  {name:<40} : {count} artikel")
    print(f"\n  Total artikel (dengan duplikasi antar kelompok): {sum(group_counts.values())}")
    print(f"  Output file: {os.path.abspath(output_path)}")
    print(f"  Selesai pada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    print_done(f"Step 02 selesai — {sum(group_counts.values())} artikel total")
    return sum(group_counts.values())


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register subcommand untuk step 02."""
    parser = subparsers.add_parser(
        "fetch",
        help=DESCRIPTION,
        description=DESCRIPTION,
    )
    parser.add_argument(
        "--issn-file", "-f",
        default=None,
        help="Path ke file ISSN (satu per baris). Default: pakai config.yaml atau output step 01.",
    )
    parser.set_defaults(func=lambda args: run(issn_file=args.issn_file))
