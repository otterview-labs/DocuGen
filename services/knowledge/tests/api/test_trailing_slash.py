from __future__ import annotations

import pytest
from fastapi import APIRouter, FastAPI, Request
from starlette.testclient import TestClient

pytestmark = pytest.mark.api


def _build_app_with_strip_middleware() -> FastAPI:
    """复刻 main.py 的 strip_trailing_slash middleware + 两种路由形态（"" 与 /xxx）。"""

    app = FastAPI()

    @app.middleware("http")
    async def strip_trailing_slash(request: Request, call_next):
        path = request.scope.get("path", "")
        if (
            len(path) > 1
            and path.endswith("/")
            and (path.startswith("/api/") or path.startswith("/knowledge/"))
        ):
            request.scope["path"] = path.rstrip("/")
        return await call_next(request)

    r_coll = APIRouter()

    @r_coll.post("")
    def coll():
        return {"coll": "ok"}

    app.include_router(r_coll, prefix="/api/v1/rag/collections")

    r_doc = APIRouter()

    @r_doc.post("/batch-delete")
    def bd():
        return {"bd": "ok"}

    app.include_router(r_doc, prefix="/api/v1/rag/documents")

    return app


def test_trailing_slash_on_no_slash_route_does_not_307() -> None:
    """带尾斜杠调无尾斜杠路由（如 batch-delete/），应透明命中，不返回 307。"""
    with TestClient(_build_app_with_strip_middleware(), follow_redirects=False) as client:
        response = client.post("/api/v1/rag/documents/batch-delete/")
    assert response.status_code == 200


def test_trailing_slash_on_empty_route_still_hits() -> None:
    """collections 用 "" 路由（无尾斜杠），前端带/不带斜杠都应命中。"""
    app = _build_app_with_strip_middleware()
    with TestClient(app, follow_redirects=False) as client:
        assert client.post("/api/v1/rag/collections/").status_code == 200
        assert client.post("/api/v1/rag/collections").status_code == 200


def test_no_slash_paths_still_work() -> None:
    app = _build_app_with_strip_middleware()
    with TestClient(app) as client:
        assert client.post("/api/v1/rag/documents/batch-delete").status_code == 200
        assert client.post("/api/v1/rag/collections").status_code == 200
