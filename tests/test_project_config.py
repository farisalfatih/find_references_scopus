"""Tests for the project-local config loader."""

from find_references_scopus.config.project import (
    apply_project_overrides,
    find_project_config,
    load_project_config,
)
from find_references_scopus.config.manager import Defaults


def test_find_project_config_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert find_project_config() is None


def test_find_project_config_yaml(tmp_path, monkeypatch):
    cfg = tmp_path / ".findref.yaml"
    cfg.write_text("defaults:\n  output_dir: ./refs\n")
    monkeypatch.chdir(tmp_path)
    result = find_project_config()
    assert result == cfg


def test_find_project_config_yml(tmp_path, monkeypatch):
    cfg = tmp_path / ".findref.yml"
    cfg.write_text("defaults:\n  output_dir: ./refs\n")
    monkeypatch.chdir(tmp_path)
    result = find_project_config()
    assert result == cfg


def test_find_project_config_walks_up(tmp_path, monkeypatch):
    """Should walk up the directory tree to find the config."""
    cfg = tmp_path / ".findref.yaml"
    cfg.write_text("defaults:\n  year_from: 2020\n")

    sub = tmp_path / "subdir" / "deep"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)

    result = find_project_config()
    assert result == cfg


def test_load_project_config_basic(tmp_path):
    cfg = tmp_path / ".findref.yaml"
    cfg.write_text(
        "defaults:\n"
        "  output_dir: ./refs\n"
        "  auto_name: true\n"
        "  year_from: 2020\n"
    )
    result = load_project_config(cfg)
    assert "defaults" in result
    assert result["defaults"]["output_dir"] == "./refs"
    assert result["defaults"]["auto_name"] is True


def test_load_project_config_missing_returns_empty(tmp_path):
    result = load_project_config(tmp_path / "nonexistent.yaml")
    assert result == {}


def test_load_project_config_invalid_yaml_returns_empty(tmp_path):
    cfg = tmp_path / ".findref.yaml"
    cfg.write_text("{{invalid yaml::")
    result = load_project_config(cfg)
    assert result == {}


def test_apply_project_overrides():
    """Project config values should override user defaults."""
    user_defaults = Defaults()
    project_cfg = {
        "defaults": {
            "output_dir": "./refs",
            "auto_name": True,
            "year_from": 2020,
            "year_to": 2025,
            "openalex_mailto": "project@univ.edu",
            "openalex_mailto_pool": "a@x.edu,b@y.edu",
            "openalex_auto_rotate": True,
        }
    }
    result = apply_project_overrides(user_defaults, project_cfg)
    assert result.output_dir == "./refs"
    assert result.auto_name is True
    assert result.year_from == 2020
    assert result.year_to == 2025
    assert result.openalex_mailto == "project@univ.edu"
    assert result.openalex_mailto_pool == "a@x.edu,b@y.edu"
    assert result.openalex_auto_rotate is True
    # Untouched fields keep their defaults
    assert result.per_page == user_defaults.per_page


def test_apply_project_overrides_scimago_top_level():
    """Top-level scimago_path should be applied as convenience."""
    user_defaults = Defaults()
    project_cfg = {"scimago_path": "./data/scimago.json"}
    result = apply_project_overrides(user_defaults, project_cfg)
    assert result.scimago_path == "./data/scimago.json"


def test_apply_project_overrides_empty_config():
    """Empty project config should not change anything."""
    user_defaults = Defaults()
    original_output_dir = user_defaults.output_dir
    result = apply_project_overrides(user_defaults, {})
    assert result.output_dir == original_output_dir


def test_apply_project_overrides_does_not_mutate_input():
    """Should return a new Defaults instance, not mutate the input."""
    user_defaults = Defaults()
    original_output_dir = user_defaults.output_dir
    project_cfg = {"defaults": {"output_dir": "./changed"}}
    _ = apply_project_overrides(user_defaults, project_cfg)
    # Original should be unchanged
    assert user_defaults.output_dir == original_output_dir


def test_apply_project_overrides_ignores_invalid_types():
    """Should silently skip fields that can't be cast."""
    user_defaults = Defaults()
    project_cfg = {"defaults": {"year_from": "not-a-number"}}
    result = apply_project_overrides(user_defaults, project_cfg)
    # Should keep the original value
    assert result.year_from == user_defaults.year_from


