#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rerank模型管理器 - 支持多种rerank模型
"""

import os
import re
import json
import logging
import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Tuple
from collections.abc import Iterable
import numpy as np
import requests
import httpx

# 第三方库导入
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

from app.shared.utils.http_auth import (
    HTTPAuthConfig,
    apply_auth_headers,
    build_httpx_auth,
    build_requests_auth,
)


def _normalize_openai_base_url(base_url: Optional[str]) -> str:
    if not base_url:
        return ""
    value = str(base_url).strip().rstrip("/")
    for suffix in ("/chat/completions", "/embeddings", "/v1/chat/completions", "/v1/embeddings"):
        if value.endswith(suffix):
            value = value[: -len(suffix)].rstrip("/")
            break
    if not value.endswith("/v1"):
        value = f"{value}/v1"
    return value


class BaseRerank(ABC):
    """Rerank模型基类"""

    def __init__(self, key: str = None, model_name: str = None, **kwargs):
        self.key = key
        self.model_name = model_name
        self._model = None
        self._model_lock = threading.Lock()

    @abstractmethod
    def similarity(self, query: str, texts: List[str]) -> Tuple[np.ndarray, int]:
        """计算查询与文本的相似度"""
        pass

    def total_token_count(self, resp) -> int:
        """计算token数量"""
        try:
            return resp.usage.total_tokens
        except Exception:
            pass
        try:
            return resp["usage"]["total_tokens"]
        except Exception:
            pass
        return 0


class QwenRerank(BaseRerank):
    """阿里云Qwen Rerank模型"""

    _FACTORY_NAME = "Qwen"

    def __init__(self, key: str = None, model_name: str = "gte-rerank", **kwargs):
        super().__init__(key, model_name)
        self.key = key or os.getenv("DASHSCOPE_API_KEY")
        self.model_name = model_name
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"

        if not self.key:
            logger.warning("未配置DASHSCOPE_API_KEY，Qwen Rerank功能将不可用")
        else:
            logger.info(f"Qwen Rerank初始化完成，模型: {model_name}")

    def similarity(self, query: str, texts: List[str]) -> Tuple[np.ndarray, int]:
        """计算相似度"""
        if not self.key:
            raise ValueError("DASHSCOPE_API_KEY未配置")

        headers = {
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json"
        }

        # 准备文档对
        documents = []
        for i, text in enumerate(texts):
            documents.append({
                "index": i,
                "text": self._truncate_text(text, 2048)
            })

        data = {
            "model": self.model_name,
            "query": query,
            "documents": documents
        }

        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=data,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                scores = np.zeros(len(texts), dtype=float)

                for item in result["output"]["results"]:
                    index = item["index"]
                    scores[index] = item["relevance_score"]

                total_tokens = result.get("usage", {}).get("total_tokens", 0)
                return scores, total_tokens
            else:
                logger.error(f"Qwen Rerank API调用失败: {response.status_code} - {response.text}")
                raise Exception(f"API调用失败: {response.status_code}")

        except Exception as e:
            logger.error(f"Qwen Rerank相似度计算失败: {e}")
            raise

    def _truncate_text(self, text: str, max_length: int) -> str:
        """截断文本"""
        if len(text) > max_length:
            return text[:max_length]
        return text


class JinaRerank(BaseRerank):
    """Jina Rerank模型"""

    _FACTORY_NAME = "Jina"

    def __init__(self, key: str = None, model_name: str = "jina-reranker-v2-base-multilingual", base_url: str = "https://api.jina.ai/v1/rerank", **kwargs):
        super().__init__(key, model_name)
        self.key = key
        self.model_name = model_name
        self.base_url = base_url

        if not self.key:
            logger.warning("未配置Jina API密钥，Jina Rerank功能将不可用")
        else:
            logger.info(f"Jina Rerank初始化完成，模型: {model_name}")

    def similarity(self, query: str, texts: List[str]) -> Tuple[np.ndarray, int]:
        """计算相似度"""
        if not self.key:
            raise ValueError("Jina API密钥未配置")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.key}"
        }

        texts = [self._truncate_text(t, 8196) for t in texts]
        data = {
            "model": self.model_name,
            "query": query,
            "documents": texts,
            "top_n": len(texts)
        }

        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=data,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                scores = np.zeros(len(texts), dtype=float)

                for item in result["results"]:
                    scores[item["index"]] = item["relevance_score"]

                total_tokens = self.total_token_count(result)
                return scores, total_tokens
            else:
                raise Exception(f"Jina Rerank API调用失败: {response.status_code}")

        except Exception as e:
            logger.error(f"Jina Rerank相似度计算失败: {e}")
            raise

    def _truncate_text(self, text: str, max_length: int) -> str:
        """截断文本"""
        if len(text) > max_length:
            return text[:max_length]
        return text


class OpenAIRerank(BaseRerank):
    """OpenAI Rerank模型"""

    _FACTORY_NAME = "OpenAI"

    def __init__(
        self,
        key: str = None,
        model_name: str = "text-embedding-ada-002",
        base_url: str = "https://api.openai.com/v1",
        auth_mode: str = "bearer",
        username: str = None,
        password: str = None,
        **kwargs,
    ):
        super().__init__(key, model_name)
        self.auth_config = HTTPAuthConfig.build(
            mode=auth_mode,
            api_key=key or os.getenv("OPENAI_API_KEY"),
            username=username,
            password=password,
            default_mode="bearer",
        )
        self.key = self.auth_config.api_key or ""
        self.model_name = model_name
        self.base_url = _normalize_openai_base_url(base_url or os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1")

        if self.auth_config.mode == "bearer" and not self.key:
            logger.warning("未配置OPENAI_API_KEY，OpenAI Rerank功能将不可用")
            return

        self.client = OpenAI(
            api_key=self.auth_config.sdk_api_key,
            base_url=self.base_url,
            http_client=httpx.Client(auth=build_httpx_auth(self.auth_config)),
        )
        logger.info(f"OpenAI Rerank初始化完成，模型: {model_name}, auth_mode: {self.auth_config.mode}")

    def similarity(self, query: str, texts: List[str]) -> Tuple[np.ndarray, int]:
        """计算相似度（使用embedding计算余弦相似度）"""
        if self.auth_config.mode == "bearer" and not self.key:
            raise ValueError("OPENAI_API_KEY未配置")

        try:
            # 编码查询
            query_response = self.client.embeddings.create(
                input=[query],
                model=self.model_name
            )
            query_embedding = np.array(query_response.data[0].embedding)

            # 编码文档
            batch_size = 16
            all_embeddings = []
            total_tokens = 0

            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]

                response = self.client.embeddings.create(
                    input=batch_texts,
                    model=self.model_name
                )

                embeddings = [np.array(data.embedding) for data in response.data]
                all_embeddings.extend(embeddings)
                total_tokens += self.total_token_count(response)

            # 计算余弦相似度
            scores = []
            for doc_embedding in all_embeddings:
                similarity = np.dot(query_embedding, doc_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding)
                )
                scores.append(similarity)

            return np.array(scores), total_tokens

        except Exception as e:
            logger.error(f"OpenAI Rerank相似度计算失败: {e}")
            raise


class LocalRerank(BaseRerank):
    """本地Rerank模型"""

    _FACTORY_NAME = "Local"

    def __init__(
        self,
        key: str = None,
        model_name: str = None,
        base_url: str = None,
        auth_mode: str = "none",
        username: str = None,
        password: str = None,
        **kwargs,
    ):
        super().__init__(key, model_name)
        self.base_url = base_url or os.getenv("LOCAL_RERANK_URL")
        self.model_name = model_name or "local-rerank"
        self.auth_config = HTTPAuthConfig.build(
            mode=auth_mode,
            api_key=key or os.getenv("LOCAL_RERANK_API_KEY"),
            username=username or os.getenv("LOCAL_RERANK_USERNAME"),
            password=password or os.getenv("LOCAL_RERANK_PASSWORD"),
            default_mode="none",
        )

        if not self.base_url:
            raise ValueError("LOCAL_RERANK_URL未配置")

        logger.info(f"本地Rerank初始化完成，端点: {self.base_url}, auth_mode: {self.auth_config.mode}")

    def similarity(self, query: str, texts: List[str]) -> Tuple[np.ndarray, int]:
        """计算相似度"""
        headers = apply_auth_headers({"Content-Type": "application/json"}, self.auth_config)

        data = {
            "model": self.model_name,
            "query": query,
            "documents": texts
        }

        try:
            response = requests.post(
                f"{self.base_url}/rerank",
                headers=headers,
                json=data,
                timeout=30,
                auth=build_requests_auth(self.auth_config),
            )

            if response.status_code == 200:
                result = response.json()
                scores = np.array(result["scores"])
                total_tokens = result.get("usage", {}).get("total_tokens", 0)
                return scores, total_tokens
            else:
                raise Exception(f"本地Rerank API调用失败: {response.status_code}")

        except Exception as e:
            logger.error(f"本地Rerank相似度计算失败: {e}")
            raise


class HuggingFaceRerank(BaseRerank):
    """HuggingFace Rerank模型"""

    _FACTORY_NAME = "HuggingFace"

    def __init__(self, key: str = None, model_name: str = None, base_url: str = None, **kwargs):
        super().__init__(key, model_name)
        self.base_url = base_url or "http://localhost:8000"
        self.model_name = model_name or "cross-encoder/ms-marco-MiniLM-L-6-v2"

        logger.info(f"HuggingFace Rerank初始化完成，模型: {model_name}")

    def similarity(self, query: str, texts: List[str]) -> Tuple[np.ndarray, int]:
        """计算相似度"""
        headers = {
            "Content-Type": "application/json"
        }

        data = {
            "query": query,
            "documents": texts
        }

        try:
            response = requests.post(
                f"{self.base_url}/rerank",
                headers=headers,
                json=data,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                scores = np.array(result["scores"])
                total_tokens = sum(len(t.split()) for t in texts)
                return scores, total_tokens
            else:
                raise Exception(f"HuggingFace Rerank API调用失败: {response.status_code}")

        except Exception as e:
            logger.error(f"HuggingFace Rerank相似度计算失败: {e}")
            raise


# 模型工厂
class RerankModelFactory:
    """Rerank模型工厂"""

    _models = {
        "Qwen": QwenRerank,
        "Jina": JinaRerank,
        "OpenAI": OpenAIRerank,
        "Local": LocalRerank,
        "HuggingFace": HuggingFaceRerank,
    }

    @classmethod
    def create(cls, model_type: str, **kwargs) -> BaseRerank:
        """创建Rerank模型实例"""
        if model_type not in cls._models:
            raise ValueError(f"不支持的Rerank模型类型: {model_type}")

        return cls._models[model_type](**kwargs)

    @classmethod
    def get_supported_models(cls) -> List[str]:
        """获取支持的模型列表"""
        return list(cls._models.keys())

    @classmethod
    def register_model(cls, name: str, model_class: type):
        """注册新的模型类型"""
        cls._models[name] = model_class


# 便捷函数
def _resolve_rerank_factory_kwargs(model_type: Optional[str], kwargs: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
    resolved_kwargs = dict(kwargs)
    if model_type:
        resolved_type = model_type
    else:
        from app.config import settings

        provider = (getattr(settings.rerank, "PROVIDER", "") or "disabled").strip().lower()
        if provider == "disabled":
            raise ValueError("Rerank provider 已禁用")
        if provider == "local":
            resolved_type = "Local"
            resolved_kwargs.setdefault("base_url", settings.rerank.LOCAL_RERANK_URL)
            resolved_kwargs.setdefault("model_name", settings.rerank.LOCAL_RERANK_MODEL or "local-rerank")
            resolved_kwargs.setdefault("key", settings.rerank.LOCAL_RERANK_API_KEY)
            resolved_kwargs.setdefault("auth_mode", settings.rerank.LOCAL_RERANK_AUTH_MODE)
            resolved_kwargs.setdefault("username", settings.rerank.LOCAL_RERANK_USERNAME)
            resolved_kwargs.setdefault("password", settings.rerank.LOCAL_RERANK_PASSWORD)
        else:
            resolved_type = "OpenAI"
            resolved_kwargs.setdefault("base_url", settings.llm.OPENAI_API_BASE)
            resolved_kwargs.setdefault("model_name", settings.rerank.OPENAI_RERANK_MODEL)
            resolved_kwargs.setdefault("key", settings.llm.OPENAI_API_KEY)
            resolved_kwargs.setdefault("auth_mode", settings.llm.OPENAI_API_AUTH_MODE)
            resolved_kwargs.setdefault("username", settings.llm.OPENAI_API_USERNAME)
            resolved_kwargs.setdefault("password", settings.llm.OPENAI_API_PASSWORD)

    if resolved_type == "OpenAI":
        from app.config import settings

        resolved_kwargs.setdefault("base_url", settings.llm.OPENAI_API_BASE)
        resolved_kwargs.setdefault("model_name", settings.rerank.OPENAI_RERANK_MODEL)
        resolved_kwargs.setdefault("key", settings.llm.OPENAI_API_KEY)
        resolved_kwargs.setdefault("auth_mode", settings.llm.OPENAI_API_AUTH_MODE)
        resolved_kwargs.setdefault("username", settings.llm.OPENAI_API_USERNAME)
        resolved_kwargs.setdefault("password", settings.llm.OPENAI_API_PASSWORD)
    elif resolved_type == "Local":
        from app.config import settings

        resolved_kwargs.setdefault("base_url", settings.rerank.LOCAL_RERANK_URL)
        resolved_kwargs.setdefault("model_name", settings.rerank.LOCAL_RERANK_MODEL or "local-rerank")
        resolved_kwargs.setdefault("key", settings.rerank.LOCAL_RERANK_API_KEY)
        resolved_kwargs.setdefault("auth_mode", settings.rerank.LOCAL_RERANK_AUTH_MODE)
        resolved_kwargs.setdefault("username", settings.rerank.LOCAL_RERANK_USERNAME)
        resolved_kwargs.setdefault("password", settings.rerank.LOCAL_RERANK_PASSWORD)

    return resolved_type, resolved_kwargs


def create_rerank_model(model_type: Optional[str] = None, **kwargs) -> BaseRerank:
    """创建Rerank模型的便捷函数"""
    resolved_type, resolved_kwargs = _resolve_rerank_factory_kwargs(model_type, kwargs)
    return RerankModelFactory.create(resolved_type, **resolved_kwargs)


def get_supported_rerank_models() -> List[str]:
    """获取支持的Rerank模型列表"""
    return RerankModelFactory.get_supported_models()
