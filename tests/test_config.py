"""Tests for the config manager (multi-account API key management)."""

import os
import tempfile
from pathlib import Path

import pytest

# Force a temp config dir before importing
_tmp = tempfile.mkdtemp(prefix="findref-test-")
os.environ["FINDREF_CONFIG_DIR"] = _tmp


from find_references_scopus.config.manager import (  # noqa: E402
    Account,
    AccountNotFoundError,
    ConfigManager,
    ConfigNotFoundError,
    reset_manager,
    get_manager,
)


@pytest.fixture
def fresh_manager():
    """Each test gets a fresh config manager with no accounts."""
    reset_manager()
    mgr = ConfigManager(path=Path(_tmp) / "config.toml")
    yield mgr
    reset_manager()


def test_config_not_found(fresh_manager):
    """Should raise ConfigNotFoundError when no config exists."""
    with pytest.raises(ConfigNotFoundError):
        fresh_manager.load(create_if_missing=False)


def test_add_account_creates_config(fresh_manager):
    """Adding an account should auto-create the config file on save."""
    fresh_manager.load(create_if_missing=True)
    acc = Account(name="alice", label="Alice", openalex_mailto="alice@univ.ac.id")
    fresh_manager.add_account(acc)
    fresh_manager.save()

    assert fresh_manager.path.is_file()
    assert "alice" in [a.name for a in fresh_manager.list_accounts()]


def test_use_account(fresh_manager):
    """Switching accounts should update the current account."""
    fresh_manager.load(create_if_missing=True)
    fresh_manager.add_account(Account(name="alice", openalex_mailto="alice@univ.ac.id"))
    fresh_manager.add_account(Account(name="bob", openalex_mailto="bob@univ.ac.id"))

    fresh_manager.use_account("bob")
    assert fresh_manager.get_current_account().name == "bob"

    fresh_manager.use_account("alice")
    assert fresh_manager.get_current_account().name == "alice"


def test_use_unknown_account_raises(fresh_manager):
    """Should raise AccountNotFoundError for unknown account."""
    fresh_manager.load(create_if_missing=True)
    with pytest.raises(AccountNotFoundError):
        fresh_manager.use_account("nonexistent")


def test_remove_account(fresh_manager):
    """Removing an account should drop it from the registry."""
    fresh_manager.load(create_if_missing=True)
    fresh_manager.add_account(Account(name="alice"))
    assert fresh_manager.remove_account("alice") is True
    assert fresh_manager.remove_account("alice") is False  # Already removed


def test_remove_current_account_picks_next(fresh_manager):
    """Removing the current account should fall back to any remaining."""
    fresh_manager.load(create_if_missing=True)
    fresh_manager.add_account(Account(name="alice"))
    fresh_manager.add_account(Account(name="bob"))
    fresh_manager.use_account("alice")

    fresh_manager.remove_account("alice")
    assert fresh_manager.get_current_account().name == "bob"


def test_effective_credentials_uses_env(fresh_manager, monkeypatch):
    """FINDREF_OPENALEX_MAILTO should override the account mailto."""
    fresh_manager.load(create_if_missing=True)
    fresh_manager.add_account(Account(name="alice", openalex_mailto="config@univ.ac.id"))
    fresh_manager.use_account("alice")

    monkeypatch.setenv("FINDREF_OPENALEX_MAILTO", "env@univ.ac.id")
    creds = fresh_manager.effective_credentials()
    assert creds["openalex_mailto"] == "env@univ.ac.id"


def test_effective_credentials_falls_back_to_account(fresh_manager, monkeypatch):
    """Account mailto should be used if the env var is not set."""
    fresh_manager.load(create_if_missing=True)
    fresh_manager.add_account(Account(name="alice", openalex_mailto="config@univ.ac.id"))
    fresh_manager.use_account("alice")

    monkeypatch.delenv("FINDREF_OPENALEX_MAILTO", raising=False)
    creds = fresh_manager.effective_credentials()
    assert creds["openalex_mailto"] == "config@univ.ac.id"
    assert set(creds) == {"openalex_mailto"}  # OpenAlex only: no Scopus/Crossref/S2 keys


def test_legacy_config_keys_are_ignored(fresh_manager):
    """Old configs with Scopus/Crossref/S2 keys must still load (keys are dropped)."""
    fresh_manager.path.parent.mkdir(parents=True, exist_ok=True)
    fresh_manager.path.write_text(
        '[accounts.old]\n'
        'label = "Old"\n'
        'scopus_api_key = "secret"\n'
        'crossref_mailto = "x@y.z"\n'
        'semantic_scholar_api_key = "s2"\n'
        'openalex_mailto = "old@univ.ac.id"\n'
        '[current]\naccount = "old"\n',
        encoding="utf-8",
    )
    fresh_manager.load()
    acc = fresh_manager.get_current_account()
    assert acc.openalex_mailto == "old@univ.ac.id"
    assert not hasattr(acc, "scopus_api_key")
    assert "scopus_api_key" not in acc.to_dict()


def test_update_defaults(fresh_manager):
    """Should update defaults and persist them."""
    fresh_manager.load(create_if_missing=True)
    fresh_manager.update_defaults(year_from=2020, year_to=2025)
    fresh_manager.save()

    # Reload and check
    reset_manager()
    mgr2 = ConfigManager(path=Path(_tmp) / "config.toml")
    mgr2.load()
    assert mgr2.get_defaults().year_from == 2020
    assert mgr2.get_defaults().year_to == 2025


def test_account_to_dict_roundtrip():
    """Account serialization should roundtrip cleanly."""
    acc = Account(
        name="alice",
        label="Alice",
        openalex_mailto="alice@example.com",
    )
    d = acc.to_dict()
    acc2 = Account.from_dict("alice", d)
    assert acc2.label == acc.label
    assert acc2.openalex_mailto == acc.openalex_mailto
