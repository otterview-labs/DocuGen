from __future__ import annotations

import importlib
import sys
from datetime import datetime
from types import SimpleNamespace

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


def _load_endpoint_module(
    monkeypatch,
    tmp_path,
    relative_path: str,
    module_name: str,
    *,
    stub_unified_search_service: bool = False,
    stub_enhanced_rag_service: bool = False,
    stub_vector_db: bool = False,
    env_overrides: dict[str, object] | None = None,
):
    configure_runtime_env(monkeypatch, tmp_path, **(env_overrides or {}))
    clear_modules(prefixes=("app", "main", "_test"))

    loguru_module = make_stub_module(
        "loguru",
        logger=SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
            debug=lambda *args, **kwargs: None,
        ),
    )
    monkeypatch.setitem(sys.modules, "loguru", loguru_module)

    import app

    if stub_unified_search_service or stub_enhanced_rag_service:
        services_pkg = make_package_stub("app.services")
        monkeypatch.setitem(sys.modules, "app.services", services_pkg)
        setattr(app, "services", services_pkg)

        if stub_unified_search_service:
            unified_search_module = make_stub_module(
                "app.services.unified_search_service",
                get_unified_search_service=lambda: None,
            )
            services_pkg.unified_search_service = unified_search_module
            monkeypatch.setitem(sys.modules, "app.services.unified_search_service", unified_search_module)

        if stub_enhanced_rag_service:
            enhanced_rag_module = make_stub_module(
                "app.services.enhanced_rag_service",
                get_enhanced_rag_service=lambda: None,
            )
            services_pkg.enhanced_rag_service = enhanced_rag_module
            monkeypatch.setitem(sys.modules, "app.services.enhanced_rag_service", enhanced_rag_module)

    if stub_vector_db:
        core_module = importlib.import_module("app.core")
        rag_pkg = make_package_stub("app.core.rag")
        vector_db_module = make_stub_module(
            "app.core.rag.vector_db",
            get_vector_db=lambda: None,
        )
        rag_pkg.vector_db = vector_db_module
        monkeypatch.setitem(sys.modules, "app.core.rag", rag_pkg)
        monkeypatch.setitem(sys.modules, "app.core.rag.vector_db", vector_db_module)
        setattr(core_module, "rag", rag_pkg)

    return load_module_from_path(module_name, REPO_ROOT / relative_path)


