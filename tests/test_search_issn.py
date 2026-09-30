"""End-to-end CLI tests for `findref search`, focused on the ISSN-restriction logic
and on --json purity (both were broken before this revision).
"""

import json

import pytest
from typer.testing import CliRunner

import find_references_scopus.api.openalex as oa
from find_references_scopus.cli import app
from find_references_scopus.core.models import Paper

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_dirs(tmp_path, monkeypatch):
    """Never touch the real user config/cache/data/logs while testing."""
    monkeypatch.setenv("FINDREF_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("FINDREF_LOGS_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("FINDREF_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FINDREF_DATA_DIR", str(tmp_path / "data"))
    yield


@pytest.fixture
def fake_scimago(tmp_path, monkeypatch):
    """A tiny SCImago file with one journal having >100... well, a controllable subject area."""
    import json as _json

    data = [
        {"journal": "CS Journal", "issn_electronic": "1111-1111", "quartile": "Q1", "subject_area": "Computer Science"},
        {"journal": "Med Journal", "issn_electronic": "2222-2222", "quartile": "Q1", "subject_area": "Medicine"},
    ]
    p = tmp_path / "scimago.json"
    p.write_text(_json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("FINDREF_DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "scimagojr_2025.json").write_text(_json.dumps(data), encoding="utf-8")
    from find_references_scopus.core import scimago

    scimago.clear_cache()
    yield p
    scimago.clear_cache()


def _install_fake_openalex(monkeypatch, papers, expect_issn_filter=None, expect_accept=None):
    """Patch OpenAlexClient.search to return a fixed list, and record how it was called."""
    calls = {}

    def fake_search(self, query, **kwargs):
        calls["kwargs"] = kwargs
        self.last_search_stats = {"scanned": len(papers), "matched": len(papers), "scan_capped": False}
        accept = kwargs.get("accept")
        if accept is not None:
            return [p for p in papers if accept(p)]
        return papers

    monkeypatch.setattr(oa.OpenAlexClient, "search", fake_search)
    return calls


def test_json_output_is_pure_json(monkeypatch):
    """Regression: --json used to leak Rich console text into stdout."""
    papers = [Paper(doi="10.1/x", title="T", authors=["A B"], year=2024, journal="J")]
    _install_fake_openalex(monkeypatch, papers)

    result = runner.invoke(app, ["search", "test query", "--json", "--no-issn-filter"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)  # must not raise
    assert data["count"] == 1
    assert data["issn_search"]["mode"] == "none"


def test_issn_flag_rejects_invalid_issn():
    result = runner.invoke(app, ["search", "test", "--issn", "not-an-issn"])
    assert result.exit_code != 0


def test_issn_flag_uses_server_side_filter(monkeypatch):
    papers = [Paper(doi="10.1/x", title="T", issns=["1111-1111"])]
    calls = _install_fake_openalex(monkeypatch, papers)

    result = runner.invoke(app, ["search", "test", "--issn", "1111-1111,2222-2222", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["issn_search"]["mode"] == "server"
    assert data["issn_search"]["issn_count"] == 2
    assert set(calls["kwargs"]["issn_filter"]) == {"1111-1111", "2222-2222"}
    assert "accept" not in calls["kwargs"] or calls["kwargs"]["accept"] is None


def test_no_issn_filter_searches_everything(monkeypatch):
    papers = [Paper(doi="10.1/x", title="T")]
    calls = _install_fake_openalex(monkeypatch, papers)

    result = runner.invoke(app, ["search", "test", "--no-issn-filter", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["issn_search"]["mode"] == "none"
    assert not calls["kwargs"].get("issn_filter")


def test_subject_area_filter_switches_to_scan_mode_when_over_100_issns(monkeypatch):
    """A SCImago subject area with many journals must not be silently truncated to 100 ISSNs."""
    import find_references_scopus.core.issn_filter as issn_filter_mod

    # Force "many ISSNs" without needing a 32k-journal fixture file.
    def fake_build(self, path):
        self.issns = [f"{1000+i:04d}-{i:04d}" for i in range(150)]
        self.stats = {"total_journals": 150, "unmatched_subject_areas": []}
        return self

    monkeypatch.setattr(issn_filter_mod.IssnFilter, "build", fake_build)

    papers = [Paper(doi="10.1/x", title="T", issns=["1000-0000"])]
    calls = _install_fake_openalex(monkeypatch, papers)

    result = runner.invoke(app, ["search", "test", "--subject-areas", "Anything", "--json"])
    assert result.exit_code == 0, result.stdout
    data = json.loads(result.stdout)
    assert data["issn_search"]["mode"] == "scan"
    assert data["issn_search"]["issn_count"] == 150
    assert calls["kwargs"].get("accept") is not None
    assert "issn_filter" not in calls["kwargs"] or not calls["kwargs"]["issn_filter"]


def test_empty_issn_filter_result_errors_instead_of_silently_returning_nothing(monkeypatch, fake_scimago):
    _install_fake_openalex(monkeypatch, [])
    result = runner.invoke(
        app,
        ["search", "test", "--subject-areas", "TotallyMadeUpAreaXYZ123", "--quartile", "Q1"],
    )
    assert result.exit_code != 0


def test_issn_override_ignores_subject_area_and_warns(monkeypatch, fake_scimago):
    papers = [Paper(doi="10.1/x", title="T", issns=["1111-1111"])]
    _install_fake_openalex(monkeypatch, papers)

    result = runner.invoke(
        app,
        ["search", "test", "--issn", "1111-1111", "--subject-areas", "Medicine", "--json"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["issn_search"]["mode"] == "server"
    assert data["issn_filter"] is None  # subject-area filter was not built; --issn wins
