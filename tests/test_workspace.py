import io
import json

import httpx
import pytest
from docx import Document
from fastapi.testclient import TestClient

from quill.config import Settings
from quill.main import create_app
from quill.providers import KnowledgeClient, LLMClient, ProviderError
from quill.store import Store


@pytest.fixture
def client(tmp_path):
    settings = Settings(data_dir=tmp_path, api_key="test-key", llm_model="test-model", _env_file=None)
    with TestClient(create_app(settings)) as client:
        client.headers["Authorization"] = "Bearer test-key"
        yield client


def upload(client, name="方案"):
    doc = Document()
    p = doc.add_paragraph()
    p.add_run("项目：{{项").bold = True
    p.add_run("目名称}}；负责人：【负责人】")
    doc.add_table(rows=1, cols=1).cell(0, 0).text = "{{项目名称}}"
    data = io.BytesIO()
    doc.save(data)
    return client.post(
        "/api/upload-template",
        data={"template_name": name},
        files={"file": ("template.docx", data.getvalue())},
    )


def test_auth_and_unknown_api(client):
    assert client.get("/health", headers={"Authorization": ""}).status_code == 200
    assert client.get("/api/templates", headers={"Authorization": ""}).status_code == 401
    assert client.get("/api/missing").status_code == 404


@pytest.mark.parametrize("access_key", ["", "test-key"])
def test_optional_workspace_access_covers_upload_render_and_download(tmp_path, access_key):
    settings = Settings(data_dir=tmp_path, api_key=access_key, _env_file=None)
    with TestClient(create_app(settings)) as local:
        if access_key:
            assert local.get("/api/v1/status").status_code == 401
            assert local.get("/api/templates").status_code == 401
            local.headers["Authorization"] = f"Bearer {access_key}"
        status = local.get("/api/v1/status")
        assert status.status_code == 200
        assert status.json()["authentication"] is bool(access_key)
        assert upload(local, "示例 · 访问模式验收").status_code == 200
        rendered = local.post(
            "/api/generate-from-template",
            data={
                "template_name": "示例 · 访问模式验收",
                "data": json.dumps({"项目名称": "本地验收", "负责人": "示例人员"}),
            },
        )
        assert rendered.status_code == 200
        url = "/download/" + rendered.json()["filename"]
        download = local.get(url)
        assert download.status_code == 200
        document = Document(io.BytesIO(download.content))
        assert "本地验收" in document.paragraphs[0].text
        assert "示例人员" in document.paragraphs[0].text
        if access_key:
            assert local.get(url, headers={"Authorization": ""}).status_code == 401
            assert local.get(url, headers={"Authorization": "Bearer wrong-key"}).status_code == 401
        else:
            # An old tab's saved token must not prevent key-free local use.
            assert local.get(url, headers={"Authorization": "Bearer old-key"}).status_code == 200


def test_template_render_roundtrip_and_persistence(client):
    response = upload(client)
    assert response.status_code == 200, response.text
    assert {v["name"] for v in response.json()["variables"]} == {"项目名称", "负责人"}
    assert upload(client).status_code == 409
    template = client.get("/api/templates").json()["templates"][0]
    assert template["name"] == "方案"
    sources = [{"title": "项目事实", "resource_id": "res-1"}]
    result = client.post(
        "/api/generate-from-template",
        data={
            "template_name": "方案",
            "data": json.dumps({"项目名称": "测试工程", "负责人": "张三"}),
            "sources": json.dumps(sources),
        },
    )
    assert result.status_code == 200, result.text
    filename = result.json()["filename"]
    download = client.get(f"/download/{filename}")
    doc = Document(io.BytesIO(download.content))
    assert "测试工程" in doc.paragraphs[0].text
    assert "张三" in doc.paragraphs[0].text
    assert doc.tables[0].cell(0, 0).text == "测试工程"
    assert doc.paragraphs[0].runs[0].bold is True
    assert client.get(f"/api/v1/artifacts/{filename}/sources").json()["sources"] == sources
    reopened = Store(client.app.state.store.root)
    assert reopened.template("方案")["id"] == template["id"]
    assert reopened.artifact(filename)["sources"] == sources
    assert client.get("/download/not-a-registered-file.docx").status_code == 404


def test_invalid_upload_and_values(client):
    assert client.post("/api/upload-template", files={"file": ("x.doc", b"bad")}).status_code == 400
    assert client.post("/api/upload-template", files={"file": ("x.docx", b"bad")}).status_code == 400
    upload(client)
    assert (
        client.post("/api/generate-from-template", data={"template_name": "方案", "data": "[]"}).status_code
        == 400
    )
    assert (
        client.post(
            "/api/ai-fill-template-variables", json={"template_name": "方案", "enable_rag": True}
        ).status_code
        == 400
    )


