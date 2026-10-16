import httpx

from quill.config import Settings


class ProviderError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class KnowledgeClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings, self.client = settings, client

    async def request(self, path: str, payload: dict) -> dict:
        headers = {}
        if self.settings.knowledge_token:
            headers["Authorization"] = f"Bearer {self.settings.knowledge_token}"
        try:
            response = await self.client.post(
                f"{self.settings.knowledge_url.rstrip('/')}/api/v1/rag/{path}",
                json=payload,
                headers=headers,
                timeout=120,
            )
            if response.status_code in {400, 404, 409, 422, 502}:
                body = response.json()
                detail = body.get("detail") or body.get("message")
                if isinstance(detail, str):
                    raise ProviderError(detail, response.status_code)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("知识引擎连接失败，请检查服务地址、访问凭据与引擎日志。") from exc
        if data.get("success") is False or data.get("status", 200) >= 400:
            raise ProviderError("知识引擎未完成请求，请检查集合、权限与引擎日志。")
        return data

    async def collections(self) -> list[dict]:
        items = []
        for page in range(100):
            result = await self.request("collections/search", {"pageIndex": page, "pageSize": 100})
            body = result.get("result", {})
            batch = body.get("data", [])
            items.extend({"id": item["id"], "name": item["name"]} for item in batch)
            if len(batch) < 100 or len(items) >= body.get("total", len(items)):
                return items
        raise ProviderError("集合数量超过当前列表上限。")

    async def search(
        self,
        query: str,
        collections: list[str],
        mode: str = "intelligent",
        *,
        top_k: int = 5,
        similarity_threshold: float = 0.15,
    ) -> list[dict]:
        data = await self.request(
            "search/unified",
            {
                "query": query,
                "collection_id": collections,
                "search_mode": mode,
                "top_k": top_k,
                "similarity_threshold": similarity_threshold,
                "include_content": True,
                "answer_with_file": False,
            },
        )
        sources = []
        for item in data.get("results", []):
            text = item.get("content") or item.get("snippet") or ""
            if not text.strip():
                continue
            meta = item.get("metadata") or {}
            sources.append(
                {
                    "resource_id": item.get("resource_id"),
                    "content_id": item.get("content_id"),
                    "collection_id": item.get("collection_id"),
                    "version": item.get("version"),
                    "title": item.get("title") or meta.get("file_name") or "未命名资料",
                    "content": text[:6000],
                    "score": item.get("similarity_score", item.get("score")),
                }
            )
        return sources


class LLMClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings, self.client = settings, client

    async def chat(self, system: str, prompt: str) -> str:
        if not self.settings.llm_model:
            raise ProviderError("尚未配置生成模型，请设置 QUILL_LLM_MODEL 和模型接口。")
        headers = {}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"
        try:
            response = await self.client.post(
                self.settings.llm_base_url.rstrip("/") + "/chat/completions",
                json={
                    "model": self.settings.llm_model,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": self.settings.llm_max_tokens,
                },
                headers=headers,
                timeout=self.settings.llm_timeout,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("empty response")
            return content.strip()
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("生成模型调用失败，请检查模型配置、配额与服务日志。") from exc


def reference_text(sources: list[dict]) -> str:
    return "\n\n".join(f"[{i}] {item['title']}\n{item['content']}" for i, item in enumerate(sources, 1))