def _build_app(endpoint_module, *, prefix: str, db_session, dependency_overrides: dict | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(endpoint_module.router, prefix=prefix)
    app.dependency_overrides[endpoint_module.get_db] = lambda: db_session
    for dependency, override in (dependency_overrides or {}).items():
        app.dependency_overrides[dependency] = override
    return app


def test_unified_search_endpoint_returns_search_response(monkeypatch, tmp_path) -> None:
    endpoint_module = _load_endpoint_module(
        monkeypatch,
        tmp_path,
        "app/api/v1/rag/endpoints/unified_search.py",
        "_test_unified_search_endpoint",
        stub_unified_search_service=True,
    )

    class _SearchService:
        async def search(self, request, user_id, db):  # noqa: ANN001
            assert request.query == "系统架构"
            assert request.search_mode == "semantic"
            assert user_id is None
            assert db is fake_db
            return {
                "results": [{"id": "doc-001", "title": "系统架构说明"}],
                "execution_info": {"search_mode_used": "semantic", "elapsed_ms": 12},
                "suggestions": ["架构设计"],
                "answer": "这是系统架构说明。",
                "citations": [{"doc_id": "doc-001", "title": "系统架构说明"}],
            }

    fake_db = FakeSession()
    monkeypatch.setattr(endpoint_module, "get_unified_search_service", lambda: _SearchService())

    with TestClient(_build_app(endpoint_module, prefix="/api/v1/rag/search", db_session=fake_db)) as client:
        response = client.post(
            "/api/v1/rag/search/unified",
            json={"query": "系统架构", "search_mode": "semantic", "top_k": 5},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "系统架构"
    assert payload["search_mode"] == "semantic"
    assert payload["total"] == 1
    assert payload["results"][0]["id"] == "doc-001"
    assert payload["answer"] == "这是系统架构说明。"


def test_unified_search_endpoint_wraps_service_failure(monkeypatch, tmp_path) -> None:
    endpoint_module = _load_endpoint_module(
        monkeypatch,
        tmp_path,
        "app/api/v1/rag/endpoints/unified_search.py",
        "_test_unified_search_endpoint_error",
        stub_unified_search_service=True,
    )

    class _BrokenSearchService:
        async def search(self, request, user_id, db):  # noqa: ANN001, ARG002
            raise RuntimeError("search backend unavailable")

    fake_db = FakeSession()
    monkeypatch.setattr(endpoint_module, "get_unified_search_service", lambda: _BrokenSearchService())

    with TestClient(_build_app(endpoint_module, prefix="/api/v1/rag/search", db_session=fake_db)) as client:
        response = client.post(
            "/api/v1/rag/search/unified",
            json={"query": "系统架构", "search_mode": "intelligent"},
        )

    assert response.status_code == 500
    assert "检索失败" in response.json()["detail"]


def test_unified_search_endpoint_accepts_kg_mode_and_resource_id(monkeypatch, tmp_path) -> None:
    endpoint_module = _load_endpoint_module(
        monkeypatch,
        tmp_path,
        "app/api/v1/rag/endpoints/unified_search.py",
        "_test_unified_search_endpoint_kg_mode",
        stub_unified_search_service=True,
    )

    class _SearchService:
        async def search(self, request, user_id, db):  # noqa: ANN001, ARG002
            assert request.query == "设备和网关之间的关系"
            assert request.search_mode == "kg"
            assert request.resource_id == "res-001"
            return {
                "results": [{"title": "网关", "resource_id": "res-001"}],
                "execution_info": {"search_mode_used": "kg", "elapsed_ms": 8},
                "suggestions": None,
                "answer": None,
                "citations": None,
            }

    fake_db = FakeSession()
    monkeypatch.setattr(endpoint_module, "get_unified_search_service", lambda: _SearchService())

    with TestClient(_build_app(endpoint_module, prefix="/api/v1/rag/search", db_session=fake_db)) as client:
        response = client.post(
            "/api/v1/rag/search/unified",
            json={
                "query": "设备和网关之间的关系",
                "search_mode": "kg",
                "resource_id": "res-001",
                "top_k": 5,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["search_mode"] == "kg"
    assert payload["results"][0]["resource_id"] == "res-001"


def test_unified_search_endpoint_accepts_image_to_image_without_query(monkeypatch, tmp_path) -> None:
    endpoint_module = _load_endpoint_module(
        monkeypatch,
        tmp_path,
        "app/api/v1/rag/endpoints/unified_search.py",
        "_test_unified_search_endpoint_image_to_image_mode",
        stub_unified_search_service=True,
    )

    class _SearchService:
        async def search(self, request, user_id, db):  # noqa: ANN001, ARG002
            assert request.query is None
            assert request.search_mode == "image_to_image"
            assert request.image.startswith("data:image/png")
            return {
                "results": [{"title": "设备外观图", "resource_id": "res-image-001"}],
                "execution_info": {"search_mode_used": "image_to_image", "elapsed_ms": 12},
                "suggestions": None,
                "answer": None,
                "citations": None,
            }

    fake_db = FakeSession()
    monkeypatch.setattr(endpoint_module, "get_unified_search_service", lambda: _SearchService())

    with TestClient(_build_app(endpoint_module, prefix="/api/v1/rag/search", db_session=fake_db)) as client:
        response = client.post(
            "/api/v1/rag/search/unified",
            json={
                "image": "data:image/png;base64,AAAA",
                "search_mode": "image_to_image",
                "top_k": 5,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["search_mode"] == "image_to_image"
    assert payload["query"] == "图片查询"


def test_collections_create_endpoint_accepts_legacy_id_alias(monkeypatch, tmp_path) -> None:
    endpoint_module = _load_endpoint_module(
        monkeypatch,
        tmp_path,
        "app/api/v1/rag/endpoints/collections.py",
        "_test_collections_endpoint",
        stub_vector_db=True,
    )

    class _VectorDB:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def create_collection(self, *, collection_name: str, dimension: int) -> bool:
            self.calls.append({"collection_name": collection_name, "dimension": dimension})
            return True

    vector_db = _VectorDB()
    fake_db = FakeSession(query_results=[None, None])
    monkeypatch.setattr(endpoint_module, "get_vector_db", lambda: vector_db)

    with TestClient(_build_app(endpoint_module, prefix="/api/v1/rag/collections", db_session=fake_db)) as client:
        response = client.post(
            "/api/v1/rag/collections",
            json={
                "id": "collection-001",
                "name": "技术文档集合",
                "description": "存储技术文档",
                "collection_type": "text",
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["success"] is True
    assert payload["status"] == 201
    assert payload["message"] == "集合创建成功（使用指定ID）"
    assert payload["result"]["id"] == "collection-001"
    assert fake_db.commits == 1
    assert len(fake_db.added) == 1
    assert vector_db.calls == [{"collection_name": "collection-001", "dimension": 1536}]


def test_collections_create_endpoint_rejects_duplicate_name(monkeypatch, tmp_path) -> None:
    endpoint_module = _load_endpoint_module(
        monkeypatch,
        tmp_path,
        "app/api/v1/rag/endpoints/collections.py",
        "_test_collections_endpoint_duplicate",
        stub_vector_db=True,
    )

    fake_db = FakeSession(query_results=[SimpleNamespace(id="existing-collection")])

    with TestClient(_build_app(endpoint_module, prefix="/api/v1/rag/collections", db_session=fake_db)) as client:
        response = client.post(
            "/api/v1/rag/collections",
            json={"name": "技术文档集合", "description": "重复集合", "collection_type": "text"},
        )

    assert response.status_code == 409
    assert "集合名称" in response.json()["detail"]
    assert fake_db.added == []


def test_collections_create_endpoint_requires_auth_when_enforced(monkeypatch, tmp_path) -> None:
    endpoint_module = _load_endpoint_module(
        monkeypatch,
        tmp_path,
        "app/api/v1/rag/endpoints/collections.py",
        "_test_collections_endpoint_auth_required",
        stub_vector_db=True,
        env_overrides={
            "ENVIRONMENT": "production",
            "DEV_MODE": False,
            "SKIP_AUTH": False,
        },
    )

    fake_db = FakeSession(query_results=[None, None])

    with TestClient(_build_app(endpoint_module, prefix="/api/v1/rag/collections", db_session=fake_db)) as client:
        response = client.post(
            "/api/v1/rag/collections",
            json={
                "id": "collection-001",
                "name": "技术文档集合",
                "description": "存储技术文档",
                "collection_type": "text",
            },
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "未提供认证token"


def test_collections_create_endpoint_skips_auth_when_configured_in_production(monkeypatch, tmp_path) -> None:
    endpoint_module = _load_endpoint_module(
        monkeypatch,
        tmp_path,
        "app/api/v1/rag/endpoints/collections.py",
        "_test_collections_endpoint_skip_auth_production",
        stub_vector_db=True,
        env_overrides={
            "ENVIRONMENT": "production",
            "DEV_MODE": False,
            "SKIP_AUTH": True,
        },
    )

    fake_db = FakeSession(query_results=[None, None])

    with TestClient(_build_app(endpoint_module, prefix="/api/v1/rag/collections", db_session=fake_db)) as client:
        response = client.post(
            "/api/v1/rag/collections",
            json={
                "id": "collection-001",
                "name": "技术文档集合",
                "description": "存储技术文档",
                "collection_type": "text",
            },
        )

    assert response.status_code == 201
    assert fake_db.added[0].user_id == "anonymous"


def test_unified_search_endpoint_forwards_authenticated_user_id(monkeypatch, tmp_path) -> None:
    endpoint_module = _load_endpoint_module(
        monkeypatch,
        tmp_path,
        "app/api/v1/rag/endpoints/unified_search.py",
        "_test_unified_search_endpoint_with_user",
        stub_unified_search_service=True,
        env_overrides={
            "ENVIRONMENT": "production",
            "DEV_MODE": False,
            "SKIP_AUTH": False,
        },
    )

    class _SearchService:
        async def search(self, request, user_id, db):  # noqa: ANN001
            assert request.query == "系统架构"
            assert user_id == "user-001"
            assert db is fake_db
            return {
                "results": [{"id": "doc-001", "title": "系统架构说明"}],
                "execution_info": {"search_mode_used": "semantic", "elapsed_ms": 12},
            }

    fake_db = FakeSession()
    monkeypatch.setattr(endpoint_module, "get_unified_search_service", lambda: _SearchService())

    dependency_overrides = {
        endpoint_module.get_request_user: lambda: SimpleNamespace(id="user-001"),
    }

    with TestClient(
        _build_app(
            endpoint_module,
            prefix="/api/v1/rag/search",
            db_session=fake_db,
            dependency_overrides=dependency_overrides,
        )
    ) as client:
        response = client.post(
            "/api/v1/rag/search/unified",
            json={"query": "系统架构", "search_mode": "semantic", "top_k": 5},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["results"][0]["id"] == "doc-001"


def test_document_get_endpoint_returns_text_fallback_payload(monkeypatch, tmp_path) -> None:
    endpoint_module = _load_endpoint_module(
        monkeypatch,
        tmp_path,
        "app/api/v1/rag/endpoints/document_operations.py",
        "_test_document_operations_endpoint",
        stub_enhanced_rag_service=True,
        stub_vector_db=True,
    )

    fake_document = SimpleNamespace(
        id="doc-001",
        title="系统启动流程",
        description="启动说明",
        user_id="tester",
        content_type="document",
        content_text="# 启动流程\n\n先检查数据库。",
        content_summary="启动流程摘要",
        content_tags=["指南", "启动"],
        file_name="guide.md",
        file_size=128,
        mime_type="text/markdown",
        file_path=None,
        vector_collection="collection-001",
        status="1",
        processing_status="completed",
        processing_message="done",
        create_time=datetime(2026, 4, 6, 12, 0, 0),
        update_time=datetime(2026, 4, 6, 12, 30, 0),
    )
    fake_db = FakeSession(query_results=[fake_document])
    monkeypatch.setattr(endpoint_module, "_resolve_existing_file_path", lambda _path: None)

    with TestClient(_build_app(endpoint_module, prefix="/api/v1/rag/documents", db_session=fake_db)) as client:
        response = client.post(
            "/api/v1/rag/documents/get",
            json={"resource_id": "doc-001"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["result"]["id"] == "doc-001"
    assert payload["result"]["content"]["format"] == "markdown"
    assert payload["result"]["file_info"]["url"] == "/api/v1/rag/documents/raw/doc-001"
    assert payload["result"]["file_info"]["download_url"].endswith("document_id=doc-001")


def test_document_reindex_endpoint_reports_ok_and_failed_counts(monkeypatch, tmp_path) -> None:
    endpoint_module = _load_endpoint_module(
        monkeypatch,
        tmp_path,
        "app/api/v1/rag/endpoints/document_operations.py",
        "_test_document_operations_reindex",
        stub_enhanced_rag_service=True,
        stub_vector_db=True,
    )

    documents = [
        SimpleNamespace(id="doc-001"),
        SimpleNamespace(id="doc-002"),
    ]
    fake_db = FakeSession(query_results=[documents])

    class _RagService:
        async def add_document_to_vector_db(self, document, db):  # noqa: ANN001
            assert db is fake_db
            return document.id == "doc-001"

    monkeypatch.setattr(endpoint_module, "get_enhanced_rag_service", lambda: _RagService())

    with TestClient(_build_app(endpoint_module, prefix="/api/v1/rag/documents", db_session=fake_db)) as client:
        response = client.post(
            "/api/v1/rag/documents/reindex",
            json={"collection_id": "collection-001", "limit": 10},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "重建完成"
    assert payload["result"]["processed"] == 2
    assert payload["result"]["ok"] == 1
    assert payload["result"]["failed"] == 1
    assert payload["result"]["errors"][0]["id"] == "doc-002"
