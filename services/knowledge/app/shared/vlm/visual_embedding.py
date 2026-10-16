#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视觉向量 provider。

内部统一命名为 visual embedding / visual similarity，
当前默认实现为 CLIP 兼容的图片向量。
"""

from __future__ import annotations

import base64
import mimetypes
import os
import tempfile
import threading
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class VisualEmbeddingConfig:
    provider: str
    model_name: str
    device: str
    cache_dir: Optional[str]
    local_files_only: bool
    api_base: Optional[str]
    api_key: Optional[str]


def _default_device() -> str:
    env = (os.getenv("VISUAL_EMBEDDING_DEVICE") or os.getenv("CLIP_DEVICE") or "").strip()
    if env:
        return env
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _parse_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _normalize_openai_base_url(api_base: Optional[str]) -> str:
    if not api_base:
        return ""
    value = str(api_base).strip().rstrip("/")
    for suffix in ("/chat/completions", "/completions", "/v1/chat/completions", "/v1/completions"):
        if value.endswith(suffix):
            value = value[: -len(suffix)].rstrip("/")
            break
    if not value.endswith("/v1"):
        value = f"{value}/v1"
    return value


@lru_cache(maxsize=1)
def _get_visual_embedding_config() -> VisualEmbeddingConfig:
    provider = (
        os.getenv("VISUAL_EMBEDDING_PROVIDER")
        or os.getenv("CLIP_PROVIDER")
        or ("openai" if (os.getenv("VISUAL_EMBEDDING_API_BASE") or os.getenv("CLIP_API_BASE") or os.getenv("OPENAI_API_BASE")) else "disabled")
    ).strip().lower()

    model_name = (
        os.getenv("VISUAL_EMBEDDING_MODEL")
        or os.getenv("CLIP_MODEL_NAME")
        or "openai/clip-vit-base-patch32"
    ).strip()

    cache_dir = (os.getenv("VISUAL_EMBEDDING_CACHE_DIR") or os.getenv("CLIP_CACHE_DIR") or "").strip() or None
    local_files_only = _parse_bool(os.getenv("VISUAL_EMBEDDING_LOCAL_FILES_ONLY"), default=False)
    if _parse_bool(os.getenv("CLIP_LOCAL_FILES_ONLY"), default=False):
        local_files_only = True
    if _parse_bool(os.getenv("HF_HUB_OFFLINE"), default=False) or _parse_bool(os.getenv("TRANSFORMERS_OFFLINE"), default=False):
        local_files_only = True

    api_base = (
        os.getenv("VISUAL_EMBEDDING_API_BASE")
        or os.getenv("CLIP_API_BASE")
        or os.getenv("OPENAI_API_BASE")
        or ""
    ).strip() or None
    api_key = (
        os.getenv("VISUAL_EMBEDDING_API_KEY")
        or os.getenv("CLIP_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    ).strip() or None

    return VisualEmbeddingConfig(
        provider=provider,
        model_name=model_name,
        device=_default_device(),
        cache_dir=cache_dir,
        local_files_only=local_files_only,
        api_base=api_base,
        api_key=api_key,
    )


@lru_cache(maxsize=1)
def _load_visual_provider():
    config = _get_visual_embedding_config()

    if config.provider in {"", "disabled", "none", "off"}:
        raise RuntimeError(
            "未配置视觉向量 provider。默认 minimal 安装不会隐式启用本地 transformers。"
            "请配置 VISUAL_EMBEDDING_PROVIDER=openai/remote 并提供 API_BASE，"
            "或安装 requirements-vision.txt / requirements-full.txt 后显式设置 provider=transformers。"
        )

    if config.provider in {"openai", "remote"}:
        from openai import OpenAI

        base_url = _normalize_openai_base_url(config.api_base)
        if not base_url:
            raise RuntimeError("视觉向量 provider=openai 需要 VISUAL_EMBEDDING_API_BASE / CLIP_API_BASE")
        client = OpenAI(api_key=config.api_key or "EMPTY", base_url=base_url)
        return client, None, config

    try:
        from transformers import CLIPModel, CLIPProcessor
    except Exception as exc:
        raise RuntimeError(
            "视觉向量 provider=transformers 需要本地视觉依赖。"
            "请安装 requirements-vision.txt 或 requirements-full.txt。"
        ) from exc

    model = CLIPModel.from_pretrained(
        config.model_name,
        cache_dir=config.cache_dir,
        local_files_only=config.local_files_only,
    )
    processor = CLIPProcessor.from_pretrained(
        config.model_name,
        cache_dir=config.cache_dir,
        local_files_only=config.local_files_only,
    )

    try:
        model.to(config.device)
    except Exception:
        pass

    model.eval()
    return model, processor, config


class VisualImageEmbedder:
    """视觉图片向量器。当前实现为 CLIP 兼容图片 embedding。"""

    def __init__(self):
        self._model, self._processor, self._config = _load_visual_provider()
        self._lock = threading.Lock()

    @property
    def provider(self) -> str:
        return self._config.provider

    @property
    def model_name(self) -> str:
        return self._config.model_name

    def embed_image_file(self, image_path: str) -> np.ndarray:
        if self._config.provider in {"openai", "remote"}:
            return self._embed_image_file_via_openai(image_path)

        from PIL import Image

        with Image.open(image_path) as image:
            image = image.convert("RGB")
            return self.embed_pil_image(image)

    def embed_pil_image(self, image) -> np.ndarray:
        if self._config.provider in {"openai", "remote"}:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                temp_path = temp_file.name
            try:
                image.save(temp_path, format="PNG")
                return self._embed_image_file_via_openai(temp_path)
            finally:
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

        import torch
        import torch.nn.functional as F

        inputs = self._processor(images=image, return_tensors="pt")
        try:
            inputs = {key: value.to(self._config.device) for key, value in inputs.items()}
        except Exception:
            pass

        with self._lock:
            with torch.no_grad():
                features = self._model.get_image_features(**inputs)
                features = F.normalize(features, p=2, dim=-1)
        return features[0].detach().cpu().numpy().astype(np.float32)

    def _embed_image_file_via_openai(self, image_path: str) -> np.ndarray:
        mime, _ = mimetypes.guess_type(image_path)
        mime = mime or "image/jpeg"
        with open(image_path, "rb") as file_obj:
            payload = base64.b64encode(file_obj.read()).decode("utf-8")
        data_url = f"data:{mime};base64,{payload}"

        with self._lock:
            response = self._model.embeddings.create(
                model=self._config.model_name,
                input=[data_url],
            )
        embedding = np.asarray(response.data[0].embedding, dtype=np.float32)
        norm = float(np.linalg.norm(embedding) + 1e-12)
        return (embedding / norm).astype(np.float32)


@lru_cache(maxsize=1)
def get_visual_image_embedder() -> VisualImageEmbedder:
    return VisualImageEmbedder()
