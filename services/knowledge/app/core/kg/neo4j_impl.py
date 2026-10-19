#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo4j图存储实现
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from app.core.kg.base import BaseGraphStorage, KnowledgeGraph, KnowledgeGraphNode, KnowledgeGraphEdge
from app.config import settings
from app.core.llm import create_embedding_model

logger = logging.getLogger(__name__)

try:
    from neo4j import AsyncGraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logger.warning("Neo4j驱动未安装，请运行: pip install neo4j")


class Neo4JGraphStorage(BaseGraphStorage):
    """基于Neo4j的图存储实现"""

    def __init__(self, namespace: str, workspace: str = "", global_config: Dict[str, Any] = None):
        super().__init__(namespace, workspace, global_config)

        if not NEO4J_AVAILABLE:
            raise ImportError("Neo4j驱动未安装，请运行: pip install neo4j")

        if not settings.graph_db.is_configured:
            raise ValueError("Neo4j未正确配置，请检查环境变量")

        self.neo4j_config = settings.graph_db.neo4j_config
        self._driver = None
        self.embedding_model = create_embedding_model()

    async def initialize(self):
        """初始化Neo4j连接"""
        try:
            self._driver = AsyncGraphDatabase.driver(
                self.neo4j_config["uri"],
                auth=(self.neo4j_config["username"], self.neo4j_config["password"])
            )

            # 测试连接
            async with self._driver.session() as session:
                result = await session.run("RETURN 1 as test")
                await result.consume()

            logger.info(f"Neo4j连接成功: {self.neo4j_config['uri']}")

        except Exception as e:
            logger.error(f"Neo4j连接失败: {e}")
            raise

    async def finalize(self):
        """清理Neo4j连接"""
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("Neo4j连接已关闭")

    async def has_node(self, node_id: str) -> bool:
        """检查节点是否存在"""
        try:
            async with self._driver.session() as session:
                query = "MATCH (n {entity_id: $node_id}) RETURN count(n) > 0 as exists"
                result = await session.run(query, node_id=node_id)
                record = await result.single()
                await result.consume()
                return record["exists"]
        except Exception as e:
            logger.error(f"检查节点存在失败: {e}")
            return False

    async def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取节点"""
        try:
            async with self._driver.session() as session:
                query = "MATCH (n {entity_id: $node_id}) RETURN n"
                result = await session.run(query, node_id=node_id)
                record = await result.single()
                await result.consume()

                if record:
                    node = record["n"]
                    return {
                        "id": node.get("entity_id"),
                        "labels": list(node.labels),
                        "properties": dict(node)
                    }
                return None
        except Exception as e:
            logger.error(f"获取节点失败: {e}")
            return None

    async def get_nodes_batch(self, node_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量获取节点"""
        results = {}
        for node_id in node_ids:
            node_data = await self.get_node(node_id)
            if node_data:
                results[node_id] = node_data
        return results

    async def upsert_node(self, node_id: str, labels: List[str], properties: Dict[str, Any]) -> bool:
        """插入或更新节点"""
        try:
            node_properties = {
                "entity_id": node_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                **properties
            }

            label_str = ":".join(labels) if labels else "Entity"

            async with self._driver.session() as session:
                query = f"""
                MERGE (n:{label_str} {{entity_id: $node_id}})
                SET n += $properties
                RETURN n
                """
                result = await session.run(query, node_id=node_id, properties=node_properties)
                await result.consume()

            logger.debug(f"节点 {node_id} 已更新")
            return True

        except Exception as e:
            logger.error(f"更新节点失败: {e}")
            return False

    async def upsert_nodes_batch(self, nodes: List[Tuple[str, List[str], Dict[str, Any]]]) -> bool:
        """批量插入或更新节点"""
        try:
            for node_id, labels, properties in nodes:
                await self.upsert_node(node_id, labels, properties)
            return True
        except Exception as e:
            logger.error(f"批量更新节点失败: {e}")
            return False

    async def has_edge(self, source_node_id: str, target_node_id: str) -> bool:
        """检查边是否存在"""
        try:
            async with self._driver.session() as session:
                query = """
                MATCH (a {entity_id: $source_id})-[r]-(b {entity_id: $target_id})
                RETURN count(r) > 0 as exists
                """
                result = await session.run(query, source_id=source_node_id, target_id=target_node_id)
                record = await result.single()
                await result.consume()
                return record["exists"]
        except Exception as e:
            logger.error(f"检查边存在失败: {e}")
            return False

    async def get_edge(self, source_node_id: str, target_node_id: str) -> Optional[Dict[str, Any]]:
        """获取边"""
        try:
            async with self._driver.session() as session:
                query = """
                MATCH (a {entity_id: $source_id})-[r]-(b {entity_id: $target_id})
                RETURN r
                """
                result = await session.run(query, source_id=source_node_id, target_id=target_node_id)
                record = await result.single()
                await result.consume()

                if record:
                    rel = record["r"]
                    return {
                        "source": source_node_id,
                        "target": target_node_id,
                        "type": rel.type,
                        "properties": dict(rel)
                    }
                return None
        except Exception as e:
            logger.error(f"获取边失败: {e}")
            return None

    async def get_edges_batch(self, pairs: List[Dict[str, str]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
        """批量获取边"""
        results = {}
        for pair in pairs:
            source = pair.get("source")
            target = pair.get("target")
            if source and target:
                edge_data = await self.get_edge(source, target)
                if edge_data:
                    results[(source, target)] = edge_data
        return results

    async def upsert_edge(self, source_node_id: str, target_node_id: str,
                         edge_type: str, properties: Dict[str, Any]) -> bool:
        """插入或更新边"""
        try:
            if not await self.has_node(source_node_id):
                await self.upsert_node(source_node_id, ["Entity"], {"name": source_node_id})

            if not await self.has_node(target_node_id):
                await self.upsert_node(target_node_id, ["Entity"], {"name": target_node_id})

            edge_properties = {
                "relationship_id": f"{source_node_id}_{target_node_id}_{edge_type}",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                **properties
            }

            async with self._driver.session() as session:
                # 关系类型不能参数化，需要直接拼接到查询中
                # 清理关系类型名称，确保它是有效的Neo4j标识符
                safe_edge_type = edge_type.replace(" ", "_").replace("-", "_").upper()

                query = f"""
                MATCH (a {{entity_id: $source_id}}), (b {{entity_id: $target_id}})
                MERGE (a)-[r:{safe_edge_type}]->(b)
                SET r += $properties
                RETURN r
                """
                result = await session.run(
                    query,
                    source_id=source_node_id,
                    target_id=target_node_id,
                    properties=edge_properties
                )
                await result.consume()

            logger.debug(f"边 {source_node_id} -> {target_node_id} 已更新")
            return True

        except Exception as e:
            logger.error(f"更新边失败: {e}")
            return False

    async def upsert_edges_batch(self, edges: List[Tuple[str, str, str, Dict[str, Any]]]) -> bool:
        """批量插入或更新边"""
        try:
            for source, target, edge_type, properties in edges:
                await self.upsert_edge(source, target, edge_type, properties)
            return True
        except Exception as e:
            logger.error(f"批量更新边失败: {e}")
            return False

    async def get_knowledge_graph(self, node_label: str, max_depth: int = 3,
                                max_nodes: int = 100) -> KnowledgeGraph:
        """获取知识图谱子图"""
        try:
            result = KnowledgeGraph()

            async with self._driver.session() as session:
                # 检查起始节点是否存在
                check_query = "MATCH (n {entity_id: $node_label}) RETURN n LIMIT 1"
                check_result = await session.run(check_query, node_label=node_label)
                start_record = await check_result.single()
                await check_result.consume()

                if not start_record:
                    logger.warning(f"未找到标签为 {node_label} 的节点")
                    return result

                # 使用简单查询获取子图
                subgraph_query = """
                MATCH (start {entity_id: $node_label})-[r*1..$max_depth]-(related)
                RETURN start, collect(DISTINCT related) as nodes, collect(DISTINCT r) as relationships
                LIMIT $max_nodes
                """

                subgraph_result = await session.run(
                    subgraph_query,
                    node_label=node_label,
                    max_depth=max_depth,
                    max_nodes=max_nodes
                )
                record = await subgraph_result.single()
                await subgraph_result.consume()

                if record:
                    all_nodes = [record["start"]] + record["nodes"]
                    for node in all_nodes:
                        kg_node = KnowledgeGraphNode(
                            id=node.get("entity_id"),
                            labels=list(node.labels),
                            properties=dict(node)
                        )
                        result.nodes.append(kg_node)

            logger.info(f"获取知识图谱子图: {len(result.nodes)} 个节点, {len(result.edges)} 条边")
            return result

        except Exception as e:
            logger.error(f"获取知识图谱失败: {e}")
            return KnowledgeGraph()

    async def search_nodes(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索节点"""
        try:
            async with self._driver.session() as session:
                search_query = """
                MATCH (n)
                WHERE n.name CONTAINS $query OR n.description CONTAINS $query
                RETURN n
                LIMIT $limit
                """
                result = await session.run(search_query, query=query, limit=limit)
                nodes = []
                async for record in result:
                    node = record["n"]
                    nodes.append({
                        "id": node.get("entity_id"),
                        "labels": list(node.labels),
                        "properties": dict(node),
                        "similarity": 0.8
                    })
                await result.consume()
                return nodes

        except Exception as e:
            logger.error(f"搜索节点失败: {e}")
            return []

    async def search_edges(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索边"""
        try:
            async with self._driver.session() as session:
                search_query = """
                MATCH ()-[r]-()
                WHERE r.description CONTAINS $query OR type(r) CONTAINS $query
                RETURN r
                LIMIT $limit
                """
                result = await session.run(search_query, query=query, limit=limit)
                edges = []
                async for record in result:
                    rel = record["r"]
                    edges.append({
                        "type": rel.type,
                        "properties": dict(rel),
                        "similarity": 0.8
                    })
                await result.consume()
                return edges

        except Exception as e:
            logger.error(f"搜索边失败: {e}")
            return []

    async def query_nodes(
        self,
        *,
        query: Optional[str] = None,
        node_type: Optional[str] = None,
        document_id: Optional[str] = None,
        node_ids: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        try:
            filters = ["1 = 1"]
            params: Dict[str, Any] = {"limit": limit}

            if query:
                filters.append(
                    "(n.name CONTAINS $query OR n.description CONTAINS $query OR toString(properties(n)) CONTAINS $query)"
                )
                params["query"] = query
            if node_type:
                filters.append("($node_type IN labels(n) OR n.node_type = $node_type)")
                params["node_type"] = node_type
            if document_id:
                filters.append("n.source_doc = $document_id")
                params["document_id"] = document_id
            if node_ids:
                filters.append("n.entity_id IN $node_ids")
                params["node_ids"] = list(node_ids)

            cypher = f"""
            MATCH (n)
            WHERE {' AND '.join(filters)}
            RETURN n
            ORDER BY n.updated_at DESC, n.created_at DESC
            LIMIT $limit
            """

            async with self._driver.session() as session:
                result = await session.run(cypher, **params)
                rows = []
                async for record in result:
                    node = record["n"]
                    rows.append(
                        {
                            "id": node.get("entity_id"),
                            "name": node.get("name"),
                            "description": node.get("description"),
                            "node_type": node.get("node_type"),
                            "labels": list(node.labels),
                            "properties": dict(node),
                            "source_doc": node.get("source_doc"),
                        }
                    )
                await result.consume()
            return rows
        except Exception as e:
            logger.error(f"查询节点失败: {e}")
            return []

    async def query_edges(
        self,
        *,
        query: Optional[str] = None,
        document_id: Optional[str] = None,
        node_ids: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        try:
            filters = ["1 = 1"]
            params: Dict[str, Any] = {"limit": limit}

            if query:
                filters.append(
                    """
                    (
                        type(r) CONTAINS $query
                        OR r.description CONTAINS $query
                        OR toString(properties(r)) CONTAINS $query
                        OR a.name CONTAINS $query
                        OR b.name CONTAINS $query
                    )
                    """
                )
                params["query"] = query
            if document_id:
                filters.append(
                    "(r.source_doc = $document_id OR a.source_doc = $document_id OR b.source_doc = $document_id)"
                )
                params["document_id"] = document_id
            if node_ids:
                filters.append("(a.entity_id IN $node_ids OR b.entity_id IN $node_ids)")
                params["node_ids"] = list(node_ids)

            cypher = f"""
            MATCH (a)-[r]->(b)
            WHERE {' AND '.join(filters)}
            RETURN a.entity_id AS source, b.entity_id AS target, type(r) AS relation_type, r
            ORDER BY r.updated_at DESC, r.created_at DESC
            LIMIT $limit
            """

            async with self._driver.session() as session:
                result = await session.run(cypher, **params)
                rows = []
                async for record in result:
                    rel = record["r"]
                    rows.append(
                        {
                            "source": record["source"],
                            "target": record["target"],
                            "type": record["relation_type"],
                            "description": rel.get("description"),
                            "properties": dict(rel),
                            "source_doc": rel.get("source_doc"),
                        }
                    )
                await result.consume()
            return rows
        except Exception as e:
            logger.error(f"查询边失败: {e}")
            return []

    async def list_document_entities(
        self,
        document_id: str,
        *,
        content_name: str = "",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        query_text = content_name or None
        rows = await self.query_nodes(query=query_text, document_id=document_id, limit=limit)
        if rows:
            return rows[:limit]
        return await self.query_nodes(document_id=document_id, limit=limit)

    async def get_statistics(self) -> Dict[str, Any]:
        try:
            async with self._driver.session() as session:
                node_total_result = await session.run("MATCH (n) RETURN count(n) AS total_nodes")
                node_total_record = await node_total_result.single()
                await node_total_result.consume()

                edge_total_result = await session.run("MATCH ()-[r]->() RETURN count(r) AS total_edges")
                edge_total_record = await edge_total_result.single()
                await edge_total_result.consume()

                node_types_result = await session.run(
                    """
                    MATCH (n)
                    UNWIND CASE
                        WHEN size(labels(n)) = 0 THEN ['entity']
                        ELSE labels(n)
                    END AS label
                    RETURN label, count(*) AS count
                    """
                )
                node_types: Dict[str, int] = {}
                async for record in node_types_result:
                    node_types[str(record["label"])] = int(record["count"])
                await node_types_result.consume()

                edge_types_result = await session.run(
                    "MATCH ()-[r]->() RETURN type(r) AS relation_type, count(*) AS count"
                )
                edge_types: Dict[str, int] = {}
                async for record in edge_types_result:
                    edge_types[str(record["relation_type"])] = int(record["count"])
                await edge_types_result.consume()

            return {
                "total_nodes": int(node_total_record["total_nodes"] if node_total_record else 0),
                "total_edges": int(edge_total_record["total_edges"] if edge_total_record else 0),
                "node_types": node_types,
                "edge_types": edge_types,
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {"total_nodes": 0, "total_edges": 0, "node_types": {}, "edge_types": {}}

    async def delete_node(self, node_id: str) -> bool:
        """删除节点"""
        try:
            async with self._driver.session() as session:
                query = "MATCH (n {entity_id: $node_id}) DETACH DELETE n"
                result = await session.run(query, node_id=node_id)
                await result.consume()
                logger.debug(f"节点 {node_id} 已删除")
                return True
        except Exception as e:
            logger.error(f"删除节点失败: {e}")
            return False

    async def delete_edge(self, source_node_id: str, target_node_id: str) -> bool:
        """删除边"""
        try:
            async with self._driver.session() as session:
                query = """
                MATCH (a {entity_id: $source_id})-[r]-(b {entity_id: $target_id})
                DELETE r
                """
                result = await session.run(query, source_id=source_node_id, target_id=target_node_id)
                await result.consume()
                logger.debug(f"边 {source_node_id} -> {target_node_id} 已删除")
                return True
        except Exception as e:
            logger.error(f"删除边失败: {e}")
            return False

    async def clear(self) -> bool:
        """清空图数据"""
        try:
            async with self._driver.session() as session:
                query = "MATCH (n) DETACH DELETE n"
                result = await session.run(query)
                await result.consume()
                logger.info("Neo4j图数据已清空")
                return True
        except Exception as e:
            logger.error(f"清空图数据失败: {e}")
            return False
