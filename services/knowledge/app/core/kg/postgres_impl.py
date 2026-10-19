#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Postgres 图存储实现（基于关系表）

目标：
- 在不依赖 Neo4j 的情况下，将知识图谱节点/边持久化到 PostgreSQL
- 提供与 BaseGraphStorage 一致的接口，便于在 neo4j/postgres 之间切换
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from app.config import settings
from app.core.kg.base import (
    BaseGraphStorage,
    GraphEdgeType,
    GraphNodeType,
    KnowledgeGraph,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
)
from app.db.session import engine as default_engine

logger = logging.getLogger(__name__)


class PostgresGraphStorage(BaseGraphStorage):
    """基于 PostgreSQL 的图存储实现（namespace 隔离）。"""

    def __init__(
        self,
        namespace: str,
        workspace: str = "",
        global_config: Optional[Dict[str, Any]] = None,
        *,
        engine: Optional[Engine] = None,
        schema: str = "public",
    ):
        super().__init__(namespace, workspace, global_config)
        self.engine = engine or default_engine
        self.schema = (schema or "public").strip() or "public"
        self.nodes_table = f"{self.schema}.kg_nodes"
        self.edges_table = f"{self.schema}.kg_edges"

    async def initialize(self):
        self._ensure_supported()
        self._ensure_schema()
        logger.info(f"初始化Postgres图存储: namespace={self.namespace}")

    async def finalize(self):
        logger.info(f"清理Postgres图存储: namespace={self.namespace}")

    def _ensure_supported(self):
        db_type = getattr(settings.database, "DB_DATABASE_TYPE", "mysql")
        if (db_type or "").lower() not in {"postgresql", "postgres"}:
            raise RuntimeError(
                f"PostgresGraphStorage 需要 DB_DATABASE_TYPE=postgresql/postgres，当前: {db_type}"
            )

    def _ensure_schema(self):
        ddl = f"""
        CREATE SCHEMA IF NOT EXISTS {self.schema};

        CREATE TABLE IF NOT EXISTS {self.nodes_table} (
            namespace TEXT NOT NULL,
            id TEXT NOT NULL,
            name TEXT,
            description TEXT,
            node_type TEXT DEFAULT '{GraphNodeType.ENTITY.value}',
            labels JSONB NOT NULL DEFAULT '[]'::jsonb,
            properties JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            PRIMARY KEY (namespace, id)
        );

        CREATE TABLE IF NOT EXISTS {self.edges_table} (
            namespace TEXT NOT NULL,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            type TEXT NOT NULL,
            description TEXT,
            edge_type TEXT DEFAULT '{GraphEdgeType.RELATES_TO.value}',
            properties JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            PRIMARY KEY (namespace, source_id, target_id, type)
        );

        CREATE INDEX IF NOT EXISTS kg_nodes_namespace_idx ON {self.nodes_table} (namespace);
        CREATE INDEX IF NOT EXISTS kg_nodes_name_idx ON {self.nodes_table} (namespace, name);
        CREATE INDEX IF NOT EXISTS kg_nodes_type_idx ON {self.nodes_table} (namespace, node_type);

        CREATE INDEX IF NOT EXISTS kg_edges_namespace_idx ON {self.edges_table} (namespace);
        CREATE INDEX IF NOT EXISTS kg_edges_type_idx ON {self.edges_table} (namespace, type);
        CREATE INDEX IF NOT EXISTS kg_edges_src_idx ON {self.edges_table} (namespace, source_id);
        CREATE INDEX IF NOT EXISTS kg_edges_tgt_idx ON {self.edges_table} (namespace, target_id);
        CREATE INDEX IF NOT EXISTS kg_edges_src_type_idx ON {self.edges_table} (namespace, source_id, type);
        CREATE INDEX IF NOT EXISTS kg_edges_tgt_type_idx ON {self.edges_table} (namespace, target_id, type);
        """
        with self.engine.begin() as conn:
            conn.execute(text(ddl))

    # ---- node ops ----
    async def has_node(self, node_id: str) -> bool:
        with self.engine.begin() as conn:
            row = conn.execute(
                text(f"SELECT 1 FROM {self.nodes_table} WHERE namespace=:ns AND id=:id LIMIT 1"),
                {"ns": self.namespace, "id": node_id},
            ).first()
        return row is not None

    async def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    f"""
                    SELECT id, name, description, node_type, labels, properties, created_at, updated_at
                    FROM {self.nodes_table}
                    WHERE namespace=:ns AND id=:id
                    """
                ),
                {"ns": self.namespace, "id": node_id},
            ).first()
        if not row:
            return None
        return {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "node_type": row[3] or GraphNodeType.ENTITY.value,
            "labels": row[4] or [],
            "properties": row[5] or {},
            "created_at": row[6].isoformat() if row[6] else None,
            "updated_at": row[7].isoformat() if row[7] else None,
        }

    async def get_nodes_batch(self, node_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        if not node_ids:
            return {}
        stmt = (
            text(
                f"""
                SELECT id, name, description, node_type, labels, properties, created_at, updated_at
                FROM {self.nodes_table}
                WHERE namespace=:ns AND id IN :ids
                """
            )
            .bindparams(bindparam("ids", expanding=True))
        )
        with self.engine.begin() as conn:
            rows = conn.execute(stmt, {"ns": self.namespace, "ids": node_ids}).fetchall()
        result: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            result[str(r[0])] = {
                "id": r[0],
                "name": r[1],
                "description": r[2],
                "node_type": r[3] or GraphNodeType.ENTITY.value,
                "labels": r[4] or [],
                "properties": r[5] or {},
                "created_at": r[6].isoformat() if r[6] else None,
                "updated_at": r[7].isoformat() if r[7] else None,
            }
        return result

    async def upsert_node(self, node_id: str, labels: List[str], properties: Dict[str, Any]) -> bool:
        try:
            name = (properties or {}).get("name")
            description = (properties or {}).get("description")
            node_type = (properties or {}).get("node_type") or GraphNodeType.ENTITY.value
            labels_json = json.dumps(labels or [], ensure_ascii=False)
            props_json = json.dumps(properties or {}, ensure_ascii=False)
            stmt = text(
                f"""
                INSERT INTO {self.nodes_table}
                    (namespace, id, name, description, node_type, labels, properties, created_at, updated_at)
                VALUES
                    (:ns, :id, :name, :desc, :node_type, (:labels)::jsonb, (:props)::jsonb, NOW(), NOW())
                ON CONFLICT (namespace, id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    node_type = EXCLUDED.node_type,
                    labels = EXCLUDED.labels,
                    properties = EXCLUDED.properties,
                    updated_at = NOW()
                """
            )
            with self.engine.begin() as conn:
                conn.execute(
                    stmt,
                    {
                        "ns": self.namespace,
                        "id": node_id,
                        "name": name,
                        "desc": description,
                        "node_type": node_type,
                        "labels": labels_json,
                        "props": props_json,
                    },
                )
            return True
        except Exception as e:
            logger.error(f"upsert_node失败: {e}")
            return False

    async def upsert_nodes_batch(self, nodes: List[Tuple[str, List[str], Dict[str, Any]]]) -> bool:
        try:
            for node_id, labels, properties in nodes:
                await self.upsert_node(node_id, labels, properties)
            return True
        except Exception as e:
            logger.error(f"upsert_nodes_batch失败: {e}")
            return False

    # ---- edge ops ----
    async def has_edge(self, source_node_id: str, target_node_id: str) -> bool:
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    f"""
                    SELECT 1
                    FROM {self.edges_table}
                    WHERE namespace=:ns AND source_id=:s AND target_id=:t
                    LIMIT 1
                    """
                ),
                {"ns": self.namespace, "s": source_node_id, "t": target_node_id},
            ).first()
        return row is not None

    async def get_edge(self, source_node_id: str, target_node_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    f"""
                    SELECT source_id, target_id, type, description, edge_type, properties, created_at, updated_at
                    FROM {self.edges_table}
                    WHERE namespace=:ns AND source_id=:s AND target_id=:t
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """
                ),
                {"ns": self.namespace, "s": source_node_id, "t": target_node_id},
            ).first()
        if not row:
            return None
        return {
            "source": row[0],
            "target": row[1],
            "type": row[2],
            "description": row[3],
            "edge_type": row[4] or GraphEdgeType.RELATES_TO.value,
            "properties": row[5] or {},
            "created_at": row[6].isoformat() if row[6] else None,
            "updated_at": row[7].isoformat() if row[7] else None,
        }

    async def get_edges_batch(self, pairs: List[Dict[str, str]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
        if not pairs:
            return {}
        result: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for p in pairs:
            s = p.get("source") or p.get("source_id")
            t = p.get("target") or p.get("target_id")
            if not s or not t:
                continue
            e = await self.get_edge(s, t)
            if e:
                result[(s, t)] = e
        return result

    async def upsert_edge(
        self, source_node_id: str, target_node_id: str, edge_type: str, properties: Dict[str, Any]
    ) -> bool:
        try:
            if not await self.has_node(source_node_id):
                await self.upsert_node(source_node_id, [], {"name": source_node_id})
            if not await self.has_node(target_node_id):
                await self.upsert_node(target_node_id, [], {"name": target_node_id})

            description = (properties or {}).get("description")
            edge_type_enum = (properties or {}).get("edge_type") or GraphEdgeType.RELATES_TO.value
            props_json = json.dumps(properties or {}, ensure_ascii=False)
            stmt = text(
                f"""
                INSERT INTO {self.edges_table}
                    (namespace, source_id, target_id, type, description, edge_type, properties, created_at, updated_at)
                VALUES
                    (:ns, :s, :t, :type, :desc, :edge_type, (:props)::jsonb, NOW(), NOW())
                ON CONFLICT (namespace, source_id, target_id, type) DO UPDATE SET
                    description = EXCLUDED.description,
                    edge_type = EXCLUDED.edge_type,
                    properties = EXCLUDED.properties,
                    updated_at = NOW()
                """
            )
            with self.engine.begin() as conn:
                conn.execute(
                    stmt,
                    {
                        "ns": self.namespace,
                        "s": source_node_id,
                        "t": target_node_id,
                        "type": edge_type or GraphEdgeType.RELATES_TO.value,
                        "desc": description,
                        "edge_type": edge_type_enum,
                        "props": props_json,
                    },
                )
            return True
        except Exception as e:
            logger.error(f"upsert_edge失败: {e}")
            return False

    async def upsert_edges_batch(self, edges: List[Tuple[str, str, str, Dict[str, Any]]]) -> bool:
        try:
            for source, target, edge_type, properties in edges:
                await self.upsert_edge(source, target, edge_type, properties)
            return True
        except Exception as e:
            logger.error(f"upsert_edges_batch失败: {e}")
            return False

    # ---- graph queries ----
    async def get_knowledge_graph(self, node_label: str, max_depth: int = 3, max_nodes: int = 100) -> KnowledgeGraph:
        kg = KnowledgeGraph(nodes=[], edges=[], is_truncated=False)
        if not node_label:
            return kg

        with self.engine.begin() as conn:
            start_rows = conn.execute(
                text(
                    f"""
                    SELECT id, labels, properties, node_type, created_at, updated_at, name, description
                    FROM {self.nodes_table}
                    WHERE namespace=:ns
                      AND (
                            (labels ? :label)
                         OR (name ILIKE :q)
                      )
                    LIMIT 20
                    """
                ),
                {"ns": self.namespace, "label": node_label, "q": f"%{node_label}%"},
            ).fetchall()

        frontier = [r[0] for r in start_rows]
        visited = set(frontier)

        for r in start_rows:
            kg.nodes.append(
                KnowledgeGraphNode(
                    id=str(r[0]),
                    labels=list(r[1] or []),
                    properties=(r[2] or {}),
                    node_type=GraphNodeType((r[3] or GraphNodeType.ENTITY.value)),
                    created_at=r[4],
                    updated_at=r[5],
                )
            )

        depth = 0
        while frontier and depth < max_depth and len(visited) < max_nodes:
            depth += 1

            stmt = (
                text(
                    f"""
                    SELECT source_id, target_id, type, properties, edge_type, created_at, updated_at, description
                    FROM {self.edges_table}
                    WHERE namespace=:ns
                      AND (source_id IN :ids OR target_id IN :ids)
                    LIMIT 500
                    """
                )
                .bindparams(bindparam("ids", expanding=True))
            )
            with self.engine.begin() as conn:
                edge_rows = conn.execute(stmt, {"ns": self.namespace, "ids": list(frontier)}).fetchall()

            next_frontier: List[str] = []
            for e in edge_rows:
                s, t = str(e[0]), str(e[1])
                edge_id = f"{s}->{t}:{e[2]}"
                kg.edges.append(
                    KnowledgeGraphEdge(
                        id=edge_id,
                        type=str(e[2]),
                        source=s,
                        target=t,
                        properties=(e[3] or {}),
                        edge_type=GraphEdgeType((e[4] or GraphEdgeType.RELATES_TO.value)),
                        created_at=e[5],
                        updated_at=e[6],
                    )
                )

                for nid in (s, t):
                    if nid not in visited and len(visited) < max_nodes:
                        visited.add(nid)
                        next_frontier.append(nid)

            frontier = next_frontier

        if len(visited) >= max_nodes:
            kg.is_truncated = True

        nodes_map = await self.get_nodes_batch(list(visited))
        kg.nodes = [
            KnowledgeGraphNode(
                id=nid,
                labels=list((nodes_map.get(nid, {}).get("labels") or [])),
                properties=(nodes_map.get(nid, {}).get("properties") or {}),
                node_type=GraphNodeType(
                    (nodes_map.get(nid, {}).get("node_type") or GraphNodeType.ENTITY.value)
                ),
            )
            for nid in nodes_map.keys()
        ]
        return kg

    async def search_nodes(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        if not query:
            return []
        q = f"%{query}%"
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT id, name, description, node_type, labels, properties, created_at, updated_at
                    FROM {self.nodes_table}
                    WHERE namespace=:ns
                      AND (
                           name ILIKE :q
                        OR description ILIKE :q
                        OR properties::text ILIKE :q
                      )
                    ORDER BY updated_at DESC
                    LIMIT :limit
                    """
                ),
                {"ns": self.namespace, "q": q, "limit": limit},
            ).fetchall()
        return [
            {
                "id": r[0],
                "name": r[1],
                "description": r[2],
                "node_type": r[3] or GraphNodeType.ENTITY.value,
                "labels": r[4] or [],
                "properties": r[5] or {},
                "created_at": r[6].isoformat() if r[6] else None,
                "updated_at": r[7].isoformat() if r[7] else None,
            }
            for r in rows
        ]

    async def search_edges(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        if not query:
            return []
        q = f"%{query}%"
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT source_id, target_id, type, description, edge_type, properties, created_at, updated_at
                    FROM {self.edges_table}
                    WHERE namespace=:ns
                      AND (
                           type ILIKE :q
                        OR description ILIKE :q
                        OR properties::text ILIKE :q
                      )
                    ORDER BY updated_at DESC
                    LIMIT :limit
                    """
                ),
                {"ns": self.namespace, "q": q, "limit": limit},
            ).fetchall()
        return [
            {
                "source": r[0],
                "target": r[1],
                "type": r[2],
                "description": r[3],
                "edge_type": r[4] or GraphEdgeType.RELATES_TO.value,
                "properties": r[5] or {},
                "created_at": r[6].isoformat() if r[6] else None,
                "updated_at": r[7].isoformat() if r[7] else None,
            }
            for r in rows
        ]

    async def query_nodes(
        self,
        *,
        query: Optional[str] = None,
        node_type: Optional[str] = None,
        document_id: Optional[str] = None,
        node_ids: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        conditions = ["namespace = :ns"]
        params: Dict[str, Any] = {"ns": self.namespace, "limit": limit}

        if query:
            params["query"] = f"%{query}%"
            conditions.append(
                "(name ILIKE :query OR description ILIKE :query OR properties::text ILIKE :query)"
            )
        if node_type:
            params["node_type"] = node_type
            conditions.append("(node_type = :node_type OR labels ? :node_type)")
        if document_id:
            params["document_id"] = document_id
            conditions.append("(properties->>'source_doc') = :document_id")

        stmt = text(
            f"""
            SELECT
                id,
                name,
                description,
                node_type,
                labels,
                properties,
                created_at,
                updated_at,
                properties->>'source_doc' AS source_doc
            FROM {self.nodes_table}
            WHERE {' AND '.join(conditions)}
            ORDER BY updated_at DESC
            LIMIT :limit
            """
        )

        if node_ids:
            stmt = stmt.bindparams(bindparam("node_ids", expanding=True))
            conditions.append("id IN :node_ids")
            params["node_ids"] = list(node_ids)
            stmt = text(
                f"""
                SELECT
                    id,
                    name,
                    description,
                    node_type,
                    labels,
                    properties,
                    created_at,
                    updated_at,
                    properties->>'source_doc' AS source_doc
                FROM {self.nodes_table}
                WHERE {' AND '.join(conditions)}
                ORDER BY updated_at DESC
                LIMIT :limit
                """
            ).bindparams(bindparam("node_ids", expanding=True))

        with self.engine.begin() as conn:
            rows = conn.execute(stmt, params).fetchall()

        return [
            {
                "id": r[0],
                "name": r[1],
                "description": r[2],
                "node_type": r[3] or GraphNodeType.ENTITY.value,
                "labels": r[4] or [],
                "properties": r[5] or {},
                "created_at": r[6].isoformat() if r[6] else None,
                "updated_at": r[7].isoformat() if r[7] else None,
                "source_doc": r[8],
            }
            for r in rows
        ]

    async def query_edges(
        self,
        *,
        query: Optional[str] = None,
        document_id: Optional[str] = None,
        node_ids: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        conditions = ["e.namespace = :ns"]
        params: Dict[str, Any] = {"ns": self.namespace, "limit": limit}

        if query:
            params["query"] = f"%{query}%"
            conditions.append(
                """
                (
                    e.type ILIKE :query
                    OR e.description ILIKE :query
                    OR e.properties::text ILIKE :query
                    OR src.name ILIKE :query
                    OR tgt.name ILIKE :query
                )
                """
            )
        if document_id:
            params["document_id"] = document_id
            conditions.append(
                """
                (
                    e.properties->>'source_doc' = :document_id
                    OR src.properties->>'source_doc' = :document_id
                    OR tgt.properties->>'source_doc' = :document_id
                )
                """
            )

        stmt_sql = f"""
            SELECT
                e.source_id,
                e.target_id,
                e.type,
                e.description,
                e.edge_type,
                e.properties,
                e.created_at,
                e.updated_at,
                COALESCE(
                    e.properties->>'source_doc',
                    src.properties->>'source_doc',
                    tgt.properties->>'source_doc'
                ) AS source_doc
            FROM {self.edges_table} e
            LEFT JOIN {self.nodes_table} src
                ON src.namespace = e.namespace AND src.id = e.source_id
            LEFT JOIN {self.nodes_table} tgt
                ON tgt.namespace = e.namespace AND tgt.id = e.target_id
            WHERE {' AND '.join(conditions)}
            ORDER BY e.updated_at DESC
            LIMIT :limit
        """

        if node_ids:
            conditions.append("(e.source_id IN :node_ids OR e.target_id IN :node_ids)")
            params["node_ids"] = list(node_ids)
            stmt_sql = f"""
                SELECT
                    e.source_id,
                    e.target_id,
                    e.type,
                    e.description,
                    e.edge_type,
                    e.properties,
                    e.created_at,
                    e.updated_at,
                    COALESCE(
                        e.properties->>'source_doc',
                        src.properties->>'source_doc',
                        tgt.properties->>'source_doc'
                    ) AS source_doc
                FROM {self.edges_table} e
                LEFT JOIN {self.nodes_table} src
                    ON src.namespace = e.namespace AND src.id = e.source_id
                LEFT JOIN {self.nodes_table} tgt
                    ON tgt.namespace = e.namespace AND tgt.id = e.target_id
                WHERE {' AND '.join(conditions)}
                ORDER BY e.updated_at DESC
                LIMIT :limit
            """

        stmt = text(stmt_sql)
        if node_ids:
            stmt = stmt.bindparams(bindparam("node_ids", expanding=True))

        with self.engine.begin() as conn:
            rows = conn.execute(stmt, params).fetchall()

        return [
            {
                "source": r[0],
                "target": r[1],
                "type": r[2],
                "description": r[3],
                "edge_type": r[4] or GraphEdgeType.RELATES_TO.value,
                "properties": r[5] or {},
                "created_at": r[6].isoformat() if r[6] else None,
                "updated_at": r[7].isoformat() if r[7] else None,
                "source_doc": r[8],
            }
            for r in rows
        ]

    async def list_document_entities(
        self,
        document_id: str,
        *,
        content_name: str = "",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        conditions = ["namespace = :ns"]
        params: Dict[str, Any] = {
            "ns": self.namespace,
            "document_id": document_id,
            "limit": limit,
        }

        if content_name:
            params["content_name"] = f"%{content_name}%"
            conditions.append(
                "((properties->>'source_doc') = :document_id OR name ILIKE :content_name)"
            )
        else:
            conditions.append("(properties->>'source_doc') = :document_id")

        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT
                        id,
                        name,
                        description,
                        node_type,
                        labels,
                        properties,
                        created_at,
                        updated_at,
                        properties->>'source_doc' AS source_doc
                    FROM {self.nodes_table}
                    WHERE {' AND '.join(conditions)}
                    ORDER BY
                        CASE WHEN (properties->>'source_doc') = :document_id THEN 0 ELSE 1 END,
                        updated_at DESC
                    LIMIT :limit
                    """
                ),
                params,
            ).fetchall()

        return [
            {
                "id": r[0],
                "name": r[1],
                "description": r[2],
                "node_type": r[3] or GraphNodeType.ENTITY.value,
                "labels": r[4] or [],
                "properties": r[5] or {},
                "created_at": r[6].isoformat() if r[6] else None,
                "updated_at": r[7].isoformat() if r[7] else None,
                "source_doc": r[8],
            }
            for r in rows
        ]

    async def get_statistics(self) -> Dict[str, Any]:
        with self.engine.begin() as conn:
            node_total = conn.execute(
                text(f"SELECT COUNT(*) FROM {self.nodes_table} WHERE namespace=:ns"),
                {"ns": self.namespace},
            ).scalar() or 0
            edge_total = conn.execute(
                text(f"SELECT COUNT(*) FROM {self.edges_table} WHERE namespace=:ns"),
                {"ns": self.namespace},
            ).scalar() or 0
            node_rows = conn.execute(
                text(
                    f"""
                    SELECT COALESCE(node_type, :default_type) AS node_type, COUNT(*)
                    FROM {self.nodes_table}
                    WHERE namespace=:ns
                    GROUP BY COALESCE(node_type, :default_type)
                    """
                ),
                {"ns": self.namespace, "default_type": GraphNodeType.ENTITY.value},
            ).fetchall()
            edge_rows = conn.execute(
                text(
                    f"""
                    SELECT COALESCE(type, :default_type) AS edge_type, COUNT(*)
                    FROM {self.edges_table}
                    WHERE namespace=:ns
                    GROUP BY COALESCE(type, :default_type)
                    """
                ),
                {"ns": self.namespace, "default_type": GraphEdgeType.RELATES_TO.value},
            ).fetchall()

        return {
            "total_nodes": int(node_total),
            "total_edges": int(edge_total),
            "node_types": {str(row[0]): int(row[1]) for row in node_rows},
            "edge_types": {str(row[0]): int(row[1]) for row in edge_rows},
        }

    async def delete_node(self, node_id: str) -> bool:
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text(f"DELETE FROM {self.nodes_table} WHERE namespace=:ns AND id=:id"),
                    {"ns": self.namespace, "id": node_id},
                )
                conn.execute(
                    text(
                        f"""
                        DELETE FROM {self.edges_table}
                        WHERE namespace=:ns AND (source_id=:id OR target_id=:id)
                        """
                    ),
                    {"ns": self.namespace, "id": node_id},
                )
            return True
        except Exception as e:
            logger.error(f"delete_node失败: {e}")
            return False

    async def delete_edge(self, source_node_id: str, target_node_id: str) -> bool:
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        f"""
                        DELETE FROM {self.edges_table}
                        WHERE namespace=:ns AND source_id=:s AND target_id=:t
                        """
                    ),
                    {"ns": self.namespace, "s": source_node_id, "t": target_node_id},
                )
            return True
        except Exception as e:
            logger.error(f"delete_edge失败: {e}")
            return False

    async def clear(self) -> bool:
        try:
            with self.engine.begin() as conn:
                conn.execute(text(f"DELETE FROM {self.edges_table} WHERE namespace=:ns"), {"ns": self.namespace})
                conn.execute(text(f"DELETE FROM {self.nodes_table} WHERE namespace=:ns"), {"ns": self.namespace})
            return True
        except Exception as e:
            logger.error(f"clear失败: {e}")
            return False

    async def find_related_documents(
        self,
        doc_id: str,
        *,
        max_hops: int = 2,
        limit: int = 10,
        vector_collection: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """基于 doc->entity 与 entity->entity 扩展，返回相关文档（doc_id 不带 doc_ 前缀）。"""
        doc_id = (doc_id or "").strip()
        if not doc_id:
            return []
        doc_node_id = f"doc_{doc_id}"

        max_hops = int(max_hops or 0)
        limit = int(limit or 0)
        if max_hops <= 0 or limit <= 0:
            return []
        max_entity_depth = max(0, max_hops - 1)

        collection_filter_sql = ""
        params: Dict[str, Any] = {
            "ns": self.namespace,
            "doc_node": doc_node_id,
            "max_entity_depth": max_entity_depth,
            "limit": limit,
        }
        if vector_collection:
            collection_filter_sql = " AND (d.properties->>'vector_collection') = :vector_collection"
            params["vector_collection"] = vector_collection

        sql = f"""
        WITH RECURSIVE seed(entity_id, depth) AS (
            SELECT e.target_id, 0
            FROM {self.edges_table} e
            JOIN {self.nodes_table} n
              ON n.namespace = e.namespace AND n.id = e.target_id AND n.node_type = '{GraphNodeType.ENTITY.value}'
            WHERE e.namespace = :ns AND e.source_id = :doc_node AND e.type = '{GraphEdgeType.CONTAINS.value}'
        ),
        expand(entity_id, depth) AS (
            SELECT entity_id, 0 FROM seed
            UNION ALL
            SELECT
                CASE WHEN ge.source_id = ex.entity_id THEN ge.target_id ELSE ge.source_id END AS entity_id,
                ex.depth + 1 AS depth
            FROM {self.edges_table} ge
            JOIN expand ex
              ON (ge.source_id = ex.entity_id OR ge.target_id = ex.entity_id)
            JOIN {self.nodes_table} n2
              ON n2.namespace = ge.namespace
             AND n2.id = CASE WHEN ge.source_id = ex.entity_id THEN ge.target_id ELSE ge.source_id END
             AND n2.node_type = '{GraphNodeType.ENTITY.value}'
            WHERE ge.namespace = :ns
              AND ge.type <> '{GraphEdgeType.CONTAINS.value}'
              AND ex.depth < :max_entity_depth
        ),
        entity_best AS (
            SELECT entity_id, MIN(depth) AS depth
            FROM expand
            GROUP BY entity_id
        ),
        doc_hits AS (
            SELECT
                ge.source_id AS doc_node_id,
                MIN(entity_best.depth) AS min_depth,
                COUNT(*) AS match_count,
                array_agg(DISTINCT entity_best.entity_id) AS via_entities
            FROM {self.edges_table} ge
            JOIN {self.nodes_table} d
              ON d.namespace = ge.namespace AND d.id = ge.source_id AND d.node_type = '{GraphNodeType.DOCUMENT.value}'
            JOIN entity_best
              ON entity_best.entity_id = ge.target_id
            WHERE ge.namespace = :ns
              AND ge.type = '{GraphEdgeType.CONTAINS.value}'
              AND ge.source_id <> :doc_node
              {collection_filter_sql}
            GROUP BY ge.source_id
        )
        SELECT doc_node_id, (min_depth + 1) AS hop_distance, match_count, via_entities
        FROM doc_hits
        ORDER BY hop_distance ASC, match_count DESC
        LIMIT :limit
        """

        with self.engine.begin() as conn:
            rows = conn.execute(text(sql), params).fetchall()

        results: List[Dict[str, Any]] = []
        for r in rows:
            doc_node = str(r[0] or "")
            if not doc_node.startswith("doc_"):
                continue
            rid = doc_node[len("doc_") :]
            results.append(
                {
                    "doc_id": rid,
                    "doc_node_id": doc_node,
                    "hop_distance": int(r[1] or 1),
                    "match_count": int(r[2] or 0),
                    "via_entities": list(r[3] or []),
                }
            )
        return results
