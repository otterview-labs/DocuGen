import io
import json
import time

import httpx
import pytest
from docx import Document
from fastapi.testclient import TestClient

from quill.config import Settings
from quill.demo import DemoGateway
from quill.demo_knowledge import DemoKnowledgeClient
from quill.providers import ProviderError


@pytest.fixture
def demo(tmp_path):
    frontend = tmp_path / "frontend"
    (frontend / "assets").mkdir(parents=True)
    (frontend / "assets" / "test.js").write_text("// synthetic static fixture")
    return DemoGateway(Settings(
        data_dir=tmp_path, frontend_dir=frontend, demo_cookie_secure=False, _env_file=None,
    ))


def test_static_assets_do_not_create_sessions_and_unknown_assets_are_404(demo):
    with TestClient(demo) as client:
        assert client.get("/assets/test.js").status_code == 200
        assert client.get("/assets/missing.js").status_code == 404
        assert len(demo.visitors) == 0
        assert not client.cookies


def test_https_demo_cookie_uses_host_prefix(tmp_path):
    app = DemoGateway(Settings(data_dir=tmp_path, demo_cookie_secure=True, _env_file=None))
    with TestClient(app, base_url="https://demo.test") as client:
        response = client.get("/api/v1/status")
        assert client.cookies.get("__Host-docugen-demo")
        assert "Secure" in response.headers["set-cookie"]
        assert len(client.get("/api/templates").json()["templates"]) == 0
        assert len(app.visitors) == 1


def test_anonymous_visitors_cannot_read_templates_downloads_or_jobs(demo):
    with TestClient(demo) as client:
        a = client.get("/api/v1/status")
        assert a.json()["workspace"] == "ephemeral-browser-demo"
        assert not a.json()["authentication"] and not a.json()["model_configured"]
        cookie_a = client.cookies.get("docugen-demo")
        assert "HttpOnly" in a.headers["set-cookie"] and "SameSite=Strict" in a.headers["set-cookie"]
        doc = Document()
        doc.add_paragraph("{{项目名称}}")
        data = io.BytesIO()
        doc.save(data)
        uploaded = client.post("/api/upload-template", files={"file": ("a.docx", data.getvalue())})
        assert uploaded.status_code == 200, uploaded.text
        rendered = client.post("/api/generate-from-template", data={
            "template_name": "a", "data": json.dumps({"项目名称": "仅访客甲可见"}),
        })
        filename = rendered.json()["filename"]
        assert client.get("/download/" + filename).status_code == 200
        sid = demo.session_id(cookie_a)
        job = demo.visitors[sid].app.state.store.new_job({"topic": "甲的主题"})
        client.cookies.clear()
        assert client.get("/api/templates").json()["templates"] == []
        cookie_b = client.cookies.get("docugen-demo")
        assert cookie_a != cookie_b
        assert client.get("/download/" + filename).status_code == 404
        assert client.get("/api/v1/artifacts/" + filename + "/sources").status_code == 404
        assert client.get("/api/v1/documents/jobs/" + job["id"]).status_code == 404
        assert client.get("/api/v1/documents/jobs").json()["jobs"] == []
        client.cookies.set("docugen-demo", cookie_a, domain="testserver.local", path="/")
        assert len(client.get("/api/templates").json()["templates"]) == 1
        assert client.get("/download/" + filename).status_code == 200


def test_demo_rejects_cross_site_oversized_and_excess_sessions(demo):
    demo.max_sessions = 1
    with TestClient(demo) as client:
        assert client.post("/api/upload-template", headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.post("/api/upload-template", content=b"a" * (demo.body_limit + 1)).status_code == 413
        assert client.get("/api/templates").status_code == 200
        client.cookies.clear()
        assert client.get("/api/templates").status_code == 429


def test_demo_cookie_forgery_expiry_and_persistent_write_limit(demo):
    with TestClient(demo) as client:
        client.get("/api/templates")
        token = client.cookies.get("docugen-demo")
        assert demo.session_id(token + "forged") is None
        sid = demo.session_id(token)
        visitor = demo.visitors[sid]
        visitor.writes = 100
        assert client.post("/api/generate-from-template", data={}).status_code == 429
        meta = demo.root / sid / "session.json"
        meta.write_text(json.dumps({"created": time.time() - 7201, "writes": 100}))
        assert client.get("/api/templates").status_code == 410


@pytest.mark.asyncio
async def test_knowledge_ownership_search_overview_and_limits(tmp_path):
    calls = []

    def engine(request):
        body = json.loads(request.content)
        path = request.url.path.rsplit("/rag/", 1)[-1]
        calls.append((path, body))
        if path == "collections":
            return httpx.Response(200, json={"result": {"id": body["collection_id"], "name": body["name"]}})
        if path == "quill/resources/get":
            return httpx.Response(200, json={"result": {"collection_id": "other", "resource_id": "secret"}})
        if path == "quill/overview":
            return httpx.Response(200, json={"result": {"collections": [
                {"id": cid, "name": "internal", "document_count": 0, "characters": 0, "indexed_count": 0}
                for cid in [*provider.owned, "other"]
            ]}})
        if path == "search/unified":
            return httpx.Response(200, json={"results": [{"collection_id": "other", "content": "private"}]})
        return httpx.Response(200, json={"result": {}})

    config = Settings(data_dir=tmp_path, _env_file=None)
    async with httpx.AsyncClient(transport=httpx.MockTransport(engine)) as client:
        provider = DemoKnowledgeClient(config, client)
        created = await provider.request("collections", {"name": "同名资料"})
        cid = created["result"]["id"]
        assert created["result"]["name"] == "同名资料"
        assert calls[-1][1]["name"].startswith("demo_")
        assert (await provider.collections()) == [{"id": cid, "name": "同名资料"}]
        overview = await provider.request("quill/overview", {})
        assert [c["id"] for c in overview["result"]["collections"]] == [cid]
        for path, body in [
            ("quill/resources/list", {"collection_id": "other"}),
            ("quill/resources/delete", {"resource_id": "secret"}),
            ("search/unified", {"collection_id": ["other"]}),
            ("collections/delete", {"collection_id": "other"}),
            ("quill/text", {"collection_id": cid, "content": "a" * 50001}),
        ]:
            with pytest.raises(ProviderError):
                await provider.request(path, body)
        with pytest.raises(ProviderError, match="超出"):
            await provider.search("test", [cid], "keyword")
        # Access control is restored from the server manifest after restart.
        restored = DemoKnowledgeClient(config, client)
        assert await restored.collections() == await provider.collections()


@pytest.mark.asyncio
async def test_expiry_closes_workspace_and_removes_owned_engine_data(demo, monkeypatch):
    cleaned = []

    async def cleanup(self):
        cleaned.append(self.settings.data_dir.name)

    monkeypatch.setattr(DemoKnowledgeClient, "cleanup", cleanup)
    sid = "a" * 32
    visitor = await demo.open_visitor(sid)
    meta = demo.root / sid / "session.json"
    meta.write_text(json.dumps({"created": time.time() - 7201}))
    await demo.reap_once()
    assert cleaned == [sid]
    assert sid not in demo.visitors and not meta.parent.exists()
    assert visitor.app.state.generation.queue.empty()
