"""A deliberately small, fail-closed knowledge contract for anonymous demos.

The internal engine remains private. Ownership comes from a server-side manifest,
never from a collection/resource identifier supplied by the browser.
"""

import json
from uuid import uuid4

from quill.providers import KnowledgeClient, ProviderError


class DemoKnowledgeClient(KnowledgeClient):
    def __init__(self, settings, client):
        super().__init__(settings, client)
        self.manifest = settings.data_dir / "demo-collections.json"
        self.owned = json.loads(self.manifest.read_text()) if self.manifest.exists() else {}
        self.prefix = f"demo_{settings.data_dir.name}_"

    def save(self):
        pending = self.manifest.with_suffix(".tmp")
        pending.write_text(json.dumps(self.owned, ensure_ascii=False))
        pending.replace(self.manifest)

    def require_collection(self, value):
        if not isinstance(value, str) or value not in self.owned:
            raise ProviderError("知识库不存在或不属于当前演示会话。", 404)

    async def collections(self):
        return [{"id": cid, "name": item["name"]} for cid, item in self.owned.items() if not item.get("pending")]

    async def request(self, path, payload):
        payload = payload.copy()
        if path == "collections":
            if len(self.owned) >= 3:
                raise ProviderError("每次演示最多创建 3 个知识库。", 429)
            cid = uuid4().hex
            name = payload["name"]
            # Record first so an interrupted provider response cannot orphan data
            # outside the expiry cleanup's ownership manifest.
            self.owned[cid] = {"name": name, "description": payload.get("description", ""), "pending": True}
            self.save()
            result = await super().request(path, {
                **payload, "collection_id": cid, "name": self.prefix + name[:50],
            })
            self.owned[cid].pop("pending")
            self.save()
            result["result"]["name"] = name
            return result
        if path == "quill/overview":
            result = (await super().request(path, payload))["result"]
            items = [c for c in result["collections"] if c["id"] in self.owned]
            for item in items:
                item.update(self.owned[item["id"]])
            return {"success": True, "result": {
                "collections": items,
                **{key: sum(c[key] for c in items) for key in (
                    "document_count", "characters", "indexed_count",
                )},
            }}
        if path == "search/unified":
            ids = payload.get("collection_id")
            if not isinstance(ids, list) or not ids:
                raise ProviderError("请选择当前会话的知识库。", 422)
            for cid in ids:
                self.require_collection(cid)
            if payload.get("search_mode") not in {"keyword", "file", "intelligent"}:
                raise ProviderError("公开演示未配置 Embedding；请使用关键词或文件检索。", 409)
            # No model/network lookups or automatic graph expansion in this mode.
            payload.update(search_mode="keyword", answer_with_file=False)
            result = await super().request(path, payload)
            if any(item.get("collection_id") not in ids for item in result.get("results", [])):
                raise ProviderError("知识引擎返回了超出当前会话范围的结果。", 502)
            return result
        if path in {"collections/update", "quill/resources/list", "quill/text"}:
            cid = payload.get("collection_id")
            self.require_collection(cid)
            if path == "collections/update":
                name = payload["name"]
                result = await super().request(path, {**payload, "name": self.prefix + name[:50]})
                self.owned[cid].update(name=name, description=payload.get("description", ""))
                self.save()
                result["result"]["name"] = name
                return result
            if path == "quill/text":
                overview = (await self.request("quill/overview", {}))["result"]
                if overview["document_count"] >= 20 or overview["characters"] + len(payload["content"]) > 500000:
                    raise ProviderError("每次演示最多保存 20 份资料、合计 50 万字符。", 429)
                if len(payload["content"]) > 50000:
                    raise ProviderError("演示站单份资料最多 5 万字符，请拆分导入。", 413)
            return await super().request(path, payload)
        if path in {
            "quill/resources/get", "quill/resources/update", "quill/resources/delete",
            "quill/resources/reindex", "quill/resources/chunks",
        }:
            detail = (await super().request("quill/resources/get", {
                "resource_id": payload.get("resource_id"),
            }))["result"]
            self.require_collection(detail.get("collection_id"))
            if path == "quill/resources/reindex":
                raise ProviderError("演示站未配置 Embedding，无需重建向量索引。", 409)
            return await super().request(path, payload)
        raise ProviderError("此引擎操作未向公开演示开放，请使用自部署版本。", 403)

    async def cleanup(self):
        for cid in list(self.owned):
            try:
                await super().request("collections/delete", {"collection_id": cid})
            except ProviderError as exc:
                if exc.status_code != 404:
                    raise
            self.owned.pop(cid)
            self.save()
