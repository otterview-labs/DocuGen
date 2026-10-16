#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识图谱可视化接口。
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.core.kg.manager import KnowledgeGraphManager
from app.db.models.rag import RAGCollectionContent, RAGContent
from app.db.session import get_db
from app.shared.response_models import ResponseHelper
from app.shared.utils.logger_util import get_logger

logger = get_logger(__name__)

router = APIRouter()

_TYPE_TO_COLOR = {
    "技术": "#7FB069",
    "技术概念": "#7FB069",
    "产品": "#7FB069",
    "概念": "#F4C430",
    "entity": "#F4C430",
    "应用领域": "#D18B8B",
    "人物": "#8B4A8C",
    "组织": "#69B3D1",
    "organization": "#69B3D1",
    "时间": "#F4A460",
    "地点": "#98D982",
    "location": "#98D982",
    "事件": "#DDA0DD",
    "event": "#DDA0DD",
    "document": "#95A5A6",
}


class GraphVisualizationRequest(BaseModel):
    """图谱可视化请求参数。"""

    query: Optional[str] = Field(None, description="搜索关键词")
    entity_type: Optional[str] = Field(None, description="实体类型过滤")
    collection_id: Optional[str] = Field(None, description="集合ID")
    max_nodes: int = Field(100, description="最大节点数", ge=1, le=500)
    layout: str = Field("force", description="布局类型")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "人工智能",
                "entity_type": "技术概念",
                "max_nodes": 100,
                "layout": "force",
            }
        }
    )


class AssociationAnalysisRequest(BaseModel):
    """实体关联分析请求。"""

    entity: str = Field(..., description="实体名称")
    depth: int = Field(2, description="关联深度", ge=1, le=5)
    threshold: float = Field(0.5, description="相关性阈值", ge=0.0, le=1.0)
    limit: int = Field(50, description="最大返回数量", ge=1, le=200)


def _build_kg_manager() -> KnowledgeGraphManager:
    namespace = (getattr(settings.graph_db, "GRAPH_NAMESPACE", None) or "default").strip() or "default"
    return KnowledgeGraphManager(namespace=namespace)


def _node_kind(node: Dict[str, Any]) -> str:
    labels = node.get("labels") or []
    if labels:
        return str(labels[0])
    return str(node.get("node_type") or "entity")


def _coerce_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _node_position(node: Dict[str, Any], key: str) -> Optional[float]:
    value = _coerce_float(node.get(key))
    if value is not None:
        return value
    return _coerce_float((node.get("properties") or {}).get(key))


def _dedupe_nodes(nodes: list[Dict[str, Any]], *, limit: int) -> list[Dict[str, Any]]:
    deduped: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for node in nodes or []:
        node_id = str(node.get("id") or "").strip()
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        deduped.append(node)
        if len(deduped) >= limit:
            break
    return deduped


