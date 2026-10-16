import asyncio
import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from quill.config import Settings
from quill.file_import import ImportError, extract_text
from quill.store import Store


class MetadataRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    tags: list[str] = Field(default_factory=list, max_length=20)


class CollectionMetadata(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field("", max_length=1000)


def knowledge_router(config: Settings, store: Store) -> APIRouter:
    router = APIRouter(prefix="/api/v1/knowledge", tags=["Knowledge workspace"])

    @router.get("/overview")
    async def overview(request: Request):
        result = await request.app.state.knowledge.request("quill/overview", {})
        return result["result"]

    @router.patch("/collections/{collection_id}")
    async def update_collection(request: Request, collection_id: str, body: CollectionMetadata):
        if not body.name.strip():
            raise HTTPException(422, "知识库名称不能为空。")
        result = await request.app.state.knowledge.request(
            "collections/update",
            {
                "collection_id": collection_id,
                **body.model_dump(),
            },
        )
        return result["result"]

    @router.get("/resources")
    async def resources(
        request: Request,
        collection_id: str,
        query: str = Query("", max_length=200),
        kind: str = Query("all", pattern="^(all|pdf|docx|md|text|csv|json)$"),
        page: int = Query(0, ge=0),
        size: int = Query(20, ge=1, le=100),
    ):
        result = await request.app.state.knowledge.request(
            "quill/resources/list",
            {
                "collection_id": collection_id,
                "query": query,
                "kind": kind,
                "page": page,
                "size": size,
            },
        )
        items = result["result"]
        for item in items["items"]:
            item["has_original"] = bool(store.knowledge_file(item["resource_id"]))
        return items

    @router.get("/resources/{resource_id}")
    async def resource(request: Request, resource_id: str):
        result = await request.app.state.knowledge.request(
            "quill/resources/get", {"resource_id": resource_id}
        )
        body = result["result"]
        body["has_original"] = bool(store.knowledge_file(resource_id))
        return body

    @router.patch("/resources/{resource_id}")
    async def update_resource(request: Request, resource_id: str, body: MetadataRequest):
        if not body.title.strip():
            raise HTTPException(422, "资料名称不能为空。")
        result = await request.app.state.knowledge.request(
            "quill/resources/update",
            {
                "resource_id": resource_id,
                **body.model_dump(),
            },
        )
        return result["result"]

    @router.delete("/resources/{resource_id}")
    async def delete_resource(request: Request, resource_id: str):
        result = await request.app.state.knowledge.request(
            "quill/resources/delete", {"resource_id": resource_id}
        )
        store.delete_knowledge_file(resource_id)
        return result["result"]

    @router.post("/resources/{resource_id}/reindex")
    async def reindex(request: Request, resource_id: str):
        result = await request.app.state.knowledge.request(
            "quill/resources/reindex", {"resource_id": resource_id}
        )
        return result["result"]

    @router.get("/resources/{resource_id}/download")
    async def download(request: Request, resource_id: str):
        await request.app.state.knowledge.request("quill/resources/get", {"resource_id": resource_id})
        metadata = store.knowledge_file(resource_id)
        if not metadata:
            raise HTTPException(404, "此资料没有保存原文件，可在内容预览中复制文字。")
        path = store.root / "knowledge-files" / metadata["stored_name"]
        if not path.is_file():
            raise HTTPException(404, "原文件不存在，请重新导入。")
        return FileResponse(path, filename=metadata["name"])

    @router.post("/import")
    async def import_file(request: Request, collection_id: str = Form(...), file: UploadFile = File(...)):
        name = Path((file.filename or "").replace("\\", "/")).name
        if not name:
            raise HTTPException(400, "请选择需要导入的文件。")
        limit = config.max_upload_mb * 1024 * 1024
        data = await file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"单个文件不能超过 {config.max_upload_mb} MB。")
        try:
            text = await asyncio.to_thread(extract_text, data, name)
        except ImportError as exc:
            raise HTTPException(422, str(exc)) from exc
        stored_name = uuid4().hex + Path(name).suffix.lower()
        path = store.root / "knowledge-files" / stored_name
        path.write_bytes(data)
        try:
            result = await request.app.state.knowledge.request(
                "quill/text",
                {
                    "collection_id": collection_id,
                    "title": Path(name).stem[:255],
                    "content": text,
                    "file_name": name[:255],
                    "file_size": len(data),
                    "mime_type": file.content_type,
                    "file_sha256": hashlib.sha256(data).hexdigest(),
                },
            )
            body = result["result"]
            saved = store.knowledge_file(body["resource_id"], {"stored_name": stored_name, "name": name})
            if saved["stored_name"] != stored_name:
                path.unlink(missing_ok=True)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return {**body, "name": name, "characters": len(text)}

    return router
