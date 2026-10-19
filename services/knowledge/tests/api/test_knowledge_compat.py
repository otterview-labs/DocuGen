from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from tests.helpers import (
    REPO_ROOT,
    FakeSession,
    clear_modules,
    configure_runtime_env,
    load_module_from_path,
    make_package_stub,
    make_stub_module,
)

pytestmark = pytest.mark.api


def _noop_logger() -> SimpleNamespace:
    return SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
        debug=lambda *a, **k: None,
    )


def _load_compat_module(monkeypatch, tmp_path, module_name: str, **env_overrides):
    """隔离加载 app/api/compat/knowledge_compat.py，stub 掉外部依赖。"""
    configure_runtime_env(monkeypatch, tmp_path, **env_overrides)
    clear_modules(prefixes=("app", "main", "_test"))

    monkeypatch.setitem(sys.modules, "loguru", make_stub_module("loguru", logger=_noop_logger()))
    monkeypatch.setitem(
        sys.modules,
        "app.shared.utils.logger_util",
        make_stub_module("app.shared.utils.logger_util", get_logger=lambda *a, **k: _noop_logger()),
    )

    import app  # noqa: F811 -- 触发 app 包结构加载

    # stub app.services.unified_search_service（compat 会 import get_unified_search_service）
    services_pkg = make_package_stub("app.services")
    uss_module = make_stub_module(
        "app.services.unified_search_service",
        get_unified_search_service=lambda: None,
    )
    services_pkg.unified_search_service = uss_module
    monkeypatch.setitem(sys.modules, "app.services", services_pkg)
    monkeypatch.setitem(sys.modules, "app.services.unified_search_service", uss_module)
    setattr(app, "services", services_pkg)

    return load_module_from_path(module_name, REPO_ROOT / "app/api/compat/knowledge_compat.py")


def _build_app(compat_module, db_session, dependency_overrides=None):
    """router 自带 prefix=/knowledge，include 时不再加前缀。"""
    application = FastAPI()
    application.include_router(compat_module.router)
    application.include_router(compat_module.router, prefix="/api")
    application.dependency_overrides[compat_module.get_db] = lambda: db_session
    for dependency, override in (dependency_overrides or {}).items():
        application.dependency_overrides[dependency] = override
    return application


# ---------------------------------------------------------------------------
# 接口1：/knowledge/resource/_search
# ---------------------------------------------------------------------------

def test_compat_search_maps_request_and_response(monkeypatch, tmp_path) -> None:
    compat = _load_compat_module(monkeypatch, tmp_path, "_test_compat_search_map")

    captured: dict = {}

    class _SearchService:
        async def search(self, request, user_id, db):  # noqa: ANN001
            captured["query"] = request.query
            captured["search_mode"] = request.search_mode
            captured["collection_id"] = request.collection_id
            captured["user_id"] = user_id
            return {
                "results": [
                    {
                        "snippet": "命中片段",
                        "similarity_score": 0.92,
                        "title": "文档标题",
                        "resource_id": "res-001",
                        "description": "文档摘要",
                        "metadata": {"extension": "pdf"},
                        "content_type": "pdf",
                    }
                ],
                "execution_info": {},
            }

    monkeypatch.setattr(compat, "get_unified_search_service", lambda: _SearchService())

    with TestClient(_build_app(compat, FakeSession())) as client:
        response = client.post(
            "/knowledge/resource/_search",
            json={"text": "查询内容", "expands": {"searchMode": "semantic", "collectionId": ["c1"]}},
        )

    assert response.status_code == 200
    # 请求转换：前端 {text, expands.searchMode, expands.collectionId} -> runtime {query, search_mode, collection_id}
    assert captured["query"] == "查询内容"
    assert captured["search_mode"] == "semantic"
    assert captured["collection_id"] == ["c1"]
    # 响应转换：runtime SearchResultItem -> 前端 {snippet, confidence, expands, knowledge}
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload["result"], list)
    item = payload["result"][0]
    assert item["snippet"] == "命中片段"
    assert item["confidence"] == 0.92
    assert item["expands"]["summary"] == "文档摘要"
    assert item["knowledge"]["id"] == "res-001"
    assert item["knowledge"]["name"] == "文档标题"
    assert item["knowledge"]["content"]["extension"] == "pdf"


def test_compat_search_unknown_mode_falls_back_to_intelligent(monkeypatch, tmp_path) -> None:
    compat = _load_compat_module(monkeypatch, tmp_path, "_test_compat_search_fallback")

    captured: dict = {}

    class _SearchService:
        async def search(self, request, user_id, db):  # noqa: ANN001, ARG002
            captured["mode"] = request.search_mode
            return {"results": [], "execution_info": {}}

    monkeypatch.setattr(compat, "get_unified_search_service", lambda: _SearchService())

    with TestClient(_build_app(compat, FakeSession())) as client:
        response = client.post(
            "/knowledge/resource/_search",
            json={"text": "x", "expands": {"searchMode": "未知的模式"}},
        )

    assert response.status_code == 200
    assert captured["mode"] == "intelligent"
    assert response.json()["result"] == []


