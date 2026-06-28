"""Step 02: Fetch artikel dari OpenAlex API berdasarkan ISSN + query.

Input  : config.yaml (issn_electronic + search_groups)
         data/01_issn_list.txt (alternatif: bisa pakai file hasil step 01)
         .env                    (OPENALEX_API_KEY, OPENALEX_MAILTO)
Output : data/02_openalex_raw.json

Perilaku:
   - Untuk setiap search_group di config, kirim query ke OpenAlex API
   - Filter: ISSN di salah satu daftar, tahun antara year_from-year_to,
     has_doi=true, has_abstract=true, language di `language`
   - Pencarian keyword menggunakan abstract.search (di filter) agar
     hasil hanya artikel yang BENAR-BENAR mengandung keyword di abstrak
   - Pecah ISSN jadi batch (issn_batch_size) agar URL tidak terlalu panjang
   - Paginasi via cursor sampai habis atau mencapai max_results_per_group
   - Rekonstruksi abstrak dari inverted-index OpenAlex
   - API key dari .env digunakan untuk akses polite pool (rate limit lebih tinggi)
   - Tulis output: { group_name: [article, ...], ... }

Setara dengan script lama: openalex_fetch.py
"""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import requests
from dotenv import load_dotenv

from ..config import get_config, PROJECT_ROOT
from ..utils import print_done, print_header, save_json, setup_logging
from ..utils import load_lines


DESCRIPTION = "Fetch artikel dari OpenAlex API per search group (pencarian di abstract)"

# Tag untuk find-refs list (M13: auto-derived dari module attribute)
MANUAL_OR_AUTO = "AUTO"


# =============================================================================
# Load credentials dari .env
# =============================================================================

def load_openalex_credentials() -> Tuple[str | None, str | None]:
    """Load OPENALEX_API_KEY dan OPENALEX_MAILTO dari .env.

    Cari file .env di:
      1. Root project (PROJECT_ROOT / .env)
      2. Current working directory

    Returns:
        Tuple (api_key, mailto). Masing-masing None jika tidak ada.
    """
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        env_path = Path.cwd() / ".env"

    if env_path.is_file():
        load_dotenv(env_path, override=True)

    api_key = os.getenv("OPENALEX_API_KEY", "")
    mailto = os.getenv("OPENALEX_MAILTO", "")

    api_key = api_key if api_key and not api_key.startswith("your_") else None
    mailto = mailto if mailto and not mailto.startswith("your_") else None

    return api_key, mailto


# =============================================================================
# Helpers: rekonstruksi abstrak & format tanggal
# =============================================================================

