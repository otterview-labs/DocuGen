from __future__ import annotations

import logging
import sys
from pathlib import Path

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


def test_legacy_frame_route_serves_only_validated_local_files(monkeypatch, tmp_path):
    main = _load_main_module(monkeypatch, tmp_path)
    # Use the configured storage root rather than an arbitrary filesystem path.
    uploads = Path(main.settings.storage.STATIC_DIR) / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    (uploads / "synthetic.png").write_bytes(b"synthetic media")
    private = tmp_path / "private.png"
    private.write_bytes(b"private sentinel")
    (uploads / "escape.png").symlink_to(private)
    app = main.FastAPI()
    main.register_routes(app)
    with TestClient(app) as client:
        normal = client.get("/optimized_frames/synthetic.png", follow_redirects=False)
        assert normal.status_code == 200
        assert normal.content == b"synthetic media"
        assert "location" not in normal.headers
        for path in ("escape.png", "%2F%2Fevil.example", "%2E%2E%2Fprivate.png"):
            response = client.get("/optimized_frames/" + path, follow_redirects=False)
            assert response.status_code == 404
            assert "location" not in response.headers


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
    shared_utils_pkg.__path__ = [str(REPO_ROOT / "app/shared/utils")]

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


def test_media_routes_reject_symlink_escape_and_encoded_traversal(monkeypatch, tmp_path):
    main_module = _load_main_module(monkeypatch, tmp_path)

    async def noop():
        return None

    main_module.initialize_services = noop
    main_module.cleanup_services = noop
    from app.config import settings
    from pathlib import Path
    uploads = Path(settings.storage.STATIC_DIR) / 'uploads'
    private = tmp_path / 'private.txt'
    private.write_text('private sentinel')
    (uploads / 'escape.txt').symlink_to(private)
    processed = uploads / 'processed' / 'one' / 'two' / 'optimized_frames'
    processed.mkdir(parents=True)
    (processed / 'frame.jpg').write_bytes(b'synthetic frame')
    (processed / 'leaked.jpg').symlink_to(private)
    with TestClient(main_module.create_app()) as client:
        assert client.get('/api/file/frame.jpg').content == b'synthetic frame'
        for url in ('/uploads/escape.txt', '/api/file/leaked.jpg', '/uploads/%2e%2e/private.txt', '/api/file/..%5cprivate.txt'):
            response = client.get(url)
            assert response.status_code == 404, url
            assert 'private sentinel' not in response.text
