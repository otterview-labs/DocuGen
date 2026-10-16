#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
向量数据库工厂函数。
"""

from __future__ import annotations

import importlib
import logging
from typing import Optional

from app.config import settings
from app.core.rag.vector_db.base import VectorDBBase

logger = logging.getLogger(__name__)

_BACKEND_CLASS_PATHS: dict[str, tuple[str, str]] = {
    "faiss": ("app.core.rag.vector_db.faiss_db", "FaissVectorDB"),
    "milvus": ("app.core.rag.vector_db.milvus_db", "MilvusVectorDB"),
    "pgvector": ("app.core.rag.vector_db.pgvector_db", "PgVectorVectorDB"),
}
_DEFAULT_DB_TYPE = "faiss"
_vector_db: Optional[VectorDBBase] = None


def _normalize_db_type(db_type: Optional[str]) -> str:
    raw_value = db_type or getattr(settings.vector_db, "VECTOR_DB_TYPE", _DEFAULT_DB_TYPE)
    normalized = str(raw_value).strip().lower()
    return normalized or _DEFAULT_DB_TYPE


def _load_backend_class(db_type: str):
    module_path, class_name = _BACKEND_CLASS_PATHS[db_type]
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _instantiate_backend(db_type: str) -> VectorDBBase:
    backend_class = _load_backend_class(db_type)
    return backend_class()


def _build_fallback_message(db_type: str, exc: Exception) -> str:
    return f"{db_type} 初始化失败: {exc}，回退到 FAISS"


def _create_with_fallback(db_type: str) -> VectorDBBase:
    normalized = _normalize_db_type(db_type)

    if normalized == "milvus":
        milvus_host = (getattr(settings.vector_db, "MILVUS_HOST", "") or "").strip().lower()
        if not milvus_host or milvus_host == "localhost":
            logger.warning("Milvus配置不完整，使用FAISS作为备选")
            normalized = _DEFAULT_DB_TYPE

    if normalized not in _BACKEND_CLASS_PATHS:
        logger.warning("未知的向量库类型: %s，使用FAISS作为默认", normalized)
        normalized = _DEFAULT_DB_TYPE

    try:
        return _instantiate_backend(normalized)
    except Exception as exc:
        if normalized == _DEFAULT_DB_TYPE:
            raise
        logger.error(_build_fallback_message(normalized, exc))
        return _instantiate_backend(_DEFAULT_DB_TYPE)


def get_vector_db(db_type: Optional[str] = None) -> VectorDBBase:
    """获取向量库实例。"""

    global _vector_db

    if db_type is not None:
        return create_vector_db(db_type)

    if _vector_db is None:
        _vector_db = create_vector_db()

    return _vector_db


def create_vector_db(db_type: Optional[str] = None) -> VectorDBBase:
    """创建向量库实例。"""

    return _create_with_fallback(_normalize_db_type(db_type))


def switch_vector_db(vector_db_type: str) -> VectorDBBase:
    """切换向量库。"""

    global _vector_db

    normalized = _normalize_db_type(vector_db_type)
    settings.vector_db.DB_TYPE = normalized
    _vector_db = create_vector_db(normalized)
    return _vector_db


async def get_vector_db_async(db_type: Optional[str] = None) -> VectorDBBase:
    """异步获取向量数据库实例（为兼容性提供）。"""

    return get_vector_db(db_type)
