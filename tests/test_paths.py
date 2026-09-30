"""Tests for path resolution + auto-naming helpers."""

import os
import tempfile
from pathlib import Path

import pytest

# Force a temp config dir
_tmp = tempfile.mkdtemp(prefix="findref-paths-test-")
os.environ["FINDREF_CONFIG_DIR"] = _tmp

from find_references_scopus.utils.paths import (  # noqa: E402
    auto_name,
    is_auto_name_enabled,
    resolve_output_dir,
    resolve_output_path,
    slugify,
    timestamp,
)


# ---------------------------------------------------------------------- #
# slugify
# ---------------------------------------------------------------------- #

def test_slugify_basic():
    assert slugify("Deep Learning for Finance") == "deep-learning-for-finance"


def test_slugify_special_chars():
    assert slugify("LSTM & Bitcoin price!") == "lstm-bitcoin-price"


def test_slugify_empty():
    assert slugify("") == "search"


def test_slugify_truncates():
    long = "a" * 100
    result = slugify(long, max_length=20)
    assert len(result) <= 20


def test_slugify_unicode():
    # NFKC normalized
    result = slugify("café münster")
    assert "caf" in result
    assert "m" in result


# ---------------------------------------------------------------------- #
# timestamp
# ---------------------------------------------------------------------- #

def test_timestamp_format():
    ts = timestamp()
    assert len(ts) == 15  # YYYYMMDD_HHMMSS
    assert ts[8] == "_"


# ---------------------------------------------------------------------- #
# auto_name
# ---------------------------------------------------------------------- #

def test_auto_name_search():
    name = auto_name("search", query="Deep Learning")
    assert name.startswith("search_deep-learning_")
    assert name.endswith(".json")


def test_auto_name_filter():
    name = auto_name("filter", input_path=Path("results.json"))
    assert name.startswith("filter_results_filtered_")
    assert name.endswith(".json")


def test_auto_name_export():
    name = auto_name("export", input_path=Path("data.json"), format="bibtex")
    assert name.startswith("export_data_bibtex_")
    assert name.endswith(".bib")


def test_auto_name_export_ris():
    name = auto_name("export", input_path=Path("papers.json"), format="ris")
    assert name.endswith(".ris")


def test_auto_name_explicit_extension():
    name = auto_name("search", query="x", extension="csv")
    assert name.endswith(".csv")


# ---------------------------------------------------------------------- #
# resolve_output_dir
# ---------------------------------------------------------------------- #

def test_resolve_output_dir_explicit(tmp_path):
    result = resolve_output_dir(explicit_dir=str(tmp_path))
    assert result == tmp_path
    assert tmp_path.is_dir()


def test_resolve_output_dir_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("FINDREF_OUTPUT_DIR", str(tmp_path))
    result = resolve_output_dir()
    assert result == tmp_path


def test_resolve_output_dir_config(tmp_path, monkeypatch):
    monkeypatch.delenv("FINDREF_OUTPUT_DIR", raising=False)
    result = resolve_output_dir(config_output_dir=str(tmp_path))
    assert result == tmp_path


def test_resolve_output_dir_fallback_cwd(monkeypatch, tmp_path):
    monkeypatch.delenv("FINDREF_OUTPUT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    result = resolve_output_dir()
    assert result == tmp_path


def test_resolve_output_dir_special_values(monkeypatch, tmp_path):
    monkeypatch.delenv("FINDREF_OUTPUT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)

    # "cwd" → CWD
    assert resolve_output_dir(explicit_dir="cwd") == tmp_path

    # "." → CWD
    assert resolve_output_dir(explicit_dir=".") == tmp_path


# ---------------------------------------------------------------------- #
# resolve_output_path
# ---------------------------------------------------------------------- #

def test_resolve_output_path_explicit_file(tmp_path):
    """--output path/to/file.json → use as-is."""
    result = resolve_output_path(
        explicit_output=str(tmp_path / "out.json"),
        kind="search",
    )
    assert result == tmp_path / "out.json"


def test_resolve_output_path_explicit_dir_with_auto_name(tmp_path):
    """--output path/ (trailing slash) + --auto-name → auto-name inside dir."""
    result = resolve_output_path(
        explicit_output=str(tmp_path) + "/",
        auto_name_enabled=True,
        kind="search",
        query="Deep Learning",
    )
    assert result.parent == tmp_path
    assert result.name.startswith("search_deep-learning_")
    assert result.name.endswith(".json")


def test_resolve_output_path_output_dir_with_auto_name(tmp_path):
    """--output-dir path + --auto-name → auto-name inside dir."""
    result = resolve_output_path(
        explicit_dir=str(tmp_path),
        auto_name_enabled=True,
        kind="search",
        query="test",
    )
    assert result.parent == tmp_path
    assert result.name.startswith("search_test_")
    assert result.name.endswith(".json")


def test_resolve_output_path_default_name_no_auto_name(tmp_path):
    """Without --auto-name, use simple default name like 'search_results.json'."""
    result = resolve_output_path(
        explicit_dir=str(tmp_path),
        auto_name_enabled=False,
        kind="search",
    )
    assert result.parent == tmp_path
    assert result.name == "search_results.json"


def test_resolve_output_path_env_var(tmp_path, monkeypatch):
    """FINDREF_OUTPUT_DIR should be respected when nothing else is set."""
    monkeypatch.setenv("FINDREF_OUTPUT_DIR", str(tmp_path))
    result = resolve_output_path(
        auto_name_enabled=False,
        kind="search",
    )
    assert result.parent == tmp_path
    assert result.name == "search_results.json"


# ---------------------------------------------------------------------- #
# is_auto_name_enabled
# ---------------------------------------------------------------------- #

def test_auto_name_enabled_cli_flag():
    assert is_auto_name_enabled(cli_flag=True) is True
    assert is_auto_name_enabled(cli_flag=False) is False


def test_auto_name_enabled_env_var(monkeypatch):
    monkeypatch.setenv("FINDREF_AUTO_NAME", "true")
    assert is_auto_name_enabled(cli_flag=None) is True

    monkeypatch.setenv("FINDREF_AUTO_NAME", "false")
    assert is_auto_name_enabled(cli_flag=None) is False


def test_auto_name_enabled_config_default(monkeypatch):
    monkeypatch.delenv("FINDREF_AUTO_NAME", raising=False)
    assert is_auto_name_enabled(cli_flag=None, config_value=True) is True
    assert is_auto_name_enabled(cli_flag=None, config_value=False) is False


def test_auto_name_enabled_cli_overrides_env(monkeypatch):
    monkeypatch.setenv("FINDREF_AUTO_NAME", "true")
    assert is_auto_name_enabled(cli_flag=False) is False
