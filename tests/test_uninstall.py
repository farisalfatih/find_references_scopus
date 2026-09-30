"""Tests for find_references_scopus.commands.uninstall."""

import os
import time
from pathlib import Path

from find_references_scopus.commands.uninstall import (
    INSTALL_MARKER,
    Layout,
    detect_layout,
    execute,
    is_safe_delete_target,
    plan_uninstall,
    strip_path_block,
)


# ---------------------------------------------------------------------- #
# strip_path_block
# ---------------------------------------------------------------------- #

def test_strip_path_block_removes_marker_and_export_line():
    text = 'line1\nline2\n\n# findref\nexport PATH="$HOME/.local/bin:$PATH"\nline3\n'
    new_text, removed = strip_path_block(text)
    assert removed is True
    assert "# findref" not in new_text
    assert "export PATH=" not in new_text
    assert new_text == "line1\nline2\nline3\n"


def test_strip_path_block_no_marker_is_noop():
    text = "line1\nline2\n"
    new_text, removed = strip_path_block(text)
    assert removed is False
    assert new_text == text


def test_strip_path_block_idempotent():
    text = 'a\n\n# findref\nexport PATH="x"\nb\n'
    once, _ = strip_path_block(text)
    twice, removed_again = strip_path_block(once)
    assert removed_again is False
    assert once == twice


def test_strip_path_block_only_drops_the_immediately_preceding_blank_line():
    """A single blank line right before the marker is dropped; content is otherwise untouched."""
    text = 'a\n\n\n# findref\nexport PATH="x"\nb\n'
    new_text, removed = strip_path_block(text)
    assert removed is True
    assert new_text == "a\n\nb\n"  # one of the two blank lines survives


def test_strip_path_block_keeps_unrelated_line_after_marker():
    """If the line after the marker isn't an export PATH line, it must be kept."""
    text = "a\n# findref\nsomething else\nb\n"
    new_text, removed = strip_path_block(text)
    assert removed is True
    assert "something else" in new_text
    assert new_text == "a\nsomething else\nb\n"


# ---------------------------------------------------------------------- #
# is_safe_delete_target
# ---------------------------------------------------------------------- #

def test_is_safe_delete_target_rejects_home():
    assert is_safe_delete_target(Path.home()) is False


def test_is_safe_delete_target_rejects_root():
    assert is_safe_delete_target(Path("/")) is False


def test_is_safe_delete_target_rejects_relative_path():
    assert is_safe_delete_target(Path("relative/path")) is False


def test_is_safe_delete_target_accepts_nested_app_folder():
    assert is_safe_delete_target(Path.home() / ".findref") is True


def test_is_safe_delete_target_rejects_ancestor_of_home():
    assert is_safe_delete_target(Path.home().parent) is False


# ---------------------------------------------------------------------- #
# detect_layout
# ---------------------------------------------------------------------- #

def _make_installer_layout(tmp_path):
    home = tmp_path / ".findref"
    venv = home / "venv"
    (venv).mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("")
    (home / "src").mkdir()
    (home / INSTALL_MARKER).write_text("")
    return home, venv


def test_detect_layout_installer(tmp_path):
    home, venv = _make_installer_layout(tmp_path)
    layout = detect_layout(prefix=venv)
    assert layout.kind == "installer"
    assert layout.home == home


def test_detect_layout_other_for_arbitrary_prefix(tmp_path):
    layout = detect_layout(prefix=tmp_path / "usr")
    assert layout.kind == "other"
    assert layout.home is None


def test_detect_layout_requires_pyvenv_cfg(tmp_path):
    """A folder merely named 'venv' without pyvenv.cfg is not treated as our venv."""
    home = tmp_path / ".findref"
    venv = home / "venv"
    venv.mkdir(parents=True)
    (home / "src").mkdir()
    layout = detect_layout(prefix=venv)
    assert layout.kind == "other"


# ---------------------------------------------------------------------- #
# plan_uninstall
# ---------------------------------------------------------------------- #

def test_plan_uninstall_other_layout_has_no_program_steps():
    steps = plan_uninstall(Layout("other"), purge=False)
    assert steps == []


