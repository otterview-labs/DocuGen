#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
兼容层：保留旧的 `KGManager` 导入路径，内部统一委托给 `KnowledgeGraphManager`。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.core.kg.manager import KnowledgeGraphManager as _KnowledgeGraphManager

logger = logging.getLogger(__name__)

class KGManager:
    """旧接口兼容壳。

    新代码请直接使用 `KnowledgeGraphManager`。
    """

    def __init__(self, namespace: str = "default"):
        self.namespace = namespace
        self._manager = _KnowledgeGraphManager(namespace=namespace)

    async def initialize(self):
        await self._manager.initialize()

    async def cleanup(self):
        await self._manager.finalize()

    async def finalize(self):
        await self.cleanup()

    def is_enabled(self) -> bool:
        return self._manager.is_enabled()

    async def query_nodes(
        self,
        *,
        query: Optional[str] = None,
        node_type: Optional[str] = None,
        document_id: Optional[str] = None,
        node_ids: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        return await self._manager.query_nodes(
            query=query,
            node_type=node_type,
            document_id=document_id,
            node_ids=node_ids,
            limit=limit,
        )

    async def query_edges(
        self,
        *,
        query: Optional[str] = None,
        document_id: Optional[str] = None,
        node_ids: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return await self._manager.query_edges(
            query=query,
            document_id=document_id,
            node_ids=node_ids,
            limit=limit,
        )

    async def list_document_entities(
        self,
        document_id: str,
        *,
        content_name: str = "",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        return await self._manager.list_document_entities(document_id, content_name=content_name, limit=limit)

    async def analyze_entity_associations(
        self,
        entity_name: str,
        *,
        max_depth: int = 2,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        return await self._manager.analyze_entity_associations(
            entity_name,
            max_depth=max_depth,
            limit=limit,
        )

    async def get_graph_statistics(self) -> Dict[str, Any]:
        return await self._manager.get_graph_statistics()

    async def extract_entities_and_relations(self, text: str) -> Dict[str, Any]:
        return await self._manager.extract_entities_and_relations(text)

    async def store_extracted_graph(
        self,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
        *,
        doc_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._manager.store_extracted_graph(entities, relations, doc_id=doc_id)

    async def build_knowledge_graph(self, text: str, doc_id: str | None = None) -> Dict[str, Any]:
        return await self._manager.build_knowledge_graph(text, doc_id)

    async def add_document_to_graph(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return await self._manager.add_document_to_graph(doc_id, content, metadata)

    async def execute_query(self, query: str, params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        raise RuntimeError(
            "KGManager.execute_query 已弃用。请改用 KnowledgeGraphManager.query_nodes/query_edges "
            "等后端无关接口，而不是直接执行 Neo4j Cypher。"
        )


class KnowledgeGraphManager(KGManager):
    """兼容旧导入路径：`from app.core.kg.simple_manager import KnowledgeGraphManager`。"""
