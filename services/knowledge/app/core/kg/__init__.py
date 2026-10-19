#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识图谱模块。
"""

from __future__ import annotations

from app.core.kg.base import (
    BaseGraphStorage, KnowledgeGraph, KnowledgeGraphNode, KnowledgeGraphEdge,
    GraphQueryResult, GraphNodeType, GraphEdgeType
)

_LAZY_EXPORTS = {
    "KnowledgeGraphManager": ("app.core.kg.manager", "KnowledgeGraphManager"),
    "PostgresGraphStorage": ("app.core.kg.postgres_impl", "PostgresGraphStorage"),
    "Neo4JGraphStorage": ("app.core.kg.neo4j_impl", "Neo4JGraphStorage"),
}


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, attr_name = _LAZY_EXPORTS[name]

    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, attr_name)

__all__ = [
    "BaseGraphStorage",
    "KnowledgeGraph",
    "KnowledgeGraphNode",
    "KnowledgeGraphEdge",
    "GraphQueryResult",
    "GraphNodeType",
    "GraphEdgeType",
    "PostgresGraphStorage",
    "Neo4JGraphStorage",
    "KnowledgeGraphManager"
]
