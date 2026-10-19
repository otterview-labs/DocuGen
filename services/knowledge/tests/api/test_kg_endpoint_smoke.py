from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

from tests.api.test_rag_endpoint_smoke import _build_app, _load_endpoint_module
from tests.helpers import FakeSession


pytestmark = pytest.mark.api


def test_kg_endpoint_imports_without_neo4j_dependency(monkeypatch, tmp_path) -> None:
    endpoint_module = _load_endpoint_module(
        monkeypatch,
        tmp_path,
        "app/api/v1/rag/endpoints/kg.py",
        "_test_kg_endpoint_import",
    )

    paths = {route.path for route in endpoint_module.router.routes}
    assert "/query" in paths
    assert "/analysis/association" in paths
    assert "/statistics/knowledge-graph" in paths


def test_kg_query_endpoint_uses_manager_abstraction(monkeypatch, tmp_path) -> None:
    endpoint_module = _load_endpoint_module(
        monkeypatch,
        tmp_path,
        "app/api/v1/rag/endpoints/kg.py",
        "_test_kg_endpoint_query",
    )

    class _Manager:
        def __init__(self, namespace: str) -> None:
            assert namespace == "default"

        def is_enabled(self) -> bool:
            return True

        async def query_nodes(self, **kwargs):  # noqa: ANN003
            assert kwargs["query"] == "人工智能"
            assert kwargs["node_type"] == "技术概念"
            assert kwargs["document_id"] == "content-001"
            return [
                {
                    "id": "node-1",
                    "name": "人工智能",
                    "description": "测试节点",
                    "node_type": "entity",
                    "labels": ["技术概念"],
                    "properties": {"confidence": 0.9},
                    "source_doc": "content-001",
                }
            ]

        async def query_edges(self, **kwargs):  # noqa: ANN003
            assert kwargs["document_id"] == "content-001"
            assert kwargs["node_ids"] == ["node-1"]
            return [
                {
                    "source": "node-1",
                    "target": "node-1",
                    "type": "相关",
                    "description": "自关联",
                    "properties": {"confidence": 0.7},
                    "source_doc": "content-001",
                }
            ]

    fake_db = FakeSession(query_results=[SimpleNamespace(id="content-001")])
    monkeypatch.setattr(endpoint_module, "KnowledgeGraphManager", _Manager)

    with TestClient(_build_app(endpoint_module, prefix="/api/v1/rag/kg", db_session=fake_db)) as client:
        response = client.post(
            "/api/v1/rag/kg/query",
            json={
                "query": "人工智能",
                "node_type": "技术概念",
                "document_id": "resource-001",
                "limit": 10,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["result"]["document_id"] == "content-001"
    assert payload["result"]["total_nodes"] == 1
    assert payload["result"]["total_relationships"] == 1
    assert payload["result"]["echarts_data"]["nodes"][0]["name"] == "人工智能"


def test_kg_extract_get_entities_uses_request_content_id(monkeypatch, tmp_path) -> None:
    endpoint_module = _load_endpoint_module(
        monkeypatch,
        tmp_path,
        "app/api/v1/rag/endpoints/kg_extract.py",
        "_test_kg_extract_endpoint",
    )

    class _Manager:
        def __init__(self, namespace: str) -> None:
            assert namespace == "default"

        def is_enabled(self) -> bool:
            return True

        async def list_document_entities(self, document_id: str, *, content_name: str = "", limit: int = 50):
            assert document_id == "content-123"
            assert content_name == "知识图谱文档"
            assert limit == 50
            return [
                {
                    "id": "entity-1",
                    "name": "人工智能",
                    "description": "测试实体",
                    "node_type": "entity",
                    "labels": ["技术概念"],
                    "properties": {},
                    "source_doc": document_id,
                }
            ]

    fake_db = FakeSession(query_results=[SimpleNamespace(id="content-123", title="知识图谱文档")])
    monkeypatch.setattr(endpoint_module, "KnowledgeGraphManager", _Manager)

    with TestClient(_build_app(endpoint_module, prefix="/api/v1/rag/kg", db_session=fake_db)) as client:
        response = client.post("/api/v1/rag/kg/get-entities", json={"content_id": "content-123"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["result"]["content_id"] == "content-123"
    assert payload["result"]["content_title"] == "知识图谱文档"
    assert payload["result"]["total_entities"] == 1
    assert payload["result"]["entities"][0]["name"] == "人工智能"
