from __future__ import annotations

import logging
import sys

import pytest
from fastapi import APIRouter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.testclient import TestClient

from tests.helpers import (
    REPO_ROOT,
    clear_modules,
    configure_runtime_env,
    load_module_from_path,
    make_package_stub,
    make_stub_module,
)


pytestmark = pytest.mark.api


class _PassThroughMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):  # noqa: ANN001
        return await call_next(request)


def _load_main_module(monkeypatch, tmp_path):
    configure_runtime_env(monkeypatch, tmp_path)
    clear_modules()

    api_v1_pkg = make_package_stub("app.api.v1")
    api_compat_pkg = make_package_stub("app.api.compat")
    services_pkg = make_package_stub("app.services")
    shared_utils_pkg = make_package_stub("app.shared.utils")

    monkeypatch.setitem(sys.modules, "app.api.quill_ingest", make_stub_module("app.api.quill_ingest", router=APIRouter()))
    api_router_module = make_stub_module("app.api.v1.router", router=APIRouter())
    compat_router_module = make_stub_module("app.api.compat.knowledge_compat", router=APIRouter())
    logger_util_module = make_stub_module(
        "app.shared.utils.logger_util",
        get_logger=lambda *args, **kwargs: logging.getLogger("test-main"),
    )
    http_auth_module = make_stub_module(
        "app.shared.utils.http_auth",
        normalize_auth_mode=lambda value, default="bearer": default if value is None else str(value).strip().lower(),
    )
    middleware_module = make_stub_module(
        "app.shared.middleware",
        APILoggingMiddleware=_PassThroughMiddleware,
    )
    health_service_module = make_stub_module(
        "app.services.health_service",
        build_health_report=lambda: ({"status": "healthy"}, 200),
    )

    async def _initialize_runtime_services():
        return {}

    startup_service_module = make_stub_module(
        "app.services.startup_service",
        initialize_runtime_services=_initialize_runtime_services,
    )

    api_v1_pkg.router = api_router_module
    api_compat_pkg.knowledge_compat = compat_router_module
    shared_utils_pkg.logger_util = logger_util_module
    shared_utils_pkg.http_auth = http_auth_module
    services_pkg.health_service = health_service_module
    services_pkg.startup_service = startup_service_module

    monkeypatch.setitem(sys.modules, "app.api.v1", api_v1_pkg)
    monkeypatch.setitem(sys.modules, "app.api.v1.router", api_router_module)
    monkeypatch.setitem(sys.modules, "app.api.compat", api_compat_pkg)
    monkeypatch.setitem(sys.modules, "app.api.compat.knowledge_compat", compat_router_module)
    monkeypatch.setitem(sys.modules, "app.shared.utils", shared_utils_pkg)
    monkeypatch.setitem(sys.modules, "app.shared.utils.logger_util", logger_util_module)
    monkeypatch.setitem(sys.modules, "app.shared.utils.http_auth", http_auth_module)
    monkeypatch.setitem(sys.modules, "app.shared.middleware", middleware_module)
    monkeypatch.setitem(sys.modules, "app.services", services_pkg)
    monkeypatch.setitem(sys.modules, "app.services.health_service", health_service_module)
    monkeypatch.setitem(sys.modules, "app.services.startup_service", startup_service_module)

    return load_module_from_path("_test_main_module", REPO_ROOT / "main.py")


def test_health_route_returns_service_payload(monkeypatch, tmp_path) -> None:
    main_module = _load_main_module(monkeypatch, tmp_path)

    async def _noop():
        return None

    main_module.initialize_services = _noop
    main_module.cleanup_services = _noop
    main_module.build_health_report = lambda: (
        {
            "status": "healthy",
            "checks": {"database": {"status": "healthy"}},
        },
        200,
    )

    with TestClient(main_module.create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["checks"]["database"]["status"] == "healthy"


def test_health_route_propagates_unhealthy_status_code(monkeypatch, tmp_path) -> None:
    main_module = _load_main_module(monkeypatch, tmp_path)

    async def _noop():
        return None

    main_module.initialize_services = _noop
    main_module.cleanup_services = _noop
    main_module.build_health_report = lambda: (
        {
            "status": "unhealthy",
            "checks": {"database": {"status": "unhealthy"}},
        },
        503,
    )

    with TestClient(main_module.create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"


def test_legacy_api_file_route_serves_static_upload(monkeypatch, tmp_path) -> None:
    main_module = _load_main_module(monkeypatch, tmp_path)

    async def _noop():
        return None

    main_module.initialize_services = _noop
    main_module.cleanup_services = _noop

    with TestClient(main_module.create_app()) as client:
        response = client.get("/api/file/hello.txt")

    assert response.status_code == 200
    assert response.text == "knowledge upload"