def test_compat_search_api_prefixed_alias(monkeypatch, tmp_path) -> None:
    compat = _load_compat_module(monkeypatch, tmp_path, "_test_compat_search_api_alias")

    class _SearchService:
        async def search(self, request, user_id, db):  # noqa: ANN001, ARG002
            return {"results": [], "execution_info": {}}

    monkeypatch.setattr(compat, "get_unified_search_service", lambda: _SearchService())

    with TestClient(_build_app(compat, FakeSession())) as client:
        response = client.post("/api/knowledge/resource/_search", json={"text": "x"})

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["result"] == []


def test_compat_search_empty_text_returns_empty(monkeypatch, tmp_path) -> None:
    compat = _load_compat_module(monkeypatch, tmp_path, "_test_compat_search_empty")

    with TestClient(_build_app(compat, FakeSession())) as client:
        response = client.post("/knowledge/resource/_search", json={})

    assert response.status_code == 200
    assert response.json()["result"] == []


def test_compat_search_tolerates_invalid_token_in_production(monkeypatch, tmp_path) -> None:
    """生产模式下携带外部无效 token 不应 401（容错放行，对应 get_compat_request_user）。"""
    compat = _load_compat_module(
        monkeypatch,
        tmp_path,
        "_test_compat_search_auth",
        env_overrides={"ENVIRONMENT": "production", "DEV_MODE": False, "SKIP_AUTH": False},
    )

    captured: dict = {}

    class _SearchService:
        async def search(self, request, user_id, db):  # noqa: ANN001, ARG002
            captured["user_id"] = user_id
            return {"results": [], "execution_info": {}}

    monkeypatch.setattr(compat, "get_unified_search_service", lambda: _SearchService())

    with TestClient(_build_app(compat, FakeSession())) as client:
        response = client.post(
            "/knowledge/resource/_search",
            json={"text": "x"},
            headers={"Authorization": "Bearer fake.cloud.token"},
        )

    assert response.status_code == 200
    assert captured["user_id"] is None


def test_compat_search_wraps_service_failure(monkeypatch, tmp_path) -> None:
    compat = _load_compat_module(monkeypatch, tmp_path, "_test_compat_search_error")

    class _BrokenSearchService:
        async def search(self, request, user_id, db):  # noqa: ANN001, ARG002
            raise RuntimeError("backend unavailable")

    monkeypatch.setattr(compat, "get_unified_search_service", lambda: _BrokenSearchService())

    with TestClient(_build_app(compat, FakeSession())) as client:
        response = client.post("/knowledge/resource/_search", json={"text": "x"})

    # 兼容层用 ResponseHelper.error：HTTP 200 + body {success:false, status:500}（jetlinks 前端风格）
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["status"] == 500
    assert "检索失败" in payload["message"]


# ---------------------------------------------------------------------------
# 接口2：/knowledge/resource/defaultAi/cmd/queryKnowledgeGraph
# ---------------------------------------------------------------------------

def test_compat_kg_query_wraps_result_under_data(monkeypatch, tmp_path) -> None:
    compat = _load_compat_module(monkeypatch, tmp_path, "_test_compat_kg_query")

    monkeypatch.setattr(compat, "_resolve_document_id", AsyncMock(return_value="resolved-doc"))

    fake_manager = SimpleNamespace(
        is_enabled=lambda: True,
        query_nodes=AsyncMock(return_value=[{"id": "n1", "name": "节点一", "type": "技术"}]),
        query_edges=AsyncMock(return_value=[{"source": "n1", "target": "n1", "value": 1}]),
    )
    monkeypatch.setattr(compat, "_build_kg_manager", lambda: fake_manager)
    monkeypatch.setattr(
        compat,
        "_build_echarts_payload",
        lambda nodes, edges: {
            "nodes": [{"name": "节点一"}],
            "links": [{"source": "n1", "target": "n1"}],
            "categories": [{"name": "技术"}],
        },
    )

    with TestClient(_build_app(compat, FakeSession())) as client:
        response = client.post(
            "/knowledge/resource/defaultAi/cmd/queryKnowledgeGraph",
            json={"document_id": "doc-001"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    # 前端取 result.data.echarts_data，故相对 runtime 原接口多包一层 data
    assert "data" in payload["result"]
    assert payload["result"]["data"]["echarts_data"]["nodes"][0]["name"] == "节点一"
    assert payload["result"]["data"]["document_id"] == "resolved-doc"


def test_compat_kg_query_disabled_returns_empty(monkeypatch, tmp_path) -> None:
    compat = _load_compat_module(monkeypatch, tmp_path, "_test_compat_kg_disabled")

    monkeypatch.setattr(compat, "_resolve_document_id", AsyncMock(return_value="d1"))
    fake_manager = SimpleNamespace(is_enabled=lambda: False)
    monkeypatch.setattr(compat, "_build_kg_manager", lambda: fake_manager)

    with TestClient(_build_app(compat, FakeSession())) as client:
        response = client.post(
            "/knowledge/resource/defaultAi/cmd/queryKnowledgeGraph",
            json={"document_id": "d1"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["data"]["echarts_data"] == {"nodes": [], "links": [], "categories": []}