def reconstruct_abstract(abstract_inverted_index: Dict[str, List[int]] | None) -> str:
    """Rekonstruksi abstrak dari format inverted-index OpenAlex."""
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
    """Lengkapi date string ke format YYYY-MM-DD."""
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
    """Ekstrak field penting dari satu work object OpenAlex."""
    try:
        doi = work.get("doi", "") or ""
        if doi:
            doi = doi.replace("https://doi.org/", "")

        biblio = work.get("biblio", {}) or {}
        primary_location = work.get("primary_location", {}) or {}
        source = primary_location.get("source", {}) or {}
        oa_status = work.get("open_access", {}) or {}

        issn_electronic = None
        for src_issn in (source.get("issn") or []):
            if src_issn in issn_set:
                issn_electronic = src_issn
                break

        authors: List[str] = []
        for authorship in (work.get("authorships") or []):
            display_name = (authorship.get("author") or {}).get("display_name", "")
            if display_name:
                authors.append(display_name)

        is_oa = oa_status.get("is_oa", False)
        oa_url = oa_status.get("oa_url", "")
        if is_oa:
            open_access = "Yes"
        elif oa_url:
            open_access = "Partial"
        else:
            open_access = "No"

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
    api_key: str | None = None,
    mailto: str | None = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """Fetch semua artikel untuk satu search_group.

    Menggunakan abstract.search di filter OpenAlex (seperti openalex_fetch.py)
    untuk memastikan artikel BENAR-BENAR mengandung keyword di abstrak.

    Robustness:
      - User-Agent header + API key/mailto untuk polite pool
      - Retry dengan exponential backoff untuk HTTP 429 dan 503
      - Max retry count untuk Timeout

    Args:
        group_name: Nama group (untuk logging).
        search_query: Query boolean OpenAlex.
        issn_list: List ISSN electronic.
        issn_set: Set ISSN (versi set, sudah di-precompute di caller).
        year_from, year_to: Rentang tahun publikasi.
        lang_list: List bahasa yang diizinkan (mis. ["en"]).
        per_page: Jumlah hasil per halaman API.
        delay: Jeda antar request (detik).
        max_results: Batas total hasil (0 = tanpa batas).
        issn_batch_size: Ukuran batch ISSN per request.
        api_key: OpenAlex API key (opsional, untuk polite pool).
        mailto: Email untuk OpenAlex polite pool (opsional).

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
    headers = {
        "User-Agent": "find_references_scopus/1.0 (https://github.com/research-pipeline)",
    }

    # Parameter ekstra untuk polite pool
    extra_params: dict = {}
    if api_key:
        extra_params["api_key"] = api_key
    if mailto:
        extra_params["mailto"] = mailto

    all_articles: List[Dict[str, Any]] = []
    seen_dois: Set[str] = set()
    total_fetched = 0

    # Konstanta retry
    MAX_TIMEOUT_RETRIES = 5
    MAX_HTTP_RETRIES = 4

    for batch_idx, batch in enumerate(issn_batches):
        print(f"    Batch ISSN {batch_idx + 1}/{len(issn_batches)} ({len(batch)} ISSN)")

        # Gunakan abstract.search di filter, sama seperti openalex_fetch.py
        params = {
            "filter": (
                f"primary_location.source.issn:{'|'.join(batch)},"
                f"from_publication_date:{year_from}-01-01,"
                f"to_publication_date:{year_to}-12-31,"
                f"has_doi:true,"
                f"has_abstract:true"
                f"{lang_filter}"
                f",abstract.search:{search_query}"
            ),
            "per_page": per_page,
        }
        params.update(extra_params)

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

                print(f"      Page {page}: {len(results)} hasil, total: {batch_fetched}")
                if max_results > 0 and total_fetched >= max_results:
                    break

                if cursor:
                    time.sleep(delay)

            except requests.exceptions.Timeout:
                timeout_retries += 1
                if timeout_retries > MAX_TIMEOUT_RETRIES:
                    print(f"      Timeout page {page} - {MAX_TIMEOUT_RETRIES}x retry gagal, skip.")
                    break
                backoff = delay * (2 ** (timeout_retries - 1))
                print(f"      Timeout page {page} (retry {timeout_retries}/{MAX_TIMEOUT_RETRIES}), tunggu {backoff}s...")
                time.sleep(backoff)
                page -= 1
                continue
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response is not None else 0
                if status_code in (429, 503):
                    http_retries += 1
                    if http_retries > MAX_HTTP_RETRIES:
                        print(f"      HTTP {status_code} page {page} - {MAX_HTTP_RETRIES}x retry gagal, skip.")
                        break
                    backoff = delay * (2 ** http_retries)
                    retry_after = e.response.headers.get("Retry-After") if e.response else None
                    if retry_after:
                        try:
                            backoff = float(retry_after)
                        except ValueError:
                            pass
                    print(f"      HTTP {status_code} page {page} (retry {http_retries}/{MAX_HTTP_RETRIES}), tunggu {backoff}s...")
                    time.sleep(backoff)
                    page -= 1
                    continue
                print(f"      HTTP Error: {e}")
                if e.response is not None:
                    print(f"      Response: {e.response.text[:500]}")
                break
            except Exception as e:
                print(f"      Error: {e}")
                break

        print(f"    Batch {batch_idx + 1} selesai -> {batch_fetched} artikel")
        if max_results > 0 and total_fetched >= max_results:
            break
        if batch_idx < len(issn_batches) - 1:
            time.sleep(delay)

    return all_articles, total_fetched


# =============================================================================
# Entry point
# =============================================================================

def run(issn_file: str | None = None) -> int:
    """Entry point step 02."""
    log = setup_logging()
    cfg = get_config()

    api_key, mailto = load_openalex_credentials()

    if issn_file:
        issn_list = load_lines(issn_file)
        log.info(f"Memuat ISSN dari file: {issn_file} ({len(issn_list)} ISSN)")
    elif cfg.get("issn_electronic"):
        issn_list = list(cfg["issn_electronic"])
        log.info(f"Memuat ISSN dari config.yaml ({len(issn_list)} ISSN)")
    else:
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

    print_header("Step 02: Fetch Artikel dari OpenAlex — Pencarian di ABSTRACT")
    print(f"  ISSN count       : {len(issn_list)}")
    print(f"  Year range       : {year_from} - {year_to}")
    print(f"  Language         : {language if language else '(semua)'}")
    print(f"  Output file      : {output_path}")
    print(f"  Max results/group: {max_results if max_results > 0 else 'tanpa batas'}")
    print(f"  API key          : {'Yes (polite pool)' if api_key else 'No'}")
    print(f"  Mailto           : {mailto or 'No'}")
    print(f"  Search mode      : abstract.search")
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
            api_key=api_key,
            mailto=mailto,
        )
        grouped_results[group_name] = articles
        group_counts[group_name] = count
        print(f"  <<< Kelompok '{group_name}' selesai -> {count} artikel ditemukan.")
        time.sleep(delay)

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