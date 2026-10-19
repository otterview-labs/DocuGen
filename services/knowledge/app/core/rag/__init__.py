#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG模块 - 检索增强生成
"""

from __future__ import annotations

import importlib

from .vector_db import VectorDBBase, create_vector_db, get_vector_db, switch_vector_db

_LAZY_EXPORTS = {
    "FaissVectorDB": "FaissVectorDB",
    "MilvusVectorDB": "MilvusVectorDB",
    "PgVectorVectorDB": "PgVectorVectorDB",
}


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    vector_db_module = importlib.import_module("app.core.rag.vector_db")
    return getattr(vector_db_module, _LAZY_EXPORTS[name])


__all__ = [
    "get_vector_db",
    "create_vector_db",
    "switch_vector_db",
    "VectorDBBase",
    "FaissVectorDB",
    "MilvusVectorDB",
    "PgVectorVectorDB",
]
