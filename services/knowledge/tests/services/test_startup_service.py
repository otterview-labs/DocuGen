from __future__ import annotations

import importlib

import pytest

from tests.helpers import clear_modules, configure_runtime_env


pytestmark = pytest.mark.unit


def _import_startup_service(monkeypatch, tmp_path, **env_overrides):
    configure_runtime_env(monkeypatch, tmp_path, **env_overrides)
    clear_modules()
    return importlib.import_module("app.services.startup_service")


@pytest.mark.asyncio
async def test_initialize_runtime_services_skips_database_actions_when_all_switches_off(monkeypatch, tmp_path) -> None:
    startup_service = _import_startup_service(monkeypatch, tmp_path)

    init_calls: list[dict] = []

    monkeypatch.setattr(startup_service.settings.startup, "CHECK_DATABASE_ON_STARTUP", False)
    monkeypatch.setattr(startup_service.settings.startup, "INITIALIZE_DATABASE_ON_STARTUP", False)
    monkeypatch.setattr(startup_service.settings.startup, "RUN_DATABASE_MIGRATIONS_ON_STARTUP", False)
    monkeypatch.setattr(startup_service.settings.startup, "SEED_LLM_CONFIG_ON_STARTUP", False)
    monkeypatch.setattr(startup_service, "init_database", lambda **kwargs: init_calls.append(kwargs))

    summary = await startup_service.initialize_runtime_services()

    assert summary["database_connection_checked"] is False
    assert summary["database_initialized"] is False
    assert summary["database_init_summary"] is None
    assert init_calls == []


@pytest.mark.asyncio
async def test_initialize_runtime_services_fails_fast_when_database_check_fails(monkeypatch, tmp_path) -> None:
    startup_service = _import_startup_service(monkeypatch, tmp_path)

    init_calls: list[dict] = []

    monkeypatch.setattr(startup_service.settings.startup, "CHECK_DATABASE_ON_STARTUP", True)
    monkeypatch.setattr(startup_service.settings.startup, "FAIL_FAST_ON_STARTUP_ERROR", True)
    monkeypatch.setattr(startup_service, "test_db_connection", lambda: False)
    monkeypatch.setattr(startup_service, "init_database", lambda **kwargs: init_calls.append(kwargs))

    with pytest.raises(RuntimeError, match="数据库连接检查失败"):
        await startup_service.initialize_runtime_services()

    assert init_calls == []


@pytest.mark.asyncio
async def test_initialize_runtime_services_forwards_explicit_database_switches(monkeypatch, tmp_path) -> None:
    startup_service = _import_startup_service(monkeypatch, tmp_path)

    captured: dict[str, bool] = {}

    monkeypatch.setattr(startup_service.settings.startup, "CHECK_DATABASE_ON_STARTUP", True)
    monkeypatch.setattr(startup_service.settings.startup, "INITIALIZE_DATABASE_ON_STARTUP", True)
    monkeypatch.setattr(startup_service.settings.startup, "RUN_DATABASE_MIGRATIONS_ON_STARTUP", True)
    monkeypatch.setattr(startup_service.settings.startup, "SEED_LLM_CONFIG_ON_STARTUP", True)
    monkeypatch.setattr(startup_service, "test_db_connection", lambda: True)

    def _fake_init_database(**kwargs):
        captured.update(kwargs)
        return {"migrations": [{"module": "fake.migration", "status": "ok"}]}

    monkeypatch.setattr(startup_service, "init_database", _fake_init_database)

    summary = await startup_service.initialize_runtime_services()

    assert captured == {
        "create_tables": True,
        "run_migrations": True,
        "initialize_seed_data": True,
    }
    assert summary["database_connection_checked"] is True
    assert summary["database_connection_ok"] is True
    assert summary["database_initialized"] is True
    assert summary["database_init_summary"]["migrations"][0]["module"] == "fake.migration"
