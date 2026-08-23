from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
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
    from promptfuzzr.storage.paths import DB_DIR, get_db_path

    monkeypatch.delenv("PROMPTFUZZR_DB_DIR", raising=False)
    monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: None)

    p = get_db_path()
    assert p == DB_DIR / "promptfuzzr.db"
    assert str(p) != "promptfuzzr.db"
    assert str(p).startswith(str(Path.home()))


def test_override_reverts_when_env_var_unset(monkeypatch, tmp_path):
    from promptfuzzr.storage.paths import DB_DIR, get_db_path

    monkeypatch.setenv("PROMPTFUZZR_DB_DIR", str(tmp_path))
    overridden = get_db_path("x.db")
    assert overridden.parent == tmp_path

    monkeypatch.delenv("PROMPTFUZZR_DB_DIR", raising=False)
    monkeypatch.setattr(Path, "mkdir", lambda self, **kwargs: None)
    reverted = get_db_path("x.db")
    assert reverted.parent == DB_DIR


def test_init_db_uses_get_db_path_by_default(monkeypatch, tmp_path):
    from promptfuzzr.storage.db import init_db

    monkeypatch.setenv("PROMPTFUZZR_DB_DIR", str(tmp_path))
    conn = init_db()
    conn.close()

    assert (tmp_path / "promptfuzzr.db").exists()


def test_init_db_explicit_path_still_works_for_test_fixtures(tmp_path):
    from promptfuzzr.storage.db import init_db

    explicit = tmp_path / "explicit.db"
    conn = init_db(explicit)
    conn.close()

    assert explicit.exists()


def test_run_config_has_no_db_path_field():
    from promptfuzzr.config import RunConfig

    field_names = {f.name for f in __import__("dataclasses").fields(RunConfig)}
    assert "db_path" not in field_names


def test_from_yaml_warns_on_legacy_db_path_key(tmp_path):
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
    import warnings

    from promptfuzzr.config import RunConfig

    clean_config = tmp_path / "clean.yaml"
    clean_config.write_text("target_id: lab_agent\ncorpus_dir: .\n")

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning becomes a test failure
        RunConfig.from_yaml(clean_config)
