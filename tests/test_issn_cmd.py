"""End-to-end CLI tests for `findref issn`."""

import json

import pytest
from typer.testing import CliRunner

from find_references_scopus.cli import app
from find_references_scopus.core import scimago

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("FINDREF_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("FINDREF_LOGS_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("FINDREF_CACHE_DIR", str(tmp_path / "cache"))
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("FINDREF_DATA_DIR", str(data_dir))

    data = [
        {
            "journal": "Dual ISSN Journal",
            "issn_electronic": "1111-1111",
            "issn_print": "2222-2222",
            "quartile": "Q1",
            "subject_area": "Computer Science",
        },
        {
            "journal": "Print Only Journal",
            "issn_print": "3333-3333",
            "quartile": "Q2",
            "subject_area": "Medicine",
        },
    ]
    (data_dir / "scimagojr_2025.json").write_text(json.dumps(data), encoding="utf-8")
    scimago.clear_cache()
    yield
    scimago.clear_cache()


def test_lookup_electronic_issn_json():
    result = runner.invoke(app, ["issn", "1111-1111", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["found"] == 1
    assert data["results"][0]["journal"] == "Dual ISSN Journal"
    assert data["results"][0]["quartile"] == "Q1"


def test_lookup_print_issn_of_dual_journal_json():
    """Regression: looking up the print ISSN of a journal that also has an e-ISSN."""
    result = runner.invoke(app, ["issn", "2222-2222", "--json"])
    data = json.loads(result.stdout)
    assert data["found"] == 1
    assert data["results"][0]["journal"] == "Dual ISSN Journal"


def test_lookup_print_only_journal_json():
    """Regression: a journal known to SCImago only by its print ISSN."""
    result = runner.invoke(app, ["issn", "3333-3333", "--json"])
    data = json.loads(result.stdout)
    assert data["found"] == 1
    assert data["results"][0]["journal"] == "Print Only Journal"
    assert data["results"][0]["quartile"] == "Q2"


def test_lookup_multiple_issns_mixed_found():
    result = runner.invoke(app, ["issn", "1111-1111", "9999-9999", "--json"])
    data = json.loads(result.stdout)
    assert data["count"] == 2
    assert data["found"] == 1
    by_issn = {r["issn"]: r for r in data["results"]}
    assert by_issn["1111-1111"]["found"] is True
    assert by_issn["9999-9999"]["found"] is False


def test_lookup_not_found_exits_nonzero_in_json_mode():
    result = runner.invoke(app, ["issn", "0000-0000", "--json"])
    assert result.exit_code != 0
    data = json.loads(result.stdout)
    assert data["found"] == 0


def test_lookup_rejects_invalid_issn_format():
    result = runner.invoke(app, ["issn", "not-an-issn"])
    assert result.exit_code != 0


def test_lookup_accepts_unhyphenated_issn():
    result = runner.invoke(app, ["issn", "11111111", "--json"])
    data = json.loads(result.stdout)
    assert data["found"] == 1
    assert data["results"][0]["issn"] == "1111-1111"


def test_human_output_is_not_json_but_succeeds():
    result = runner.invoke(app, ["issn", "1111-1111"])
    assert result.exit_code == 0
    assert "Dual ISSN Journal" in result.stdout
