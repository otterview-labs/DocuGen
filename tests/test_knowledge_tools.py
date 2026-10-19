import json

import httpx
import pytest
from fastapi.testclient import TestClient

from quill.config import Settings
from quill.knowledge_operations import OPERATIONS
from quill.main import create_app


@pytest.fixture
def tools(tmp_path, monkeypatch):
    requests = []
    configured = {"graph": False, "llm": False, "embedding": False}
    replies = {}

    def respond(request):
        requests.append(request)
        path = request.url.path.removeprefix("/api/v1/rag/")
        if path == "quill/capabilities":
            return httpx.Response(
                200,
                json={
                    "paths": {"/api/v1/rag/" + op.path: [op.method] for op in OPERATIONS.values()},
                    "configured": configured,
                    "vector_backend": "pgvector",
                },
            )
        return replies.get(path, httpx.Response(200, json={"success": True, "result": {"accepted": True}}))

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs)
    )
    settings = Settings(data_dir=tmp_path, api_key="test-key", _env_file=None)
    with TestClient(create_app(settings)) as client:
        client.headers["Authorization"] = "Bearer test-key"
        yield client, requests, configured, replies


def test_tools_require_auth_and_use_closed_operation_list(tools):
    client, requests, _, _ = tools
    assert client.get("/api/v1/knowledge/capabilities", headers={"Authorization": ""}).status_code == 401
    assert client.post("/api/v1/knowledge/operations/arbitrary", json={}).status_code == 404
    assert requests == []
    catalog = client.get("/api/v1/knowledge/capabilities").json()
    assert len(catalog["operations"]) == len(OPERATIONS)
    assert next(o for o in catalog["operations"] if o["id"] == "graph-view")["available"] is False
    assert (
        client.post("/api/v1/knowledge/operations/graph-view", json={"collection_id": "x"}).status_code == 409
    )


def test_parameter_validation_and_form_encoding(tools):
    client, requests, _, _ = tools
    assert client.post("/api/v1/knowledge/operations/qa-single", json={"question": "x"}).status_code == 422
    assert (
        client.post(
            "/api/v1/knowledge/operations/status", json={"resource_ids": ["r"], "action": "delete"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/knowledge/operations/advanced-search",
            json={"collection_id": "c", "query": "x", "top_k": -1},
        ).status_code
        == 422
    )
    result = client.post(
        "/api/v1/knowledge/operations/qa-single",
        json={"collection_id": "c", "question": "Q?", "answer": "A", "metadata": "{}"},
    )
    assert result.status_code == 200
    assert requests[-1].headers["content-type"] == "application/x-www-form-urlencoded"
    assert b"collection_id=c" in requests[-1].content
    assert (
        client.post(
            "/api/v1/knowledge/operations/collection-detail", json={"collection_id": "../bad"}
        ).status_code
        == 422
    )
    assert (
        client.post("/api/v1/knowledge/operations/collection-delete", json={"collection_id": "c"}).status_code
        == 422
    )


def test_batch_selection_transform_and_engine_failure_remains_failure(tools):
    client, requests, _, replies = tools
    response = client.post(
        "/api/v1/knowledge/operations/status", json={"resource_ids": ["r1", "r2"], "action": "disable"}
    )
    assert response.status_code == 200
    assert json.loads(requests[-1].content) == {
        "targets": ["r1", "r2"],
        "target_type": "resource_ids",
        "action": "disable",
    }
    replies["documents/batch-toggle-status"] = httpx.Response(
        200, json={"success": False, "status": 422, "message": "不存在"}
    )
    assert (
        client.post(
            "/api/v1/knowledge/operations/status", json={"resource_ids": ["r"], "action": "disable"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/knowledge/operations/batch-parse",
            json={"collection_id": "c", "urls": ["http://127.0.0.1/private"]},
        ).status_code
        == 422
    )


def test_file_upload_and_authenticated_template_download(tools):
    client, requests, _, replies = tools
    response = client.post(
        "/api/v1/knowledge/uploads/qa-batch",
        data={"fields": '{"collection_id":"c"}'},
        files={"file": ("questions.json", b"[]", "application/json")},
    )
    assert response.status_code == 200
    assert requests[-1].url.path.endswith("/qa/batch")
    assert b'name="collection_id"' in requests[-1].content
    replies["qa/template"] = httpx.Response(
        200, content=b"question,answer", headers={"Content-Type": "text/csv"}
    )
    response = client.get("/api/v1/knowledge/exports/qa-template?format=csv")
    assert response.content == b"question,answer"
    assert "qa-template.csv" in response.headers["content-disposition"]
    assert client.get("/api/v1/knowledge/exports/qa-template?format=exe").status_code == 422


def test_advanced_search_rejects_missing_dependencies_and_local_image_paths(tools):
    client, _, configured, _ = tools
    assert (
        client.post(
            "/api/v1/knowledge/operations/advanced-search",
            json={"collection_id": "c", "search_mode": "semantic", "query": "text"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/knowledge/operations/advanced-search",
            json={"collection_id": "c", "search_mode": "kg", "query": "text"},
        ).status_code
        == 409
    )
    configured["embedding"] = True
    assert (
        client.post(
            "/api/v1/knowledge/operations/advanced-search",
            json={"collection_id": "c", "search_mode": "image", "image": "/etc/passwd"},
        ).status_code
        == 422
    )
