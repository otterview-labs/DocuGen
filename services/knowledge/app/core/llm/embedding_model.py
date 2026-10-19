#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Embedding模型管理器 - 支持多种embedding模型
"""

import os
import re
import json
import logging
import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Tuple
from urllib.parse import urljoin
import numpy as np
import requests
import httpx

# 第三方库导入
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import dashscope
    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False

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


class BaseEmbedding(ABC):
    """Embedding模型基类"""

    def __init__(self, key: str = None, model_name: str = None, **kwargs):
        self.key = key
        self.model_name = model_name
        self._model = None
        self._model_lock = threading.Lock()

    @abstractmethod
    def encode(self, texts: List[str]) -> Tuple[np.ndarray, int]:
        """编码文本列表"""
        pass

    @abstractmethod
    def encode_queries(self, text: str) -> Tuple[np.ndarray, int]:
        """编码查询文本"""
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

    def resolve_batch_size(self, default_batch_size: int = 16) -> int:
        """解析 embedding 批大小。

        优先使用环境变量；对本地 qwen3-embedding 走更保守的小批次，
        避免长文本/多分块批量请求把本地 embedding 服务压住。
        """
        env_candidates = [
            os.getenv("EMBEDDING_BATCH_SIZE"),
            os.getenv(f"{self._FACTORY_NAME.upper()}_EMBEDDING_BATCH_SIZE", ""),
        ]
        for raw in env_candidates:
            try:
                if raw and int(raw) > 0:
                    return int(raw)
            except Exception:
                continue

        model_name = (self.model_name or "").strip().lower()
        if "qwen3-embedding" in model_name:
            return min(default_batch_size, 8)
        return default_batch_size

    def resolve_output_dimensions(self) -> Optional[int]:
        """解析期望输出维度。

        当前 pgvector 表是固定维度列，OpenAI 兼容 embedding 服务若支持
        `dimensions` 参数，需要显式请求与向量库一致的维度。
        """
        raw = (
            os.getenv("OPENAI_EMBEDDING_DIMENSIONS")
            or os.getenv("EMBEDDING_OUTPUT_DIMENSION")
            or os.getenv("VECTOR_DB_DIMENSION")
            or ""
        ).strip()
        try:
            value = int(raw)
            return value if value > 0 else None
        except Exception:
            return None


class QwenEmbedding(BaseEmbedding):
    """阿里云Qwen3 Embedding模型"""

    _FACTORY_NAME = "Qwen"

    def __init__(self, key: str = None, model_name: str = "text-embedding-v1", **kwargs):
        super().__init__(key, model_name)
        self.key = key or os.getenv("DASHSCOPE_API_KEY")
        self.model_name = model_name
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"

        if not self.key:
            logger.warning("未配置DASHSCOPE_API_KEY，Qwen Embedding功能将不可用")
        else:
            logger.info(f"Qwen Embedding初始化完成，模型: {model_name}")

    def encode(self, texts: List[str]) -> Tuple[np.ndarray, int]:
        """批量编码文本"""
        if not self.key:
            raise ValueError("DASHSCOPE_API_KEY未配置")

        headers = {
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json"
        }

        batch_size = self.resolve_batch_size(16)
        all_embeddings = []
        total_tokens = 0

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]

            data = {
                "model": self.model_name,
                "input": {
                    "texts": batch_texts
                },
                "parameters": {}
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
                    embeddings = [item["embedding"] for item in result["output"]["embeddings"]]
                    all_embeddings.extend(embeddings)
                    total_tokens += result.get("usage", {}).get("total_tokens", 0)
                else:
                    logger.error(f"Qwen Embedding API调用失败: {response.status_code} - {response.text}")
                    raise Exception(f"API调用失败: {response.status_code}")

            except Exception as e:
                logger.error(f"Qwen Embedding编码失败: {e}")
                raise

        return np.array(all_embeddings), total_tokens

    def encode_queries(self, text: str) -> Tuple[np.ndarray, int]:
        """编码查询文本"""
        embeddings, token_count = self.encode([text])
        return embeddings[0], token_count


class OpenAIEmbedding(BaseEmbedding):
    """OpenAI Embedding模型"""

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
            logger.warning("未配置OPENAI_API_KEY，OpenAI Embedding功能将不可用")
            return

        self.client = OpenAI(
            api_key=self.auth_config.sdk_api_key,
            base_url=self.base_url,
            http_client=httpx.Client(auth=build_httpx_auth(self.auth_config)),
        )
        logger.info(f"OpenAI Embedding初始化完成，模型: {model_name}, auth_mode: {self.auth_config.mode}")

    def encode(self, texts: List[str]) -> Tuple[np.ndarray, int]:
        """批量编码文本"""
        if self.auth_config.mode == "bearer" and not self.key:
            raise ValueError("OPENAI_API_KEY未配置")

        batch_size = self.resolve_batch_size(16)
        texts = [self._truncate_text(t, 8191) for t in texts]

        all_embeddings = []
        total_tokens = 0
        output_dimensions = self.resolve_output_dimensions()

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]

            try:
                kwargs = {
                    "input": batch_texts,
                    "model": self.model_name,
                }
                if output_dimensions and "qwen3-embedding" in (self.model_name or "").lower():
                    kwargs["dimensions"] = output_dimensions

                response = self.client.embeddings.create(**kwargs)

                embeddings = [data.embedding for data in response.data]
                all_embeddings.extend(embeddings)
                total_tokens += self.total_token_count(response)

            except Exception as e:
                logger.error(f"OpenAI Embedding编码失败: {e}")
                raise

        return np.array(all_embeddings), total_tokens

    def encode_queries(self, text: str) -> Tuple[np.ndarray, int]:
        """编码查询文本"""
        text = self._truncate_text(text, 8191)

        try:
            kwargs = {
                "input": [text],
                "model": self.model_name,
            }
            output_dimensions = self.resolve_output_dimensions()
            if output_dimensions and "qwen3-embedding" in (self.model_name or "").lower():
                kwargs["dimensions"] = output_dimensions

            response = self.client.embeddings.create(**kwargs)

            embedding = response.data[0].embedding
            return np.array(embedding), self.total_token_count(response)

        except Exception as e:
            logger.error(f"OpenAI Embedding查询编码失败: {e}")
            raise

    def _truncate_text(self, text: str, max_length: int) -> str:
        """截断文本"""
        if len(text) > max_length:
            return text[:max_length]
        return text


class LocalEmbedding(BaseEmbedding):
    """本地Embedding模型"""

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
        self.auth_config = HTTPAuthConfig.build(
            mode=auth_mode,
            api_key=key or os.getenv("LOCAL_EMBEDDING_API_KEY"),
            username=username or os.getenv("LOCAL_EMBEDDING_USERNAME"),
            password=password or os.getenv("LOCAL_EMBEDDING_PASSWORD"),
            default_mode="none",
        )
        self.base_url = _normalize_openai_base_url(base_url or os.getenv("LOCAL_EMBEDDING_URL"))
        self.model_name = model_name or "local-embedding"

        if not self.base_url:
            raise ValueError("LOCAL_EMBEDDING_URL未配置")

        self.client = OpenAI(
            api_key=self.auth_config.sdk_api_key,
            base_url=self.base_url,
            http_client=httpx.Client(auth=build_httpx_auth(self.auth_config)),
        )
        logger.info(f"本地Embedding初始化完成，端点: {self.base_url}, auth_mode: {self.auth_config.mode}")

    def encode(self, texts: List[str]) -> Tuple[np.ndarray, int]:
        """批量编码文本"""
        texts = [self._truncate_text(t, 8191) for t in texts]
        batch_size = self.resolve_batch_size(16)
        output_dimensions = self.resolve_output_dimensions()

        all_embeddings = []
        total_tokens = 0

        try:
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                kwargs = {
                    "input": batch_texts,
                    "model": self.model_name,
                }
                if output_dimensions and "qwen3-embedding" in (self.model_name or "").lower():
                    kwargs["dimensions"] = output_dimensions

                response = self.client.embeddings.create(**kwargs)
                embeddings = [data.embedding for data in response.data]
                all_embeddings.extend(embeddings)
                total_tokens += self.total_token_count(response)
        except Exception as e:
            logger.error(f"本地Embedding编码失败: {e}")
            raise

        return np.array(all_embeddings), total_tokens

    def encode_queries(self, text: str) -> Tuple[np.ndarray, int]:
        """编码查询文本"""
        text = self._truncate_text(text, 8191)
        try:
            kwargs = {
                "input": [text],
                "model": self.model_name,
            }
            output_dimensions = self.resolve_output_dimensions()
            if output_dimensions and "qwen3-embedding" in (self.model_name or "").lower():
                kwargs["dimensions"] = output_dimensions

            response = self.client.embeddings.create(**kwargs)
            embedding = response.data[0].embedding
            return np.array(embedding), self.total_token_count(response)
        except Exception as e:
            logger.error(f"本地Embedding查询编码失败: {e}")
            raise

    def _truncate_text(self, text: str, max_length: int) -> str:
        if len(text) > max_length:
            return text[:max_length]
        return text


class HuggingFaceEmbedding(BaseEmbedding):
    """HuggingFace Embedding模型"""

    _FACTORY_NAME = "HuggingFace"

    def __init__(self, key: str = None, model_name: str = None, base_url: str = None, **kwargs):
        super().__init__(key, model_name)
        self.base_url = base_url or "http://localhost:8000"
        self.model_name = model_name or "sentence-transformers/all-MiniLM-L6-v2"

        logger.info(f"HuggingFace Embedding初始化完成，模型: {model_name}")

    def encode(self, texts: List[str]) -> Tuple[np.ndarray, int]:
        """批量编码文本"""
        headers = {
            "Content-Type": "application/json"
        }

        data = {
            "inputs": texts
        }

        try:
            response = requests.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=data,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                embeddings = result["embeddings"]
                return np.array(embeddings), sum(len(t.split()) for t in texts)
            else:
                raise Exception(f"HuggingFace Embedding API调用失败: {response.status_code}")

        except Exception as e:
            logger.error(f"HuggingFace Embedding编码失败: {e}")
            raise

    def encode_queries(self, text: str) -> Tuple[np.ndarray, int]:
        """编码查询文本"""
        embeddings, token_count = self.encode([text])
        return embeddings[0], token_count


# 模型工厂
class EmbeddingModelFactory:
    """Embedding模型工厂"""

    _models = {
        "Qwen": QwenEmbedding,
        "OpenAI": OpenAIEmbedding,
        "Local": LocalEmbedding,
        "HuggingFace": HuggingFaceEmbedding,
    }

    @classmethod
    def create(cls, model_type: str, **kwargs) -> BaseEmbedding:
        """创建Embedding模型实例"""
        if model_type not in cls._models:
            raise ValueError(f"不支持的Embedding模型类型: {model_type}")

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
def _resolve_embedding_factory_kwargs(model_type: Optional[str], kwargs: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
    resolved_kwargs = dict(kwargs)
    if model_type:
        resolved_type = model_type
    else:
        from app.config import settings

        provider = (getattr(settings.embedding, "PROVIDER", "") or "openai").strip().lower()
        if provider == "local":
            resolved_type = "Local"
            resolved_kwargs.setdefault("base_url", settings.embedding.LOCAL_EMBEDDING_URL)
            resolved_kwargs.setdefault("model_name", settings.embedding.LOCAL_EMBEDDING_MODEL or "local-embedding")
            resolved_kwargs.setdefault("key", settings.embedding.LOCAL_EMBEDDING_API_KEY)
            resolved_kwargs.setdefault("auth_mode", settings.embedding.LOCAL_EMBEDDING_AUTH_MODE)
            resolved_kwargs.setdefault("username", settings.embedding.LOCAL_EMBEDDING_USERNAME)
            resolved_kwargs.setdefault("password", settings.embedding.LOCAL_EMBEDDING_PASSWORD)
        else:
            resolved_type = "OpenAI"
            resolved_kwargs.setdefault("base_url", settings.llm.OPENAI_API_BASE)
            resolved_kwargs.setdefault("model_name", settings.embedding.OPENAI_EMBEDDING_MODEL)
            resolved_kwargs.setdefault("key", settings.llm.OPENAI_API_KEY)
            resolved_kwargs.setdefault("auth_mode", settings.llm.OPENAI_API_AUTH_MODE)
            resolved_kwargs.setdefault("username", settings.llm.OPENAI_API_USERNAME)
            resolved_kwargs.setdefault("password", settings.llm.OPENAI_API_PASSWORD)

    if resolved_type == "OpenAI":
        from app.config import settings

        resolved_kwargs.setdefault("base_url", settings.llm.OPENAI_API_BASE)
        resolved_kwargs.setdefault("model_name", settings.embedding.OPENAI_EMBEDDING_MODEL)
        resolved_kwargs.setdefault("key", settings.llm.OPENAI_API_KEY)
        resolved_kwargs.setdefault("auth_mode", settings.llm.OPENAI_API_AUTH_MODE)
        resolved_kwargs.setdefault("username", settings.llm.OPENAI_API_USERNAME)
        resolved_kwargs.setdefault("password", settings.llm.OPENAI_API_PASSWORD)
    elif resolved_type == "Local":
        from app.config import settings

        resolved_kwargs.setdefault("base_url", settings.embedding.LOCAL_EMBEDDING_URL)
        resolved_kwargs.setdefault("model_name", settings.embedding.LOCAL_EMBEDDING_MODEL or "local-embedding")
        resolved_kwargs.setdefault("key", settings.embedding.LOCAL_EMBEDDING_API_KEY)
        resolved_kwargs.setdefault("auth_mode", settings.embedding.LOCAL_EMBEDDING_AUTH_MODE)
        resolved_kwargs.setdefault("username", settings.embedding.LOCAL_EMBEDDING_USERNAME)
        resolved_kwargs.setdefault("password", settings.embedding.LOCAL_EMBEDDING_PASSWORD)

    return resolved_type, resolved_kwargs


def create_embedding_model(model_type: Optional[str] = None, **kwargs) -> BaseEmbedding:
    """创建Embedding模型的便捷函数"""
    resolved_type, resolved_kwargs = _resolve_embedding_factory_kwargs(model_type, kwargs)
    return EmbeddingModelFactory.create(resolved_type, **resolved_kwargs)


def get_supported_embedding_models() -> List[str]:
    """获取支持的Embedding模型列表"""
    return EmbeddingModelFactory.get_supported_models()