def test_plan_uninstall_installer_layout_lists_program_dirs(tmp_path):
    home, venv = _make_installer_layout(tmp_path)
    layout = Layout("installer", home)
    steps = plan_uninstall(layout, purge=False, bin_dir=tmp_path / "bin")
    targets = {s.target for s in steps}
    assert str(venv) in targets
    assert str(home / "src") in targets
    assert str(home / INSTALL_MARKER) in targets
    assert all(s.deferred for s in steps if s.kind in ("dir", "file"))


def test_plan_uninstall_finds_launcher_symlinks(tmp_path):
    home, venv = _make_installer_layout(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (venv / "bin").mkdir()
    target = venv / "bin" / "findref"
    target.write_text("#!/bin/sh\n")
    (bin_dir / "findref").symlink_to(target)

    layout = Layout("installer", home)
    steps = plan_uninstall(layout, purge=False, bin_dir=bin_dir)
    launcher_steps = [s for s in steps if s.kind == "launcher"]
    assert len(launcher_steps) == 1
    assert launcher_steps[0].target == str(bin_dir / "findref")
    assert launcher_steps[0].deferred is False  # removed immediately, not by the helper


def test_plan_uninstall_purge_adds_data_folders(tmp_path, monkeypatch):
    monkeypatch.setenv("FINDREF_CONFIG_DIR", str(tmp_path / "custom-config"))
    home, venv = _make_installer_layout(tmp_path)
    layout = Layout("installer", home)
    steps_no_purge = plan_uninstall(layout, purge=False, bin_dir=tmp_path / "bin")
    steps_purge = plan_uninstall(layout, purge=True, bin_dir=tmp_path / "bin")
    assert len(steps_purge) > len(steps_no_purge)


# ---------------------------------------------------------------------- #
# execute (end-to-end with a throwaway HOME)
# ---------------------------------------------------------------------- #

def test_execute_removes_program_and_rc_line(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    (fake_home / ".local" / "bin").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home))

    findref_home = fake_home / ".findref"
    venv = findref_home / "venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("")
    (findref_home / "src").mkdir()
    (findref_home / INSTALL_MARKER).write_text("")

    bin_dir = fake_home / ".local" / "bin"
    for name in ("findref", "find-refs"):
        exe = venv / "bin" / name
        exe.write_text("#!/bin/sh\n")
        (bin_dir / name).symlink_to(exe)

    rc = fake_home / ".bashrc"
    rc.write_text('alias ll="ls -la"\n\n# findref\nexport PATH="$HOME/.local/bin:$PATH"\n')

    layout = Layout("installer", findref_home)
    steps = plan_uninstall(layout, purge=False, bin_dir=bin_dir)
    execute(steps, layout)

    # Immediate steps: launchers and rc line gone right away.
    assert not (bin_dir / "findref").exists()
    assert not (bin_dir / "find-refs").exists()
    assert "# findref" not in rc.read_text()
    assert 'alias ll="ls -la"' in rc.read_text()

    # Deferred steps: program folder removed shortly after by the background helper.
    for _ in range(20):
        if not findref_home.exists():
            break
        time.sleep(0.25)
    assert not findref_home.exists()

    assert all(s.status in ("done", "scheduled") for s in steps)


def test_execute_purge_removes_only_findref_files_in_custom_dir(tmp_path, monkeypatch):
    """A custom FINDREF_CONFIG_DIR shared with other apps must not be deleted wholesale."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    custom_config = tmp_path / "shared-config-dir"
    custom_config.mkdir()
    (custom_config / "config.toml").write_text("x")
    (custom_config / "unrelated-app.ini").write_text("keep me")
    monkeypatch.setenv("FINDREF_CONFIG_DIR", str(custom_config))
    monkeypatch.setenv("FINDREF_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FINDREF_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FINDREF_LOGS_DIR", str(tmp_path / "logs"))
    for env in ("FINDREF_DATA_DIR", "FINDREF_CACHE_DIR", "FINDREF_LOGS_DIR"):
        Path(os.environ[env]).mkdir(parents=True, exist_ok=True)

    layout = Layout("other")
    steps = plan_uninstall(layout, purge=True)
    execute(steps, layout)

    for _ in range(20):
        if not (custom_config / "config.toml").exists():
            break
        time.sleep(0.25)

    assert not (custom_config / "config.toml").exists()
    assert (custom_config / "unrelated-app.ini").exists(), "must not delete files findref didn't create"
