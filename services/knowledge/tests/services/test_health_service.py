from __future__ import annotations

import importlib
import sys
import types

import pytest

from tests.helpers import clear_modules, configure_runtime_env


pytestmark = pytest.mark.unit


def _import_health_service(monkeypatch, tmp_path, **env_overrides):
    configure_runtime_env(monkeypatch, tmp_path, **env_overrides)
    clear_modules()
    return importlib.import_module("app.services.health_service")


def test_build_health_report_returns_healthy_when_required_checks_pass(monkeypatch, tmp_path) -> None:
    health_service = _import_health_service(monkeypatch, tmp_path)

    payload, status_code = health_service.build_health_report()

    assert status_code == 200
    assert payload["status"] == "healthy"
    assert payload["mode"] == "test"
    assert payload["checks"]["database"]["status"] == "healthy"
    assert payload["checks"]["vector_db"]["status"] == "healthy"
    assert payload["checks"]["graph_db"]["status"] == "skipped"
    assert payload["checks"]["redis"]["status"] == "skipped"


def test_build_health_report_returns_degraded_when_optional_redis_fails(monkeypatch, tmp_path) -> None:
    health_service = _import_health_service(
        monkeypatch,
        tmp_path,
        HEALTH_CHECK_REDIS=True,
        REDIS_HOST="redis.local",
        REDIS_PORT=6379,
    )

    redis_module = types.ModuleType("redis")

    class _BrokenRedisClient:
        def ping(self) -> None:
            raise RuntimeError("redis down")

    redis_module.Redis = lambda *args, **kwargs: _BrokenRedisClient()
    redis_module.from_url = lambda *args, **kwargs: _BrokenRedisClient()
    monkeypatch.setitem(sys.modules, "redis", redis_module)

    payload, status_code = health_service.build_health_report()

    assert status_code == 200
    assert payload["status"] == "degraded"
    assert payload["checks"]["database"]["status"] == "healthy"
    assert payload["checks"]["redis"]["status"] == "unhealthy"
    assert "redis down" in payload["checks"]["redis"]["detail"]


def test_build_health_report_returns_unhealthy_when_database_check_fails(monkeypatch, tmp_path) -> None:
    health_service = _import_health_service(monkeypatch, tmp_path)
    monkeypatch.setattr(health_service, "test_db_connection", lambda: False)

    payload, status_code = health_service.build_health_report()

    assert status_code == 503
    assert payload["status"] == "unhealthy"
    assert payload["checks"]["database"]["status"] == "unhealthy"
