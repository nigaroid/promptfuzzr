"""Tests for storage/paths.py — the single source of truth for where
promptfuzzr's SQLite database lives. See requirements this module
implements: always ~/.promptfuzzr/db/, never configurable via YAML,
Path.home()-based (platform-independent), directory auto-created.

Every test here uses the PROMPTFUZZR_DB_DIR env var override (the one
sanctioned test hook — see paths.py's own docstring) so nothing in this
file ever touches a real user's actual ~/.promptfuzzr directory.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Belt-and-braces: even though every test below sets its own
    override explicitly, make sure no leftover PROMPTFUZZR_DB_DIR from
    the surrounding environment (e.g. a previous test run, or a
    developer's shell) can leak into a test that doesn't expect it.
    """
    monkeypatch.delenv("PROMPTFUZZR_DB_DIR", raising=False)
    yield


def test_promptfuzzr_home_and_db_dir_are_under_path_home():
    from promptfuzzr.storage.paths import DB_DIR, PROMPTFUZZR_HOME

    assert PROMPTFUZZR_HOME == Path.home() / ".promptfuzzr"
    assert DB_DIR == Path.home() / ".promptfuzzr" / "db"


def test_get_db_path_default_name_and_location(monkeypatch, tmp_path):
    from promptfuzzr.storage.paths import get_db_path

    monkeypatch.setenv("PROMPTFUZZR_DB_DIR", str(tmp_path))
    p = get_db_path()

    assert p == tmp_path / "promptfuzzr.db"
    # Requirement: the directory is created automatically when required.
    assert p.parent.exists()
    assert p.parent.is_dir()


def test_get_db_path_custom_name(monkeypatch, tmp_path):
    from promptfuzzr.storage.paths import get_db_path

    monkeypatch.setenv("PROMPTFUZZR_DB_DIR", str(tmp_path))
    p = get_db_path("dvaa.db")

    assert p.name == "dvaa.db"
    assert p.parent == tmp_path


def test_get_db_path_creates_directory_if_missing(monkeypatch, tmp_path):
    from promptfuzzr.storage.paths import get_db_path

    target_dir = tmp_path / "does" / "not" / "exist" / "yet"
    assert not target_dir.exists()

    monkeypatch.setenv("PROMPTFUZZR_DB_DIR", str(target_dir))
    get_db_path()

    assert target_dir.exists() and target_dir.is_dir()


def test_get_db_path_without_override_resolves_under_real_home(monkeypatch):
    """With no override set, get_db_path() must resolve under the REAL
    ~/.promptfuzzr/db/ — this is the "no repo-relative fallback"
    requirement. We don't actually let it create that real directory
    (the assertion is purely path-equality, not existence), so this
    test can't pollute a real user's home directory.
    """
    from promptfuzzr.storage.paths import DB_DIR, get_db_path

    monkeypatch.delenv("PROMPTFUZZR_DB_DIR", raising=False)
    # Patch mkdir to a no-op so this test doesn't actually create
    # anything on the real filesystem, while still exercising the real
    # path-construction logic.
    monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: None)

    p = get_db_path()
    assert p == DB_DIR / "promptfuzzr.db"
    # The real assertion for the "no repo-relative fallback" requirement:
    # the returned path must be an absolute path under the home
    # directory, never a bare filename that would resolve relative to
    # whatever the current working directory happens to be.
    assert str(p) != "promptfuzzr.db"
    assert str(p).startswith(str(Path.home()))


def test_override_reverts_when_env_var_unset(monkeypatch, tmp_path):
    """The override is read at call time, not import time -- setting
    and then unsetting PROMPTFUZZR_DB_DIR must actually change behavior
    on the next call, not get cached.
    """
    from promptfuzzr.storage.paths import DB_DIR, get_db_path

    monkeypatch.setenv("PROMPTFUZZR_DB_DIR", str(tmp_path))
    overridden = get_db_path("x.db")
    assert overridden.parent == tmp_path

    monkeypatch.delenv("PROMPTFUZZR_DB_DIR", raising=False)
    monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: None)
    reverted = get_db_path("x.db")
    assert reverted.parent == DB_DIR


def test_init_db_uses_get_db_path_by_default(monkeypatch, tmp_path):
    """storage/db.py::init_db() must default to the centralized path,
    not a hardcoded or repo-relative one, when called with no argument
    — this is what every real call site (orchestrator/engine.py,
    cli.py) relies on.
    """
    from promptfuzzr.storage.db import init_db

    monkeypatch.setenv("PROMPTFUZZR_DB_DIR", str(tmp_path))
    conn = init_db()
    conn.close()

    assert (tmp_path / "promptfuzzr.db").exists()


def test_init_db_explicit_path_still_works_for_test_fixtures(tmp_path):
    """Explicit paths remain supported — this is the sanctioned
    test-fixture exception, used throughout scripts/verify_phases.py
    and elsewhere for isolated one-off connections that don't need to
    go through get_db_path() at all.
    """
    from promptfuzzr.storage.db import init_db

    explicit = tmp_path / "explicit.db"
    conn = init_db(explicit)
    conn.close()

    assert explicit.exists()


def test_run_config_has_no_db_path_field():
    """Requirement: db_path must be removed from the user configuration
    entirely, not just ignored.
    """
    from promptfuzzr.config import RunConfig

    field_names = {f.name for f in __import__("dataclasses").fields(RunConfig)}
    assert "db_path" not in field_names


def test_from_yaml_warns_on_legacy_db_path_key(tmp_path):
    """A config file left over from before this change (with a stray
    db_path: key) must not fail silently — from_yaml() should warn so
    the mismatch between what's in the file and what actually happens
    isn't a surprise.
    """
    from promptfuzzr.config import RunConfig

    legacy_config = tmp_path / "legacy.yaml"
    legacy_config.write_text(
        "target_id: lab_agent\n"
        "corpus_dir: .\n"
        "db_path: some/old/path.db\n"
    )

    with pytest.warns(UserWarning, match="db_path"):
        rc = RunConfig.from_yaml(legacy_config)

    assert not hasattr(rc, "db_path")


def test_from_yaml_without_db_path_key_is_silent(tmp_path):
    """The normal case (no db_path key at all) must NOT warn — only a
    legacy leftover key should trigger the warning.
    """
    import warnings

    from promptfuzzr.config import RunConfig

    clean_config = tmp_path / "clean.yaml"
    clean_config.write_text("target_id: lab_agent\ncorpus_dir: .\n")

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning becomes a test failure
        RunConfig.from_yaml(clean_config)
