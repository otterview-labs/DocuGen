"""Authenticated, allowlisted protocol bridge for knowledge workbench actions."""

import json
import re
from dataclasses import asdict
from uuid import uuid4

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response

from quill.knowledge_operations import OPERATIONS
from quill.providers import ProviderError


def tools_router(config, store):
    router = APIRouter(prefix="/api/v1/knowledge", tags=["Knowledge tools"])

    async def engine(request, path, method="GET", **kwargs):
        provider = request.app.state.knowledge
        headers = {"Authorization": f"Bearer {config.knowledge_token}"} if config.knowledge_token else {}
        try:
            response = await provider.client.request(
                method,
                f"{config.knowledge_url.rstrip('/')}/api/v1/rag/{path}",
                headers=headers,
                timeout=180,
                **kwargs,
            )
        except httpx.HTTPError as exc:
            raise ProviderError("知识引擎连接失败，请检查服务状态后重试。") from exc
        if not response.is_success:
            try:
                data = response.json()
                detail = data.get("detail") or data.get("message") or "知识引擎请求失败。"
            except ValueError:
                detail = "知识引擎请求失败，请检查服务日志。"
            raise ProviderError(str(detail), response.status_code)
        return response

    def decoded(response):
        try:
            data = response.json()
        except ValueError:
            raise ProviderError("知识引擎返回了无法读取的结果。") from None
        if isinstance(data, dict) and (
            data.get("success") is False or (isinstance(data.get("status"), int) and data["status"] >= 400)
        ):
            status = data.get("status", 502)
            raise ProviderError(
                str(data.get("message") or data.get("error") or "知识引擎未完成操作。"),
                status if isinstance(status, int) and 400 <= status < 600 else 502,
            )
        return data

    async def catalog(request):
        caps = decoded(await engine(request, "quill/capabilities"))
        operations = []
        for key, operation in OPERATIONS.items():
            path = "/api/v1/rag/" + operation.path
            registered = operation.method in caps["paths"].get(path, [])
            reason = "" if registered else "当前引擎未加载此功能，请检查可选依赖与启动日志。"
            for dependency in operation.dependency.split("_"):
                if dependency and not caps.get("configured", {}).get(dependency):
                    reason = {
                        "llm": "尚未配置知识引擎生成模型。",
                        "graph": "尚未启用图数据库。",
                        "embedding": "尚未配置 Embedding 模型。",
                    }[dependency]
                    break
            operations.append(
                {"id": key, **asdict(operation), "available": registered and not reason, "reason": reason}
            )
        return {
            "operations": operations,
            "configured": caps.get("configured", {}),
            "vector_backend": caps.get("vector_backend"),
            "registration_checked": True,
        }

    @router.get("/capabilities")
    async def capabilities(request: Request):
        return await catalog(request)

    async def require_operation(request, key, file=False):
        operation = OPERATIONS.get(key)
        if not operation or (operation.encoding == "file") != file:
            raise HTTPException(404, "未找到此知识库操作。")
        item = next(item for item in (await catalog(request))["operations"] if item["id"] == key)
        if not item["available"]:
            raise HTTPException(409, item["reason"])
        return operation

    def validate(operation, payload):
        fields = {item["key"]: item for item in operation.fields}
        if set(payload) - fields.keys() - {"confirmed"}:
            raise HTTPException(422, "包含不支持的操作参数。")
        for key, item in fields.items():
            value = payload.get(key)
            if item.get("required") and (
                value is None or (isinstance(value, str) and not value.strip()) or value == []
            ):
                raise HTTPException(422, f"请填写{item['label']}。")
            if value is None:
                continue
            if item["kind"] == "number":
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not item.get("min", float("-inf")) <= value <= item.get("max", float("inf"))
                ):
                    raise HTTPException(422, f"{item['label']}超出允许范围。")
            elif item["kind"] in {"lines", "resources"} and (
                not isinstance(value, list) or len(value) > 1000 or any(not isinstance(v, str) for v in value)
            ):
                raise HTTPException(422, f"请检查{item['label']}。")
            elif item["kind"] == "boolean" and not isinstance(value, bool):
                raise HTTPException(422, f"请检查{item['label']}。")
            elif item["kind"] == "select" and value not in [o[0] for o in item["options"]]:
                raise HTTPException(422, f"请检查{item['label']}。")
        if operation.destructive and payload.pop("confirmed", False) is not True:
            raise HTTPException(422, "请先确认删除知识库及其资料。")
        if len(json.dumps(payload, ensure_ascii=False)) > 4 * 1024 * 1024:
            raise HTTPException(413, "操作参数过大。")
        return payload

    @router.post("/operations/{key}")
    async def execute(request: Request, key: str, payload: dict):
        operation = await require_operation(request, key)
        payload = validate(operation, payload.copy())
        if key == "batch-parse":
            urls = payload.pop("urls")
            # Parsing local staged uploads avoids giving the engine an arbitrary network fetch target.
            if any(not re.fullmatch(r"/uploads/[A-Za-z0-9_.-]+", url) for url in urls):
                raise HTTPException(422, "请先上传文件，再使用返回的 /uploads/ 文件地址。")
            payload = {
                "resources": [
                    {
                        "id": uuid4().hex,
                        "classifyId": payload["collection_id"],
                        "name": url.rsplit("/", 1)[-1],
                        "description": "",
                        "type": "file",
                        "content": {"url": url},
                    }
                    for url in urls
                ]
            }
        if key == "process-upload" and not re.fullmatch(
            r"/uploads/[A-Za-z0-9_.-]+", str(payload.get("url", ""))
        ):
            raise HTTPException(422, "请选择已上传的文件地址。")
        if key == "analyze":
            payload["resource_id"] = payload.pop("resource_ids")
        if key == "status":
            payload["targets"] = payload.pop("resource_ids")
            payload["target_type"] = "resource_ids"
        if key == "advanced-search":
            configured = (await catalog(request))["configured"]
            mode = payload.get("search_mode", "intelligent")
            if (mode == "kg" or payload.get("enable_graph_expansion")) and not configured.get("graph"):
                raise HTTPException(409, "尚未启用图数据库，请使用关键词或文件检索。")
            if mode == "semantic" and not configured.get("embedding"):
                raise HTTPException(409, "尚未配置 Embedding 模型，请先使用关键词检索。")
            if payload.get("answer_with_file") and not configured.get("llm"):
                raise HTTPException(409, "尚未配置知识引擎生成模型，可先关闭文件回答进行检索。")
            image = payload.get("image")
            if image and (
                not isinstance(image, str) or not re.match(r"^data:image/(png|jpeg|webp|gif);base64,", image)
            ):
                raise HTTPException(422, "请上传 PNG、JPEG、WebP 或 GIF 查询图片。")
            payload["collection_id"] = [payload["collection_id"]]
        path = operation.path
        if "{collection_id}" in path:
            cid = payload.pop("collection_id")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(cid)):
                raise HTTPException(422, "知识库编号无效。")
            path = path.replace("{collection_id}", cid)
        original_ids = []
        if key == "collection-delete":
            for page in range(100):
                result = await request.app.state.knowledge.request(
                    "quill/resources/list",
                    {"collection_id": payload["collection_id"], "page": page, "size": 100},
                )
                batch = result["result"]["items"]
                original_ids.extend(item["resource_id"] for item in batch)
                if len(batch) < 100:
                    break
            else:
                raise HTTPException(409, "资料数量超过当前删除上限，请先分批移除资料。")
        kwargs = (
            {"params": payload}
            if operation.method == "GET"
            else {"data" if operation.encoding == "form" else "json": payload}
        )
        result = decoded(await engine(request, path, operation.method, **kwargs))
        if key == "collection-delete":
            for rid in original_ids:
                store.delete_knowledge_file(rid)
        return result

    @router.post("/uploads/{key}")
    async def upload(request: Request, key: str, file: UploadFile = File(...), fields: str = Form("{}")):
        operation = await require_operation(request, key, file=True)
        try:
            payload = json.loads(fields)
            if not isinstance(payload, dict):
                raise ValueError()
        except ValueError:
            raise HTTPException(422, "上传参数格式不正确。") from None
        validate(operation, payload)
        limit = config.max_upload_mb * 1024 * 1024
        data = await file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"文件不能超过 {config.max_upload_mb} MB。")
        return decoded(
            await engine(
                request,
                operation.path,
                "POST",
                data=payload,
                files={
                    "file": (file.filename or "upload", data, file.content_type or "application/octet-stream")
                },
            )
        )

    @router.get("/exports/qa-template")
    async def export_template(request: Request, format: str = Query("json", pattern="^(json|csv)$")):
        response = await engine(request, "qa/template", params={"format": format})
        return Response(
            response.content,
            media_type=response.headers.get("content-type", "application/octet-stream"),
            headers={"Content-Disposition": f'attachment; filename="qa-template.{format}"'},
        )

    return router
