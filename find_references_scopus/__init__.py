"""Package find_references_scopus.

Pipeline untuk fetch, filter, deduplikasi, dan konversi artikel ilmiah
dari OpenAlex berdasarkan daftar ISSN SCImago.

Penggunaan utama via CLI:
    python -m find_references_scopus <step>
    find-refs <step>          # jika sudah di-install

Daftar step tersedia di modul find_references_scopus.pipeline.
"""

__version__ = "1.0.0"