# ---------------------------------------------------------------------- #
# ISSN filter keys (project file)
# ---------------------------------------------------------------------- #

def test_apply_project_overrides_issn_keys():
    user_defaults = Defaults()
    project_cfg = {
        "defaults": {
            "use_issn_filter": True,
            "issn_subject_areas": ["Computer Science", "Mathematics"],
            "issn_quartiles": "Q1,Q2",
            "issn_include_unranked": False,
        }
    }
    result = apply_project_overrides(user_defaults, project_cfg)
    assert result.use_issn_filter is True
    assert result.issn_subject_areas == "Computer Science,Mathematics"
    assert result.issn_quartiles == "Q1,Q2"
    assert result.issn_include_unranked is False


def test_apply_project_overrides_issn_boolean_as_string():
    """YAML sometimes yields a plain string like 'false' instead of a real bool."""
    user_defaults = Defaults()
    project_cfg = {"defaults": {"use_issn_filter": "false"}}
    result = apply_project_overrides(user_defaults, project_cfg)
    assert result.use_issn_filter is False


def test_apply_project_overrides_csv_list_of_one():
    user_defaults = Defaults()
    project_cfg = {"defaults": {"issn_subject_areas": ["Medicine"]}}
    result = apply_project_overrides(user_defaults, project_cfg)
    assert result.issn_subject_areas == "Medicine"


# ---------------------------------------------------------------------- #
# Environment variable overrides
# ---------------------------------------------------------------------- #

def test_apply_env_overrides_sets_issn_filter(monkeypatch):
    from find_references_scopus.config.project import apply_env_overrides

    monkeypatch.setenv("FINDREF_USE_ISSN_FILTER", "true")
    monkeypatch.setenv("FINDREF_ISSN_SUBJECT_AREAS", "Physics,Chemistry")
    monkeypatch.setenv("FINDREF_ISSN_QUARTILES", "Q1")
    monkeypatch.setenv("FINDREF_ISSN_INCLUDE_UNRANKED", "false")

    result = apply_env_overrides(Defaults())
    assert result.use_issn_filter is True
    assert result.issn_subject_areas == "Physics,Chemistry"
    assert result.issn_quartiles == "Q1"
    assert result.issn_include_unranked is False


def test_apply_env_overrides_unset_vars_leave_config_untouched(monkeypatch):
    from find_references_scopus.config.project import apply_env_overrides

    for var in (
        "FINDREF_USE_ISSN_FILTER",
        "FINDREF_ISSN_SUBJECT_AREAS",
        "FINDREF_ISSN_QUARTILES",
        "FINDREF_ISSN_INCLUDE_UNRANKED",
    ):
        monkeypatch.delenv(var, raising=False)

    base = Defaults(use_issn_filter=True, issn_subject_areas="Biology")
    result = apply_env_overrides(base)
    assert result.use_issn_filter is True
    assert result.issn_subject_areas == "Biology"


def test_apply_env_overrides_does_not_mutate_input(monkeypatch):
    from find_references_scopus.config.project import apply_env_overrides

    monkeypatch.setenv("FINDREF_USE_ISSN_FILTER", "true")
    base = Defaults(use_issn_filter=False)
    apply_env_overrides(base)
    assert base.use_issn_filter is False


# ---------------------------------------------------------------------- #
# resolve_defaults (config < project file < env, in that priority order)
# ---------------------------------------------------------------------- #

def test_resolve_defaults_priority_order(tmp_path, monkeypatch):
    from find_references_scopus.config.project import resolve_defaults

    class FakeManager:
        def get_defaults(self):
            return Defaults(use_issn_filter=False, issn_quartiles="Q3")

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".findref.yaml").write_text(
        "defaults:\n  use_issn_filter: true\n  issn_quartiles: 'Q2'\n"
    )
    # Env var beats the project file.
    monkeypatch.setenv("FINDREF_ISSN_QUARTILES", "Q1")

    result = resolve_defaults(FakeManager())
    assert result.use_issn_filter is True  # from the project file (user config had it False)
    assert result.issn_quartiles == "Q1"  # env wins over both project file and user config
