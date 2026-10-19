#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NetworkX图存储实现
"""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional, Tuple, Union
from collections import defaultdict, deque
import networkx as nx
from datetime import datetime

from app.core.kg.base import (
    BaseGraphStorage, KnowledgeGraph, KnowledgeGraphNode, KnowledgeGraphEdge,
    GraphQueryResult, GraphNodeType, GraphEdgeType
)
from app.core.llm import create_embedding_model

logger = logging.getLogger(__name__)


class NetworkXGraphStorage(BaseGraphStorage):
    """基于NetworkX的图存储实现"""

    def __init__(self, namespace: str, workspace: str = "", global_config: Dict[str, Any] = None):
        super().__init__(namespace, workspace, global_config)
        self.graph = nx.MultiDiGraph()  # 使用有向多重图
        self.embedding_model = create_embedding_model()
        self.node_embeddings = {}  # 节点嵌入缓存
        self.edge_embeddings = {}  # 边嵌入缓存

    async def initialize(self):
        """初始化存储"""
        logger.info(f"初始化NetworkX图存储: {self.namespace}")

    async def finalize(self):
        """清理资源"""
        logger.info(f"清理NetworkX图存储: {self.namespace}")
        self.graph.clear()
        self.node_embeddings.clear()
        self.edge_embeddings.clear()

    async def has_node(self, node_id: str) -> bool:
        """检查节点是否存在"""
        return self.graph.has_node(node_id)

    async def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取节点"""
        if not self.graph.has_node(node_id):
            return None

        node_data = self.graph.nodes[node_id]
        return {
            "id": node_id,
            "labels": node_data.get("labels", []),
            "properties": node_data.get("properties", {}),
            "node_type": node_data.get("node_type", GraphNodeType.ENTITY.value),
            "created_at": node_data.get("created_at"),
            "updated_at": node_data.get("updated_at")
        }

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
            node_attrs = {
                "labels": labels,
                "properties": properties,
                "node_type": properties.get("node_type", GraphNodeType.ENTITY.value),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }

            if self.graph.has_node(node_id):
                existing_data = self.graph.nodes[node_id]
                node_attrs["created_at"] = existing_data.get("created_at", node_attrs["created_at"])

            self.graph.add_node(node_id, **node_attrs)
            await self._generate_node_embedding(node_id, properties)

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
        return self.graph.has_edge(source_node_id, target_node_id)

    async def get_edge(self, source_node_id: str, target_node_id: str) -> Optional[Dict[str, Any]]:
        """获取边"""
        if not self.graph.has_edge(source_node_id, target_node_id):
            return None

        edge_data = self.graph.get_edge_data(source_node_id, target_node_id)
        if not edge_data:
            return None

        edge_key = list(edge_data.keys())[0]
        edge_attrs = edge_data[edge_key]

        return {
            "source": source_node_id,
            "target": target_node_id,
            "type": edge_attrs.get("type", "relates_to"),
            "properties": edge_attrs.get("properties", {}),
            "edge_type": edge_attrs.get("edge_type", GraphEdgeType.RELATES_TO.value),
            "created_at": edge_attrs.get("created_at"),
            "updated_at": edge_attrs.get("updated_at")
        }

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
            if not self.graph.has_node(source_node_id):
                await self.upsert_node(source_node_id, [], {"name": source_node_id})

            if not self.graph.has_node(target_node_id):
                await self.upsert_node(target_node_id, [], {"name": target_node_id})

            edge_attrs = {
                "type": edge_type,
                "properties": properties,
                "edge_type": properties.get("edge_type", GraphEdgeType.RELATES_TO.value),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }

            if self.graph.has_edge(source_node_id, target_node_id):
                existing_data = self.graph.get_edge_data(source_node_id, target_node_id)
                if existing_data:
                    edge_key = list(existing_data.keys())[0]
                    edge_attrs["created_at"] = existing_data[edge_key].get("created_at", edge_attrs["created_at"])

            self.graph.add_edge(source_node_id, target_node_id, **edge_attrs)
            await self._generate_edge_embedding(source_node_id, target_node_id, properties)

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
            visited_nodes = set()
            visited_edges = set()

            start_nodes = []
            for node_id in self.graph.nodes():
                node_data = self.graph.nodes[node_id]
                if node_label in node_data.get("labels", []) or node_label == node_id:
                    start_nodes.append(node_id)

            if not start_nodes:
                logger.warning(f"未找到标签为 {node_label} 的节点")
                return result

            queue = deque([(node_id, 0) for node_id in start_nodes])

            while queue and len(visited_nodes) < max_nodes:
                current_node, depth = queue.popleft()

                if current_node in visited_nodes or depth > max_depth:
                    continue

                node_data = self.graph.nodes[current_node]
                kg_node = KnowledgeGraphNode(
                    id=current_node,
                    labels=node_data.get("labels", []),
                    properties=node_data.get("properties", {}),
                    node_type=GraphNodeType(node_data.get("node_type", GraphNodeType.ENTITY.value))
                )
                result.nodes.append(kg_node)
                visited_nodes.add(current_node)

                for neighbor in self.graph.neighbors(current_node):
                    edge_data = self.graph.get_edge_data(current_node, neighbor)
                    if edge_data:
                        edge_key = list(edge_data.keys())[0]
                        edge_attrs = edge_data[edge_key]

                        edge_id = f"{current_node}_{neighbor}_{edge_key}"
                        if edge_id not in visited_edges:
                            kg_edge = KnowledgeGraphEdge(
                                id=edge_id,
                                type=edge_attrs.get("type", "relates_to"),
                                source=current_node,
                                target=neighbor,
                                properties=edge_attrs.get("properties", {}),
                                edge_type=GraphEdgeType(edge_attrs.get("edge_type", GraphEdgeType.RELATES_TO.value))
                            )
                            result.edges.append(kg_edge)
                            visited_edges.add(edge_id)

                        if neighbor not in visited_nodes and depth < max_depth:
                            queue.append((neighbor, depth + 1))

                if len(visited_nodes) >= max_nodes:
                    result.is_truncated = True
                    break

            logger.info(f"获取知识图谱子图: {len(result.nodes)} 个节点, {len(result.edges)} 条边")
            return result

        except Exception as e:
            logger.error(f"获取知识图谱失败: {e}")
            return KnowledgeGraph()

    async def search_nodes(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索节点"""
        try:
            query_embedding, _ = self.embedding_model.encode_queries(query)

            similarities = []
            for node_id in self.graph.nodes():
                if node_id in self.node_embeddings:
                    node_embedding = self.node_embeddings[node_id]
                    similarity = self._compute_similarity(query_embedding, node_embedding)
                    node_data = await self.get_node(node_id)
                    if node_data:
                        similarities.append((similarity, node_data))

            similarities.sort(key=lambda x: x[0], reverse=True)
            return [node_data for _, node_data in similarities[:limit]]

        except Exception as e:
            logger.error(f"搜索节点失败: {e}")
            return []

    async def search_edges(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索边"""
        try:
            query_embedding, _ = self.embedding_model.encode_queries(query)

            similarities = []
            for source, target in self.graph.edges():
                edge_key = f"{source}_{target}"
                if edge_key in self.edge_embeddings:
                    edge_embedding = self.edge_embeddings[edge_key]
                    similarity = self._compute_similarity(query_embedding, edge_embedding)
                    edge_data = await self.get_edge(source, target)
                    if edge_data:
                        similarities.append((similarity, edge_data))

            similarities.sort(key=lambda x: x[0], reverse=True)
            return [edge_data for _, edge_data in similarities[:limit]]

        except Exception as e:
            logger.error(f"搜索边失败: {e}")
            return []

    async def delete_node(self, node_id: str) -> bool:
        """删除节点"""
        try:
            if self.graph.has_node(node_id):
                self.graph.remove_node(node_id)
                if node_id in self.node_embeddings:
                    del self.node_embeddings[node_id]
                logger.debug(f"节点 {node_id} 已删除")
                return True
            return False
        except Exception as e:
            logger.error(f"删除节点失败: {e}")
            return False

    async def delete_edge(self, source_node_id: str, target_node_id: str) -> bool:
        """删除边"""
        try:
            if self.graph.has_edge(source_node_id, target_node_id):
                self.graph.remove_edge(source_node_id, target_node_id)
                edge_key = f"{source_node_id}_{target_node_id}"
                if edge_key in self.edge_embeddings:
                    del self.edge_embeddings[edge_key]
                logger.debug(f"边 {source_node_id} -> {target_node_id} 已删除")
                return True
            return False
        except Exception as e:
            logger.error(f"删除边失败: {e}")
            return False

    async def clear(self) -> bool:
        """清空图数据"""
        try:
            self.graph.clear()
            self.node_embeddings.clear()
            self.edge_embeddings.clear()
            logger.info("图数据已清空")
            return True
        except Exception as e:
            logger.error(f"清空图数据失败: {e}")
            return False

    async def _generate_node_embedding(self, node_id: str, properties: Dict[str, Any]):
        """生成节点嵌入"""
        try:
            text = properties.get("name", "") + " " + properties.get("description", "")
            if text.strip():
                embedding, _ = self.embedding_model.encode([text])
                self.node_embeddings[node_id] = embedding[0]
        except Exception as e:
            logger.warning(f"生成节点嵌入失败: {e}")

    async def _generate_edge_embedding(self, source: str, target: str, properties: Dict[str, Any]):
        """生成边嵌入"""
        try:
            text = properties.get("description", "") + " " + properties.get("type", "")
            if text.strip():
                embedding, _ = self.embedding_model.encode([text])
                edge_key = f"{source}_{target}"
                self.edge_embeddings[edge_key] = embedding[0]
        except Exception as e:
            logger.warning(f"生成边嵌入失败: {e}")

    def _compute_similarity(self, query_embedding, target_embedding):
        """计算相似度"""
        try:
            import numpy as np
            return np.dot(query_embedding, target_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(target_embedding)
            )
        except Exception:
            return 0.0

    def get_graph_stats(self) -> Dict[str, Any]:
        """获取图统计信息"""
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_types": self._get_node_type_distribution(),
            "edge_types": self._get_edge_type_distribution()
        }

    def _get_node_type_distribution(self) -> Dict[str, int]:
        """获取节点类型分布"""
        distribution = defaultdict(int)
        for node_id in self.graph.nodes():
            node_data = self.graph.nodes[node_id]
            node_type = node_data.get("node_type", GraphNodeType.ENTITY.value)
            distribution[node_type] += 1
        return dict(distribution)

    def _get_edge_type_distribution(self) -> Dict[str, int]:
        """获取边类型分布"""
        distribution = defaultdict(int)
        for source, target in self.graph.edges():
            edge_data = self.graph.get_edge_data(source, target)
            if edge_data:
                edge_key = list(edge_data.keys())[0]
                edge_attrs = edge_data[edge_key]
                edge_type = edge_attrs.get("edge_type", GraphEdgeType.RELATES_TO.value)
                distribution[edge_type] += 1
        return dict(distribution)