async def test_knowledge_contract_and_pagination():
    seen = []

    def handle(request):
        seen.append(json.loads(request.content))
        assert request.headers["Authorization"] == "Bearer engine-token"
        if request.url.path.endswith("collections/search"):
            page = seen[-1]["pageIndex"]
            if page == 0:
                return httpx.Response(
                    200,
                    json={
                        "result": {"data": [{"id": str(i), "name": str(i)} for i in range(100)], "total": 101}
                    },
                )
            return httpx.Response(
                200, json={"result": {"data": [{"id": "last", "name": "最后一个"}], "total": 101}}
            )
        assert seen[-1]["collection_id"] == ["last"]
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "resource_id": "r1",
                        "content_id": "c1",
                        "content": "参考事实",
                        "title": "技术资料",
                        "collection_id": "last",
                        "version": 2,
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        provider = KnowledgeClient(Settings(knowledge_token="engine-token", _env_file=None), client)
        assert len(await provider.collections()) == 101
        sources = await provider.search("事实", ["last"])
        assert sources[0]["resource_id"] == "r1"
        assert sources[0]["version"] == 2


async def test_provider_failure_never_becomes_empty_success():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(503))) as client:
        provider = KnowledgeClient(Settings(_env_file=None), client)
        with pytest.raises(ProviderError):
            await provider.collections()
        llm = LLMClient(Settings(llm_model="model", _env_file=None), client)
        with pytest.raises(ProviderError):
            await llm.chat("system", "prompt")


@pytest.mark.parametrize("effort", ["", "none"])
async def test_keyless_model_contract_and_optional_reasoning(effort):
    def respond(request):
        assert "Authorization" not in request.headers
        body = json.loads(request.content)
        if effort:
            assert body["reasoning_effort"] == effort
        else:
            assert "reasoning_effort" not in body
        return httpx.Response(200, json={"choices": [{"message": {"content": "本机模型验收成功"}}]})

    settings = Settings(llm_model="local-model", llm_reasoning_effort=effort, _env_file=None)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        assert await LLMClient(settings, client).chat("验收", "测试") == "本机模型验收成功"


async def test_model_reasoning_without_a_final_answer_is_not_success():
    response = {"choices": [{"message": {"content": "", "reasoning": "尚未完成的推理"}}]}
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=response))) as c:
        with pytest.raises(ProviderError):
            await LLMClient(Settings(llm_model="local-model", _env_file=None), c).chat("验收", "测试")


async def test_generation_sections_sources_and_failure(tmp_path):
    from quill.generation import GenerationService

    class Knowledge:
        async def search(self, query, collections):
            return [{"title": "证据", "content": "工期30天", "resource_id": "r1"}]

    class Model:
        async def chat(self, system, prompt):
            return "根据资料，工期为30天 [1]。"

    store = Store(tmp_path)
    service = GenerationService(store, Knowledge(), Model())
    job = store.new_job({"topic": "实施方案", "sections": ["背景", "计划"], "collection_ids": ["c1"]})
    await service.run(job["id"])
    result = store.job(job["id"])
    assert result["status"] == "completed"
    assert result["progress"] == 100
    assert [s["section"] for s in result["sources"]] == ["背景", "计划"]
    assert (tmp_path / "downloads" / result["filename"]).is_file()
    assert store.artifact(result["filename"])["job_id"] == job["id"]

    class EmptyKnowledge:
        async def search(self, query, collections):
            return []

    service.knowledge = EmptyKnowledge()
    failed = store.new_job({"topic": "实施方案", "collection_ids": ["c1"]})
    await service.run(failed["id"])
    assert store.job(failed["id"])["status"] == "failed"
    assert "没有检索到" in store.job(failed["id"])["error"]


def test_restart_recovers_all_pending_jobs(tmp_path):
    store = Store(tmp_path)
    one = store.new_job({"topic": "one"})
    two = store.new_job({"topic": "two"})
    two.update(status="running", content="已生成片段")
    store.save_job(two)
    store.recover()
    assert store.job(one["id"])["status"] == "interrupted"
    assert store.job(two["id"])["content"] == "已生成片段"


def test_template_values_are_not_recursively_expanded(tmp_path):
    from quill.legacy.template import BaseTemplatesGenerator

    renderer = BaseTemplatesGenerator(tmp_path)
    document = Document()
    paragraph = document.add_paragraph("{{变量}} 和 {{变量}}")
    renderer._replace_text_in_paragraph(paragraph, {"变量": "{{变量}}保留"})
    assert paragraph.text == "{{变量}}保留 和 {{变量}}保留"


def test_word_export_contains_a_real_toc_field(tmp_path):
    from quill.legacy.document import DocumentGenerator

    path = DocumentGenerator(tmp_path).export_to_doc("# 报告\n\n## 背景\n\n正文", "fulltext")
    document = Document(path)
    assert document._element.xpath(".//w:fldSimple")
    assert "TOC" not in "\n".join(p.text for p in document.paragraphs)


def test_job_enqueued_and_worker_completes(client):
    class Model:
        async def chat(self, system, prompt):
            return "已生成的文档内容。"

    client.app.state.generation.llm = Model()
    job = client.post("/api/v1/documents/jobs", json={"topic": "工作报告", "reference": "已完成部署"})
    assert job.status_code == 202
    # The worker runs on the ASGI lifespan event loop; synchronize against its queue.
    client.portal.call(client.app.state.generation.queue.join)
    result = client.get("/api/v1/documents/jobs/" + job.json()["id"]).json()
    assert result["status"] == "completed"
    assert client.get("/download/" + result["filename"]).status_code == 200
