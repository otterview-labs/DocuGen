#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
向量库模块。
"""

from __future__ import annotations

import importlib

from app.core.rag.vector_db.base import VectorDBBase
from app.core.rag.vector_db.factory import create_vector_db, get_vector_db, switch_vector_db

_LAZY_BACKENDS: dict[str, tuple[str, str]] = {
    "FaissVectorDB": ("app.core.rag.vector_db.faiss_db", "FaissVectorDB"),
    "MilvusVectorDB": ("app.core.rag.vector_db.milvus_db", "MilvusVectorDB"),
    "PgVectorVectorDB": ("app.core.rag.vector_db.pgvector_db", "PgVectorVectorDB"),
}


def __getattr__(name: str):
    if name not in _LAZY_BACKENDS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, attr_name = _LAZY_BACKENDS[name]
    module = importlib.import_module(module_path)
    return getattr(module, attr_name)


__all__ = [
    "VectorDBBase",
    "FaissVectorDB",
    "MilvusVectorDB",
    "PgVectorVectorDB",
    "get_vector_db",
    "create_vector_db",
    "switch_vector_db",
]
