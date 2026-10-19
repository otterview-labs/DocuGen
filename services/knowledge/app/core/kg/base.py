#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识图谱基础架构
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
from datetime import datetime
import json
import uuid
from enum import Enum


class GraphNodeType(Enum):
    """图节点类型枚举"""
    ENTITY = "entity"           # 实体节点
    CONCEPT = "concept"         # 概念节点
    DOCUMENT = "document"       # 文档节点
    USER = "user"              # 用户节点
    AGENT = "agent"            # 智能体节点
    EVENT = "event"            # 事件节点
    LOCATION = "location"      # 地点节点
    ORGANIZATION = "organization"  # 组织节点


class GraphEdgeType(Enum):
    """图边类型枚举"""
    RELATES_TO = "relates_to"      # 相关关系
    BELONGS_TO = "belongs_to"      # 属于关系
    CREATED_BY = "created_by"      # 创建者关系
    CONTAINS = "contains"          # 包含关系
    SIMILAR_TO = "similar_to"      # 相似关系
    DEPENDS_ON = "depends_on"      # 依赖关系
    LOCATED_IN = "located_in"      # 位于关系
    WORKS_FOR = "works_for"        # 工作关系
    FRIEND_OF = "friend_of"        # 朋友关系
    PART_OF = "part_of"           # 部分关系


@dataclass
class KnowledgeGraphNode:
    """知识图谱节点"""
    id: str
    labels: List[str]
    properties: Dict[str, Any]
    node_type: GraphNodeType = GraphNodeType.ENTITY
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "labels": self.labels,
            "properties": self.properties,
            "node_type": self.node_type.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeGraphNode':
        """从字典创建"""
        return cls(
            id=data["id"],
            labels=data["labels"],
            properties=data["properties"],
            node_type=GraphNodeType(data["node_type"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"])
        )


@dataclass
class KnowledgeGraphEdge:
    """知识图谱边"""
    id: str
    type: str
    source: str
    target: str
    properties: Dict[str, Any]
    edge_type: GraphEdgeType = GraphEdgeType.RELATES_TO
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "target": self.target,
            "properties": self.properties,
            "edge_type": self.edge_type.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeGraphEdge':
        """从字典创建"""
        return cls(
            id=data["id"],
            type=data["type"],
            source=data["source"],
            target=data["target"],
            properties=data["properties"],
            edge_type=GraphEdgeType(data["edge_type"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"])
        )


@dataclass
class KnowledgeGraph:
    """知识图谱"""
    nodes: List[KnowledgeGraphNode]
    edges: List[KnowledgeGraphEdge]
    is_truncated: bool = False

    def __post_init__(self):
        if self.nodes is None:
            self.nodes = []
        if self.edges is None:
            self.edges = []

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "is_truncated": self.is_truncated
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeGraph':
        """从字典创建"""
        return cls(
            nodes=[KnowledgeGraphNode.from_dict(n) for n in data["nodes"]],
            edges=[KnowledgeGraphEdge.from_dict(e) for e in data["edges"]],
            is_truncated=data.get("is_truncated", False)
        )


class BaseGraphStorage(ABC):
    """图存储基类 - 参考LightRAG设计"""

    def __init__(self, namespace: str, workspace: str = "", global_config: Dict[str, Any] = None):
        self.namespace = namespace
        self.workspace = workspace
        self.global_config = global_config or {}

    @abstractmethod
    async def initialize(self):
        """初始化存储"""
        pass

    @abstractmethod
    async def finalize(self):
        """清理资源"""
        pass

    @abstractmethod
    async def has_node(self, node_id: str) -> bool:
        """检查节点是否存在"""
        pass

    @abstractmethod
    async def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取节点"""
        pass

    @abstractmethod
    async def get_nodes_batch(self, node_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量获取节点"""
        pass

    @abstractmethod
    async def upsert_node(self, node_id: str, labels: List[str], properties: Dict[str, Any]) -> bool:
        """插入或更新节点"""
        pass

    @abstractmethod
    async def upsert_nodes_batch(self, nodes: List[Tuple[str, List[str], Dict[str, Any]]]) -> bool:
        """批量插入或更新节点"""
        pass

    @abstractmethod
    async def has_edge(self, source_node_id: str, target_node_id: str) -> bool:
        """检查边是否存在"""
        pass

    @abstractmethod
    async def get_edge(self, source_node_id: str, target_node_id: str) -> Optional[Dict[str, Any]]:
        """获取边"""
        pass

    @abstractmethod
    async def get_edges_batch(self, pairs: List[Dict[str, str]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
        """批量获取边"""
        pass

    @abstractmethod
    async def upsert_edge(self, source_node_id: str, target_node_id: str,
                         edge_type: str, properties: Dict[str, Any]) -> bool:
        """插入或更新边"""
        pass

    @abstractmethod
    async def upsert_edges_batch(self, edges: List[Tuple[str, str, str, Dict[str, Any]]]) -> bool:
        """批量插入或更新边"""
        pass

    @abstractmethod
    async def get_knowledge_graph(self, node_label: str, max_depth: int = 3,
                                max_nodes: int = 100) -> KnowledgeGraph:
        """获取知识图谱子图"""
        pass

    @abstractmethod
    async def search_nodes(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索节点"""
        pass

    @abstractmethod
    async def search_edges(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索边"""
        pass

    @abstractmethod
    async def delete_node(self, node_id: str) -> bool:
        """删除节点"""
        pass

    @abstractmethod
    async def delete_edge(self, source_node_id: str, target_node_id: str) -> bool:
        """删除边"""
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """清空图数据"""
        pass


class GraphQueryResult:
    """图查询结果"""

    def __init__(self, nodes: List[Dict[str, Any]] = None, edges: List[Dict[str, Any]] = None):
        self.nodes = nodes or []
        self.edges = edges or []
        self.total_nodes = len(self.nodes)
        self.total_edges = len(self.edges)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges
        }

    def merge(self, other: 'GraphQueryResult') -> 'GraphQueryResult':
        """合并查询结果"""
        merged_nodes = self.nodes + other.nodes
        merged_edges = self.edges + other.edges

        # 去重节点
        seen_node_ids = set()
        unique_nodes = []
        for node in merged_nodes:
            if node.get("id") not in seen_node_ids:
                unique_nodes.append(node)
                seen_node_ids.add(node.get("id"))

        # 去重边
        seen_edge_ids = set()
        unique_edges = []
        for edge in merged_edges:
            edge_id = edge.get("id")
            if edge_id not in seen_edge_ids:
                unique_edges.append(edge)
                seen_edge_ids.add(edge_id)

        return GraphQueryResult(unique_nodes, unique_edges)