def _dedupe_edges(edges: list[Dict[str, Any]], *, limit: int) -> list[Dict[str, Any]]:
    deduped: list[Dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in edges or []:
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        edge_type = str(edge.get("type") or "").strip()
        if not source or not target:
            continue
        key = (source, target, edge_type)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(edge)
        if len(deduped) >= limit:
            break
    return deduped


def _build_graph_positions(
    nodes: list[Dict[str, Any]],
    links: list[Dict[str, Any]],
) -> dict[str, tuple[float, float]]:
    node_ids = [str(node["id"]) for node in nodes if node.get("id") is not None]
    if not node_ids:
        return {}

    degree = {node_id: 0 for node_id in node_ids}
    for link in links or []:
        source = str(link.get("source") or "")
        target = str(link.get("target") or "")
        if source in degree:
            degree[source] += 1
        if target in degree:
            degree[target] += 1

    original_index = {node_id: index for index, node_id in enumerate(node_ids)}
    ranked_ids = sorted(node_ids, key=lambda node_id: (-degree.get(node_id, 0), original_index[node_id]))
    center_x = 500.0
    center_y = 360.0
    positions: dict[str, tuple[float, float]] = {}

    for rank, node_id in enumerate(ranked_ids):
        if len(ranked_ids) == 1 or rank == 0:
            positions[node_id] = (center_x, center_y)
            continue

        offset = rank - 1
        ring = 0
        ring_start = 0
        ring_capacity = 10
        while offset >= ring_start + ring_capacity:
            ring_start += ring_capacity
            ring += 1
            ring_capacity = 10 + ring * 8

        pos_in_ring = offset - ring_start
        remaining = len(ranked_ids) - 1 - ring_start
        count_in_ring = min(ring_capacity, max(1, remaining))
        radius = 150.0 + ring * 125.0
        angle = (2 * math.pi * pos_in_ring / count_in_ring) - (math.pi / 2) + ring * 0.31
        positions[node_id] = (
            round(center_x + radius * math.cos(angle), 3),
            round(center_y + radius * math.sin(angle), 3),
        )

    return positions


async def _query_collection_graph(
    kg_manager: KnowledgeGraphManager,
    db: Session,
    request: GraphVisualizationRequest,
) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    content_ids = [
        row[0]
        for row in (
            db.query(RAGCollectionContent.content_id)
            .join(RAGContent, RAGContent.id == RAGCollectionContent.content_id)
            .filter(RAGCollectionContent.collection_id == request.collection_id)
            .order_by(RAGContent.update_time.desc())
            .limit(max(request.max_nodes * 4, request.max_nodes))
            .all()
        )
    ]
    if not content_ids:
        return [], []

    nodes: list[Dict[str, Any]] = []
    for content_id in content_ids:
        if len(nodes) >= request.max_nodes:
            break
        batch = await kg_manager.query_nodes(
            query=request.query,
            node_type=request.entity_type,
            document_id=str(content_id),
            limit=max(10, request.max_nodes - len(nodes)),
        )
        nodes = _dedupe_nodes([*nodes, *batch], limit=request.max_nodes)

    node_ids = [str(node["id"]) for node in nodes if node.get("id") is not None]
    if not node_ids:
        return nodes, []

    max_edges = max(request.max_nodes * 4, 100)
    edges: list[Dict[str, Any]] = []
    for content_id in content_ids:
        if len(edges) >= max_edges:
            break
        batch = await kg_manager.query_edges(
            query=request.query,
            document_id=str(content_id),
            node_ids=node_ids,
            limit=max_edges - len(edges),
        )
        edges = _dedupe_edges([*edges, *batch], limit=max_edges)

    node_id_set = set(node_ids)
    edges = [
        edge
        for edge in edges
        if str(edge.get("source")) in node_id_set and str(edge.get("target")) in node_id_set
    ]
    return nodes, edges


@router.post("/visualization/graph-data", response_model=Dict)
async def get_graph_visualization_data(
    request: GraphVisualizationRequest,
    db: Session = Depends(get_db),
):
    """获取可视化图谱数据。"""

    try:
        kg_manager = _build_kg_manager()
        if not kg_manager.is_enabled():
            return ResponseHelper.success(
                result={
                    "nodes": [],
                    "links": [],
                    "statistics": {
                        "total_knowledge": 0,
                        "total_nodes": 0,
                        "total_relationships": 0,
                        "node_types": {},
                        "relationship_types": {},
                    },
                },
                message="知识图谱服务未启用",
            )

        if request.collection_id:
            nodes, edges = await _query_collection_graph(kg_manager, db, request)
        else:
            nodes = await kg_manager.query_nodes(
                query=request.query,
                node_type=request.entity_type,
                limit=request.max_nodes,
            )
            node_ids = [str(node["id"]) for node in nodes]
            edges = await kg_manager.query_edges(
                query=request.query,
                node_ids=node_ids or None,
                limit=max(request.max_nodes * 4, 100),
            )

        node_ids = [str(node["id"]) for node in nodes]

        links = [
            {
                "source": str(edge["source"]),
                "target": str(edge["target"]),
                "type": edge.get("type", "相关"),
                "properties": edge.get("properties") or {},
            }
            for edge in edges
            if str(edge.get("source")) in node_ids and str(edge.get("target")) in node_ids
        ]
        positions = _build_graph_positions(nodes, links)

        node_types: Dict[str, int] = {}
        graph_nodes = []
        for node in nodes:
            node_type = _node_kind(node)
            node_types[node_type] = node_types.get(node_type, 0) + 1
            node_id = str(node["id"])
            fallback_x, fallback_y = positions.get(node_id, (500.0, 360.0))
            graph_nodes.append(
                {
                    "id": node_id,
                    "name": node.get("name") or node_id,
                    "type": node_type,
                    "value": max(1, len(node.get("description", "") or "") // 50),
                    "x": _node_position(node, "x") if _node_position(node, "x") is not None else fallback_x,
                    "y": _node_position(node, "y") if _node_position(node, "y") is not None else fallback_y,
                    "properties": node.get("properties") or {},
                    "itemStyle": {"color": _TYPE_TO_COLOR.get(node_type, "#95A5A6")},
                }
            )

        relationship_types: Dict[str, int] = {}
        for link in links:
            relationship_types[link["type"]] = relationship_types.get(link["type"], 0) + 1

        return ResponseHelper.success(
            result={
                "nodes": graph_nodes,
                "links": links,
                "statistics": {
                    "total_knowledge": len(graph_nodes),
                    "total_nodes": len(graph_nodes),
                    "total_relationships": len(links),
                    "node_types": node_types,
                    "relationship_types": relationship_types,
                },
            },
            message=f"获取到{len(graph_nodes)}个节点和{len(links)}条关系",
        )
    except Exception as exc:
        logger.error("获取图谱可视化数据失败: %s", exc, exc_info=True)
        return ResponseHelper.error(message=f"获取图谱数据失败: {exc}")


@router.get("/statistics/knowledge-graph", response_model=Dict)
async def get_knowledge_graph_statistics():
    """获取知识图谱统计信息。"""

    try:
        kg_manager = _build_kg_manager()
        stats = await kg_manager.get_graph_statistics()
        if not stats.get("enabled", False):
            return ResponseHelper.success(
                result={
                    "total_knowledge": 0,
                    "total_nodes": 0,
                    "total_relationships": 0,
                    "node_types": {},
                    "relationship_types": {},
                },
                message="知识图谱服务未启用",
            )

        return ResponseHelper.success(
            result={
                "total_knowledge": int(stats.get("total_knowledge", 0) or 0),
                "total_nodes": int(stats.get("total_nodes", 0) or 0),
                "total_relationships": int(stats.get("total_relationships", 0) or 0),
                "node_types": stats.get("node_types", {}) or {},
                "relationship_types": stats.get("relationship_types", {}) or {},
            }
        )
    except Exception as exc:
        logger.error("获取图谱统计信息失败: %s", exc, exc_info=True)
        return ResponseHelper.error(message=f"获取统计信息失败: {exc}")


@router.post("/analysis/association", response_model=Dict)
async def analyze_entity_associations(request: AssociationAnalysisRequest):
    """实体关联分析。"""

    try:
        kg_manager = _build_kg_manager()
        if not kg_manager.is_enabled():
            return ResponseHelper.success(
                result={
                    "entity": request.entity,
                    "associations": [],
                    "total_associations": 0,
                    "max_depth": request.depth,
                    "threshold": request.threshold,
                },
                message="知识图谱服务未启用",
            )

        associations = await kg_manager.analyze_entity_associations(
            request.entity,
            max_depth=request.depth,
            limit=request.limit,
        )
        filtered = [item for item in associations if float(item.get("relevance", 0.0)) >= request.threshold]

        return ResponseHelper.success(
            result={
                "entity": request.entity,
                "associations": filtered,
                "total_associations": len(filtered),
                "max_depth": request.depth,
                "threshold": request.threshold,
            }
        )
    except Exception as exc:
        logger.error("实体关联分析失败: %s", exc, exc_info=True)
        return ResponseHelper.error(message=f"关联分析失败: {exc}")
