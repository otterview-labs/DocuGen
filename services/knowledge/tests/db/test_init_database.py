from __future__ import annotations

import importlib

import pytest

from tests.helpers import clear_modules, configure_runtime_env


pytestmark = pytest.mark.unit


def _import_init_database_module(monkeypatch, tmp_path, **env_overrides):
    configure_runtime_env(monkeypatch, tmp_path, **env_overrides)
    clear_modules()
    return importlib.import_module("app.db.init_database")


def test_init_database_respects_disabled_switches(monkeypatch, tmp_path) -> None:
    init_database_module = _import_init_database_module(monkeypatch, tmp_path)

    calls = {"create_all": 0, "migrations": 0, "seed": 0, "session": 0}

    def _fake_create_all(*, bind=None) -> None:
        calls["create_all"] += 1

    def _fake_run_online_migrations():
        calls["migrations"] += 1
        return []

    class _DummySession:
        def __init__(self) -> None:
            calls["session"] += 1

        def close(self) -> None:
            return None

    def _fake_init_llm_config_data(_db) -> None:
        calls["seed"] += 1

    monkeypatch.setattr(init_database_module.Base.metadata, "create_all", _fake_create_all)
    monkeypatch.setattr(init_database_module, "run_online_migrations", _fake_run_online_migrations)
    monkeypatch.setattr(init_database_module, "SessionLocal", _DummySession)
    monkeypatch.setattr(init_database_module, "init_llm_config_data", _fake_init_llm_config_data)

    summary = init_database_module.init_database(
        create_tables=False,
        run_migrations=False,
        initialize_seed_data=False,
    )

    assert summary["create_tables"] is False
    assert summary["run_migrations"] is False
    assert summary["initialize_seed_data"] is False
    assert summary["seed_data"] == "skipped"
    assert summary["migrations"] == []
    assert calls == {"create_all": 0, "migrations": 0, "seed": 0, "session": 0}


def test_init_database_executes_only_enabled_actions(monkeypatch, tmp_path) -> None:
    init_database_module = _import_init_database_module(monkeypatch, tmp_path)

    calls = {"create_all": 0, "migrations": 0, "seed": 0, "session": 0}
    closed = {"value": False}
    captured_bind = {"value": None}

    def _fake_create_all(*, bind=None) -> None:
        calls["create_all"] += 1
        captured_bind["value"] = bind

    def _fake_run_online_migrations():
        calls["migrations"] += 1
        return [{"module": "fake.migration", "status": "ok"}]

    class _DummySession:
        def __init__(self) -> None:
            calls["session"] += 1

        def close(self) -> None:
            closed["value"] = True

    def _fake_init_llm_config_data(_db) -> None:
        calls["seed"] += 1

    monkeypatch.setattr(init_database_module.Base.metadata, "create_all", _fake_create_all)
    monkeypatch.setattr(init_database_module, "run_online_migrations", _fake_run_online_migrations)
    monkeypatch.setattr(init_database_module, "SessionLocal", _DummySession)
    monkeypatch.setattr(init_database_module, "init_llm_config_data", _fake_init_llm_config_data)

    summary = init_database_module.init_database(
        create_tables=True,
        run_migrations=True,
        initialize_seed_data=True,
    )

    assert calls == {"create_all": 1, "migrations": 1, "seed": 1, "session": 1}
    assert captured_bind["value"] is init_database_module.engine
    assert closed["value"] is True
    assert summary["migrations"] == [{"module": "fake.migration", "status": "ok"}]
    assert summary["seed_data"] == "initialized"
