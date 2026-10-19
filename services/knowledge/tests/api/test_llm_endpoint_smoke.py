from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from tests.helpers import (
    REPO_ROOT,
    clear_modules,
    configure_runtime_env,
    load_module_from_path,
    make_stub_module,
)


pytestmark = pytest.mark.api


def _load_llm_router_module(monkeypatch, tmp_path, *, env_overrides: dict[str, object] | None = None):
    runtime_env = {
        "EMBEDDING_PROVIDER": "openai",
        "EMBEDDING_OPENAI_EMBEDDING_MODEL": "text-embedding-3-small",
    }
    runtime_env.update(env_overrides or {})

    configure_runtime_env(
        monkeypatch,
        tmp_path,
        **runtime_env,
    )
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

    return load_module_from_path("_test_llm_router_module", REPO_ROOT / "app/api/v1/llm/router.py")


def _build_app(endpoint_module) -> FastAPI:
    app = FastAPI()
    app.include_router(endpoint_module.router, prefix="/api/v1/llm")
    return app


def test_embed_endpoint_returns_embeddings_with_configured_provider(monkeypatch, tmp_path) -> None:
    endpoint_module = _load_llm_router_module(
        monkeypatch,
        tmp_path,
        env_overrides={
            "EMBEDDING_PROVIDER": "local",
            "EMBEDDING_LOCAL_EMBEDDING_URL": "http://127.0.0.1:8001",
            "EMBEDDING_LOCAL_EMBEDDING_MODEL": "bge-m3",
        },
    )

    class _FakeLLMService:
        async def embed(self, texts, provider=None):  # noqa: ANN001
            assert texts == ["知识库检索请求"]
            assert provider == endpoint_module.LLMProvider.LOCAL
            return [[0.12, 0.34, 0.56]]

    monkeypatch.setattr(endpoint_module, "get_unified_llm_service", lambda: _FakeLLMService())

    with TestClient(_build_app(endpoint_module)) as client:
        response = client.post("/api/v1/llm/embed", json={"text": "知识库检索请求"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["status"] == 200
    assert payload["message"] == "ok"
    assert payload["result"]["embeddings"] == [[0.12, 0.34, 0.56]]
    assert payload["result"]["dimensions"] == 3
    assert payload["result"]["count"] == 1
    assert payload["result"]["provider"] == "local"
    assert payload["result"]["model_name"] == "bge-m3"


def test_embed_endpoint_supports_batch_texts_and_provider_override(monkeypatch, tmp_path) -> None:
    endpoint_module = _load_llm_router_module(monkeypatch, tmp_path)

    class _FakeLLMService:
        async def embed(self, texts, provider=None):  # noqa: ANN001
            assert texts == ["第一段文本", "第二段文本"]
            assert provider == endpoint_module.LLMProvider.OPENAI
            return [[0.1, 0.2], [0.3, 0.4]]

    monkeypatch.setattr(endpoint_module, "get_unified_llm_service", lambda: _FakeLLMService())

    with TestClient(_build_app(endpoint_module)) as client:
        response = client.post(
            "/api/v1/llm/embed",
            json={"texts": ["第一段文本", "第二段文本"], "provider": "openai"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["count"] == 2
    assert payload["result"]["dimensions"] == 2
    assert payload["result"]["provider"] == "openai"


def test_embed_endpoint_rejects_ambiguous_input(monkeypatch, tmp_path) -> None:
    endpoint_module = _load_llm_router_module(monkeypatch, tmp_path)

    with TestClient(_build_app(endpoint_module)) as client:
        response = client.post(
            "/api/v1/llm/embed",
            json={"text": "单条文本", "texts": ["另一条文本"]},
        )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["status"] == 400
    assert "不能同时传入" in payload["message"]


def test_embed_endpoint_wraps_backend_failure(monkeypatch, tmp_path) -> None:
    endpoint_module = _load_llm_router_module(monkeypatch, tmp_path)

    class _BrokenLLMService:
        async def embed(self, texts, provider=None):  # noqa: ANN001, ARG002
            raise RuntimeError("embedding backend unavailable")

    monkeypatch.setattr(endpoint_module, "get_unified_llm_service", lambda: _BrokenLLMService())

    with TestClient(_build_app(endpoint_module)) as client:
        response = client.post("/api/v1/llm/embed", json={"text": "测试文本"})

    assert response.status_code == 500
    payload = response.json()
    assert payload["success"] is False
    assert payload["status"] == 500
    assert "文本向量化失败" in payload["message"]
