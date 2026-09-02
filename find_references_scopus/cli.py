"""CLI terpadu untuk pipeline find_references_scopus.

Penggunaan:
    # Via module Python
    python -m find_references_scopus <command> [options]
    python -m find_references_scopus --help

    # Via entry point (jika sudah pip install)
    find-refs <command> [options]

Daftar command (urutan pipeline):
    01. get-issn              Ekstrak ISSN electronic dari SCImago       [MANUAL]
    02. fetch                 Fetch artikel dari OpenAlex API            [AUTO]
    03. filter                Filter artikel berdasarkan keyword         [AUTO]
    04. deduplicate           Deduplikasi antar group                    [AUTO]
    05. remove-excluded       Hapus DOI yang ada di daftar exclude       [MANUAL]
    06. distribution          Tampilkan distribusi artikel per kategori  [AUTO]
    07. merge-journal         Tambah info quartile & open_access         [AUTO]
    08. extract-claims        Ekstrak kalimat berisi DOI dari Markdown   [MANUAL]
    09. extract-references    Format artikel jadi Markdown ringkas       [AUTO]
    10. select-articles       Pilih subset artikel berdasar DOI          [MANUAL]
    11. convert-bib           Konversi JSON ke BibTeX                    [AUTO]

Legend:
    [AUTO]   = Bisa dijalankan otomatis, tidak butuh keputusan user
    [MANUAL] = Butuh input/keputusan user sebelum/sesudah dijalankan

Command utilitas (preprocessing SCImago):
    csv-to-json               Konversi SCImago CSV -> JSON
    check-issn                Inspeksi kelengkapan ISSN
    delete-no-issn            Hapus jurnal tanpa ISSN electronic
    split-subject             Pecah JSON per subject area

Command khusus:
    list                      Tampilkan daftar command tersedia
    guide                     Tampilkan panduan tahap-tahap pipeline + checkpoint manual
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from .pipeline import STEPS, get_step_map
from .journal_lists import JOURNAL_LISTS_STEPS


# =============================================================================
# Daftar command (gabungan pipeline + journal_lists)
# =============================================================================

def build_all_steps() -> list[tuple[str, Any]]:
    """Gabungkan registry pipeline + journal_lists untuk help."""
    return list(STEPS) + list(JOURNAL_LISTS_STEPS)


# =============================================================================
# Tag AUTO/MANUAL per step
# =============================================================================
# M13: Sebelumnya hard-coded dict terpisah dari registry. Kalau step baru
# ditambah ke STEPS tapi lupa tambah ke MANUAL_AUTO, tampil [?] di `find-refs list`.
# Fix: ambil dari attribute `MANUAL_OR_AUTO` di module step (default "AUTO").

def _get_step_tag(mod: Any) -> str:
    """Ambil tag AUTO/MANUAL dari module step. Default AUTO kalau tidak diset."""
    return getattr(mod, "MANUAL_OR_AUTO", "AUTO")


def cmd_list() -> int:
    """Tampilkan daftar semua command tersedia dengan tag AUTO/MANUAL."""
    print("Pipeline commands (urutan eksekusi standar):\n")
    print(f"  {'#':>3}  {'Command':<22} {'Type':<8} Description")
    print("  " + "-" * 80)
    for idx, (cmd, mod) in enumerate(STEPS, 1):
        tag = _get_step_tag(mod)
        desc = getattr(mod, "DESCRIPTION", "")
        print(f"  {idx:>3}. {cmd:<22} [{tag}]  {desc}")

    print("\nUtility commands (preprocessing SCImago):\n")
    for cmd, mod in JOURNAL_LISTS_STEPS:
        desc = getattr(mod, "DESCRIPTION", "")
        print(f"        {cmd:<22} {desc}")

    print("\nSpecial commands:\n")
    print(f"        {'list':<22} Tampilkan daftar command tersedia")
    print(f"        {'guide':<22} Tampilkan panduan tahap-tahap pipeline")
    return 0


# =============================================================================
# Subcommand khusus: guide (panduan tahapan, BUKAN pipeline runner)
# =============================================================================

def cmd_guide() -> int:
    """Tampilkan panduan tahap-tahap pipeline dengan checkpoint manual.

    BUKAN menjalankan pipeline — hanya menjelaskan urutan dan keputusan
    manual yang perlu diambil user di setiap tahap.
    """
    print("=" * 78)
    print("  PANDUAN PIPELINE — Tahap demi Tahap")
    print("=" * 78)
    print()
    print("Pipeline ini TIDAK otomatis end-to-end. Setiap tahap butuh keputusan")
    print("manual dari Anda. Jalankan satu per satu command di bawah ini.")
    print()
    print("Lihat README.md untuk panduan lengkap + kumpulan prompt AI untuk")
    print("membantu pembuatan artikel jurnal dari awal sampai akhir.")
    print()

    # Tahap 0: Preprocess SCImago
    print("-" * 78)
    print("  TAHAP 0 — Persiapan data SCImago (sekali saja, otomatis)")
    print("-" * 78)
    print("  Jalankan:  find-refs csv-to-json")
    print("             find-refs delete-no-issn")
    print("             find-refs split-subject   (opsional)")
    print("  Output   : data/scimagojr_2025.json + scimagojr_2025_ok.json")
    print()

    # Tahap 1: Pilih ISSN
    print("-" * 78)
    print("  TAHAP 1 — Pilih ISSN berdasarkan quartile  [MANUAL]")
    print("-" * 78)
    print("  Keputusan : quartile mana yang dipakai? (Q1? Q1+Q2? semua?)")
    print("  Jalankan  : find-refs get-issn -q Q1,Q2")
    print("  Output    : data/01_issn_list.txt")
    print()

    # Tahap 2: Fetch + Filter + Dedup
    print("-" * 78)
    print("  TAHAP 2 — Fetch artikel OpenAlex + filter + deduplikasi")
    print("-" * 78)
    print("  Jalankan  : find-refs fetch")
    print("              find-refs filter")
    print("              find-refs deduplicate")
    print("  Output    : data/04_deduplicated.json")
    print("  Catatan   : fetch bisa lama (menit–jam tergantung ISSN & search_groups)")
    print()

    # Tahap 3: Review manual
    print("-" * 78)
    print("  TAHAP 3 — REVIEW MANUAL: tentukan DOI exclude  [MANUAL]")
    print("-" * 78)
    print("  Lakukan  : buka data/04_deduplicated.json, baca abstrak tiap artikel,")
    print("             identifikasi DOI yang tidak relevan meski match keyword")
    print("  Tulis ke : data/excluded_dois.txt (satu DOI per baris)")
    print("             (boleh kosong kalau tidak ada yang di-exclude)")
    print()

    # Tahap 4: Remove excluded + distribution + merge journal
    print("-" * 78)
    print("  TAHAP 4 — Hapus exclude + statistik + merge info jurnal")
    print("-" * 78)
    print("  Jalankan  : find-refs remove-excluded")
    print("              find-refs distribution")
    print("              find-refs merge-journal")
    print("  Output    : data/07_with_journal_info.json (dataset final)")
    print()

    # Tahap 5: Tulis latar belakang dengan citation [DOI]
    print("-" * 78)
    print("  TAHAP 5 — TULIS LATAR BELAKANG  [MANUAL dengan bantuan AI]")
    print("-" * 78)
    print("  Lakukan  : gunakan AI (ChatGPT/Gemini/Claude) untuk tulis latar")
    print("             belakang. Berikan data/07_with_journal_info.json sebagai")
    print("             konteks. Minta AI menyisipkan [DOI] di setiap klaim.")
    print("  Lihat    : README.md bagian 'Prompt AI untuk Pembuatan Artikel'")
    print("             untuk kumpulan prompt siap pakai.")
    print("  Simpan ke: data/draft.md")
    print()

    # Tahap 6: Verifikasi klaim DOI
    print("-" * 78)
    print("  TAHAP 6 — Verifikasi klaim [DOI] di draf")
    print("-" * 78)
    print("  Jalankan  : find-refs extract-claims --input data/draft.md")
    print("  Output    : data/08_claims.json (kalimat + DOI yang di-claim)")
    print("  Lakukan  : review apakah setiap klaim benar-benar didukung artikel")
    print("             yang DOI-nya di-claim. Hapus/ubah klaim yang tidak cocok.")
    print()

    # Tahap 7: Subset artikel untuk cite
    print("-" * 78)
    print("  TAHAP 7 — PILIH DOI untuk cite di paper  [MANUAL opsional]")
    print("-" * 78)
    print("  Lakukan  : tentukan DOI mana yang akan Anda cite di paper akhir")
    print("  Edit     : config.yaml, isi bagian `selected_dois`")
    print("  Jalankan : find-refs select-articles")
    print("  Output   : data/10_selected.json")
    print()

    # Tahap 8: Export
    print("-" * 78)
    print("  TAHAP 8 — Export ke Markdown & BibTeX")
    print("-" * 78)
    print("  Jalankan : find-refs extract-references")
    print("             find-refs convert-bib")
    print("                 (atau: convert-bib --input data/10_selected.json")
    print("                  kalau mau pakai subset dari tahap 7)")
    print("  Output   : data/09_references.md + data/11_references.bib")
    print()

    # Penutup
    print("=" * 78)
    print("  TIPS")
    print("=" * 78)
    print("  - Setiap step individual bisa dijalankan ulang tanpa rusak data lain")
    print("  - Lihat `find-refs <command> --help` untuk opsi tiap command")
    print("  - Lihat README.md untuk:")
    print("      * Kumpulan prompt AI (brainstorming topik, latar belakang,")
    print("        metode, hasil, diskusi, kesimpulan, verifikasi klaim)")
    print("      * Prompt jika bingung mau topik apa")
    print("      * Prompt jika sudah punya code penelitian")
    print("      * Prompt untuk memilih jurnal yang relevan")
    print("=" * 78)
    return 0


# =============================================================================
# Main entry point
# =============================================================================

def main(argv: list[str] | None = None) -> int:
    """Entry point CLI utama.

    Args:
        argv: Argumen command line. None = pakai sys.argv.

    Returns:
        Exit code (0 sukses, 1 error).
    """
    parser = argparse.ArgumentParser(
        prog="find-refs",
        description="Pipeline fetch & filter artikel OpenAlex berbasis ISSN SCImago",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Contoh pemakaian:\n"
            "  find-refs list                       # daftar semua command\n"
            "  find-refs guide                      # panduan tahap-tahap\n"
            "  find-refs get-issn --quartile Q1,Q2  # step 01 manual\n"
            "  find-refs fetch                      # step 02 otomatis\n"
            "  find-refs extract-claims -i draft.md # step 08 manual\n"
            "\n"
            "Lihat README.md untuk kumpulan prompt AI pembuatan artikel jurnal."
        ),
    )
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Path ke config.yaml (default: config.yaml di root project)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Sub-command tersedia")

    # Register semua subcommand dari registry pipeline + journal_lists
    for cmd, mod in build_all_steps():
        mod.add_parser(subparsers)

    # Subcommand khusus
    list_parser = subparsers.add_parser("list", help="Tampilkan daftar command tersedia")
    list_parser.set_defaults(func=lambda args: cmd_list())

    guide_parser = subparsers.add_parser(
        "guide",
        help="Tampilkan panduan tahap-tahap pipeline + checkpoint manual",
    )
    guide_parser.set_defaults(func=lambda args: cmd_guide())

    args = parser.parse_args(argv)

    # Override config path jika --config diberikan
    if args.config:
        from pathlib import Path
        import yaml
        from .config import PROJECT_ROOT, set_config_override

        path = Path(args.config)
        if not path.is_file():
            print(f"Error: config file tidak ditemukan: {path}")
            return 1
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"Error: format YAML tidak valid: {e}")
            return 1
        if not isinstance(cfg, dict):
            print("Error: root konfigurasi harus mapping.")
            return 1

        # Resolve path relatif terhadap PROJECT_ROOT
        if "paths" in cfg and isinstance(cfg["paths"], dict):
            resolved = {}
            for k, v in cfg["paths"].items():
                resolved[k] = str(PROJECT_ROOT / v)
            cfg["paths"] = resolved

        # Set override via API yang thread-safe (H8)
        set_config_override(cfg)

    # Tidak ada subcommand -> tampilkan help
    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    # Jalankan fungsi subcommand
    try:
        result = args.func(args)
        if isinstance(result, bool):
            return 0 if result else 1
        return 0
    except KeyboardInterrupt:
        print("\nDihentikan oleh user.")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
