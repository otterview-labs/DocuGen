from __future__ import annotations

import importlib
import types

import pytest
from fastapi import APIRouter

from tests.helpers import REPO_ROOT, clear_modules, collect_route_paths, load_module_from_path


pytestmark = pytest.mark.api


def test_rag_router_skips_endpoints_with_missing_optional_dependencies(monkeypatch) -> None:
    clear_modules(prefixes=("app.api.v1.rag", "_test"))

    real_import_module = importlib.import_module

    def _build_fake_endpoint_module(name: str) -> types.SimpleNamespace:
        router = APIRouter()

        @router.get("/probe")
        async def probe():  # noqa: ANN202
            return {"module": name}

        return types.SimpleNamespace(router=router)

    def _fake_import_module(name: str, package: str | None = None):
        if name == "app.api.v1.rag.endpoints.multimodal_upload":
            raise ModuleNotFoundError("No module named 'aiofiles'")
        if name.startswith("app.api.v1.rag.endpoints."):
            return _build_fake_endpoint_module(name)
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", _fake_import_module)

    router_module = load_module_from_path(
        "_test_rag_router_module",
        REPO_ROOT / "app/api/v1/rag/router.py",
    )

    paths = collect_route_paths(router_module.router)
    errors = router_module.get_route_import_errors()

    assert "/collections/probe" in paths
    assert "/search/probe" in paths
    assert "/multimodal/probe" not in paths
    assert "app.api.v1.rag.endpoints.multimodal_upload" in errors
    assert "aiofiles" in errors["app.api.v1.rag.endpoints.multimodal_upload"]
