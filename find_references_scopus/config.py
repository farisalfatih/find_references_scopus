"""Loader konfigurasi terpusat.

Membaca file config.yaml dan menyediakan akses terstruktur ke semua
parameter pipeline. Setiap script pipeline mengimpor `get_config()`
untuk membaca konfigurasi — tidak ada lagi hard-coded value di kode.

H8 (thread-safety): Override config via CLI --config dipakai melalui
global _OVERRIDE_CONFIG. Untuk reset (mis. antar test), panggil
`reset_config_override()`.

Contoh pemakaian:
    from find_references_scopus.config import get_config
    cfg = get_config()
    year_from = cfg["year_from"]
    search_groups = cfg["search_groups"]
    output_path = cfg["paths"]["step_02_openalex_raw"]
"""

from __future__ import annotations

import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml


# Root project = parent directory dari package ini
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"

# Lock untuk thread-safety saat set/reset override (H8)
_OVERRIDE_LOCK = threading.Lock()


class ConfigError(Exception):
    """Error ketika konfigurasi tidak valid atau tidak ditemukan."""


@lru_cache(maxsize=1)
def get_config(config_path: str | None = None) -> Dict[str, Any]:
    """Muat konfigurasi dari file YAML.

    Args:
        config_path: Path absolut/relatif ke config.yaml. Jika None,
            akan memakai config.yaml di root project ATAU override yang
            diset via set_config_override() (untuk CLI --config).

    Returns:
        Dict berisi seluruh konfigurasi yang sudah di-resolve path-nya
        (path relatif diubah jadi absolut berbasis PROJECT_ROOT).

    Raises:
        ConfigError: jika file tidak ditemukan atau format tidak valid.
    """
    # Cek override global dulu (dipakai oleh CLI --config)
    # Tidak pakai globals().get() lagi — pakai variabel module-level yang eksplisit
    override = _OVERRIDE_CONFIG
    if override is not None and config_path is None:
        return override

    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.is_file():
        raise ConfigError(
            f"File konfigurasi tidak ditemukan: {path}\n"
            f"Pastikan config.yaml ada di root project atau tentukan path via --config."
        )

    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Format YAML tidak valid di {path}: {e}") from e

    if not isinstance(cfg, dict):
        raise ConfigError(f"Root konfigurasi harus berupa mapping, bukan {type(cfg).__name__}.")

    # Resolve semua path relatif menjadi absolut berbasis PROJECT_ROOT
    if "paths" in cfg and isinstance(cfg["paths"], dict):
        resolved: Dict[str, str] = {}
        for key, rel_path in cfg["paths"].items():
            resolved[key] = str(PROJECT_ROOT / rel_path)
        cfg["paths"] = resolved

    return cfg


def set_config_override(cfg: Dict[str, Any]) -> None:
    """Set override konfigurasi (dipakai oleh CLI --config).

    Thread-safe: pakai lock saat set. Cache LRU juga di-clear agar
    modul yang sudah panggil get_config() sebelumnya dapat config baru.

    Args:
        cfg: Dict konfigurasi yang sudah di-resolve path-nya.
    """
    global _OVERRIDE_CONFIG
    with _OVERRIDE_LOCK:
        _OVERRIDE_CONFIG = cfg
        # Clear cache agar get_config() baca ulang
        get_config.cache_clear()


def reset_config_override() -> None:
    """Reset override konfigurasi ke None (kembali ke file config.yaml default).

    Dipakai antar test untuk isolation.
    """
    global _OVERRIDE_CONFIG
    with _OVERRIDE_LOCK:
        _OVERRIDE_CONFIG = None
        get_config.cache_clear()


# Variabel module-level untuk override (H8)
# Dideklarasi SETELAH fungsi yang memakai nya agar tidak None saat get_config dipanggil
_OVERRIDE_CONFIG: Dict[str, Any] | None = None


def get_path(key: str, config_path: str | None = None) -> str:
    """Helper singkat untuk ambil satu path absolut dari konfigurasi.

    Args:
        key: Key di dalam mapping `paths` (mis. "step_02_openalex_raw").
        config_path: Path ke config.yaml (opsional).

    Returns:
        Path absolut sebagai string.

    Raises:
        ConfigError: jika key tidak ada di mapping `paths`.
    """
    cfg = get_config(config_path)
    paths = cfg.get("paths", {})
    if key not in paths:
        raise ConfigError(
            f"Key '{key}' tidak ditemukan di bagian `paths` config.yaml. "
            f"Key yang tersedia: {list(paths.keys())}"
        )
    return paths[key]


def ensure_parent_dir(file_path: str) -> None:
    """Pastikan direktori parent dari file_path sudah ada.

    Dipakai sebelum menulis file output agar tidak error FileNotFoundError.
    """
    parent = os.path.dirname(os.path.abspath(file_path))
    os.makedirs(parent, exist_ok=True)
