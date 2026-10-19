#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识图谱查询与分析接口。
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.core.kg.manager import KnowledgeGraphManager
from app.db.models.rag import RAGContent
from app.db.session import get_db
from app.shared.response_models import ResponseHelper
from app.shared.utils.logger_util import get_logger

logger = get_logger(__name__)

router = APIRouter()

_TYPE_TO_CATEGORY = {
    "技术": 0,
    "技术概念": 0,
    "产品": 0,
    "概念": 1,
    "entity": 1,
    "应用领域": 2,
    "人物": 3,
    "组织": 4,
    "organization": 4,
    "时间": 5,
    "地点": 6,
    "location": 6,
    "事件": 7,
    "event": 7,
    "document": 8,
}

_CATEGORY_META = {
    0: {"name": "技术", "color": "#7FB069"},
    1: {"name": "概念", "color": "#F4C430"},
    2: {"name": "应用领域", "color": "#D18B8B"},
    3: {"name": "人物", "color": "#8B4A8C"},
    4: {"name": "组织", "color": "#69B3D1"},
    5: {"name": "时间", "color": "#F4A460"},
    6: {"name": "地点", "color": "#98D982"},
    7: {"name": "事件", "color": "#DDA0DD"},
    8: {"name": "文档", "color": "#95A5A6"},
}


class KnowledgeGraphQueryRequest(BaseModel):
    """知识图谱查询请求。"""

    query: Optional[str] = Field(None, description="查询关键词")
    node_type: Optional[str] = Field(None, description="节点类型")
    document_id: Optional[str] = Field(None, description="文档ID或资源ID")
    limit: int = Field(10, description="结果数量限制", ge=1, le=100)
    include_relations: bool = Field(True, description="是否返回关系边")
    expand_neighbors: bool = Field(True, description="是否围绕命中节点扩展邻居节点，生成可视化子图")
    max_depth: int = Field(1, description="邻居扩展深度；1 表示一跳关系", ge=1, le=3)
    max_edges: int = Field(200, description="最多返回关系边数量", ge=1, le=1000)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "人工智能",
                "node_type": "技术概念",
                "document_id": "eaac3b67-16eb-48d1-8687-31e3d41c5a09",
                "limit": 10,
                "include_relations": True,
                "expand_neighbors": True,
                "max_depth": 1,
                "max_edges": 200,
            }
        }
    )


class AssociationAnalysisRequest(BaseModel):
    """实体关联分析请求。"""

    entity: str = Field(..., description="实体名称")
    depth: int = Field(2, description="关联深度", ge=1, le=5)
    threshold: float = Field(0.5, description="相关性阈值", ge=0.0, le=1.0)
    limit: int = Field(50, description="最大返回数量", ge=1, le=200)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entity": "人工智能",
                "depth": 2,
                "threshold": 0.5,
                "limit": 50,
            }
        }
    )


def _build_kg_manager() -> KnowledgeGraphManager:
    namespace = (getattr(settings.graph_db, "GRAPH_NAMESPACE", None) or "default").strip() or "default"
    return KnowledgeGraphManager(namespace=namespace)


def _get_node_kind(node: Dict[str, Any]) -> str:
    labels = node.get("labels") or []
    if labels:
        return str(labels[0])
    return str(node.get("node_type") or "entity")


def _build_categories(category_ids: set[int]) -> tuple[dict[int, int], list[dict[str, Any]]]:
    remap: dict[int, int] = {}
    categories: list[dict[str, Any]] = []
    for new_index, category_id in enumerate(sorted(category_ids)):
        meta = _CATEGORY_META.get(category_id, _CATEGORY_META[1])
        remap[category_id] = new_index
        categories.append(
            {
                "name": meta["name"],
                "itemStyle": {"color": meta["color"]},
            }
        )
    return remap, categories


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


def _build_graph_positions(
    nodes: list[Dict[str, Any]],
    edges: list[Dict[str, Any]],
) -> dict[str, tuple[float, float]]:
    """为不会运行力导向布局的图谱前端生成稳定 x/y 坐标。"""
    node_ids = [str(node["id"]) for node in nodes if node.get("id") is not None]
    if not node_ids:
        return {}

    degree = {node_id: 0 for node_id in node_ids}
    for edge in edges or []:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
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


def _with_graph_positions(
    nodes: list[Dict[str, Any]],
    edges: list[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    positions = _build_graph_positions(nodes, edges)
    positioned_nodes: list[Dict[str, Any]] = []

    for node in nodes or []:
        node_id = str(node.get("id") or "")
        positioned = dict(node)
        x = _node_position(positioned, "x")
        y = _node_position(positioned, "y")
        fallback_x, fallback_y = positions.get(node_id, (500.0, 360.0))
        positioned["x"] = x if x is not None else fallback_x
        positioned["y"] = y if y is not None else fallback_y
        positioned_nodes.append(positioned)

    return positioned_nodes


def _build_echarts_payload(
    nodes: list[Dict[str, Any]],
    edges: list[Dict[str, Any]],
) -> Dict[str, Any]:
    node_ids = {str(node["id"]) for node in nodes}
    filtered_edges = [
        edge
        for edge in edges
        if str(edge.get("source")) in node_ids and str(edge.get("target")) in node_ids
    ]

    used_categories = {
        _TYPE_TO_CATEGORY.get(_get_node_kind(node), 1)
        for node in nodes
    } or {1}
    category_remap, categories = _build_categories(used_categories)

    echarts_nodes = []
    for node in nodes:
        node_kind = _get_node_kind(node)
        category_id = _TYPE_TO_CATEGORY.get(node_kind, 1)
        confidence = float((node.get("properties") or {}).get("confidence", 0.8) or 0.8)
        meta = _CATEGORY_META.get(category_id, _CATEGORY_META[1])
        echarts_nodes.append(
            {
                "id": str(node["id"]),
                "name": node.get("name") or str(node["id"]),
                "symbolSize": max(30, min(80, int(confidence * 100))),
                "value": int(confidence * 100),
                "category": category_remap.get(category_id, 0),
                "itemStyle": {"color": meta["color"]},
                "type": node_kind,
                "description": node.get("description", ""),
                "confidence": confidence,
                "x": _node_position(node, "x"),
                "y": _node_position(node, "y"),
                "original_data": node,
            }
        )

    echarts_links = [
        {
            "source": str(edge["source"]),
            "target": str(edge["target"]),
            "relation": edge.get("type", "相关"),
            "description": edge.get("description", ""),
            "confidence": float((edge.get("properties") or {}).get("confidence", 0.8) or 0.8),
            "original_data": edge,
        }
        for edge in filtered_edges
    ]

    return {
        "nodes": echarts_nodes,
        "links": echarts_links,
        "categories": categories,
    }


async def _resolve_document_id(db: Session, raw_document_id: Optional[str]) -> Optional[str]:
    if not raw_document_id:
        return None

    rag_content = (
        db.query(RAGContent)
        .filter((RAGContent.resource_id == raw_document_id) | (RAGContent.id == raw_document_id))
        .first()
    )
    if rag_content:
        logger.info("将 resource_id/content_id %s 映射到 content_id: %s", raw_document_id, rag_content.id)
        return str(rag_content.id)

    rag_content = (
        db.query(RAGContent)
        .filter(
            or_(
                RAGContent.file_name == raw_document_id,
                RAGContent.title == raw_document_id,
                RAGContent.resource_name == raw_document_id,
                RAGContent.file_path == raw_document_id,
                RAGContent.content_url == raw_document_id,
                RAGContent.file_md5 == raw_document_id,
                RAGContent.file_sha256 == raw_document_id,
            )
        )
        .order_by(RAGContent.update_time.desc())
        .first()
    )
    if rag_content:
        logger.info("将文件标识 %s 映射到 content_id: %s", raw_document_id, rag_content.id)
        return str(rag_content.id)

    if "." in raw_document_id or "/" in raw_document_id:
        like_value = f"%{raw_document_id}%"
        rag_content = (
            db.query(RAGContent)
            .filter(
                or_(
                    RAGContent.file_name.like(like_value),
                    RAGContent.title.like(like_value),
                    RAGContent.resource_name.like(like_value),
                    RAGContent.file_path.like(like_value),
                    RAGContent.content_url.like(like_value),
                )
            )
            .order_by(RAGContent.update_time.desc())
            .first()
        )
        if rag_content:
            logger.info("将模糊文件标识 %s 映射到 content_id: %s", raw_document_id, rag_content.id)
            return str(rag_content.id)

    return raw_document_id


def _dedupe_nodes(nodes: list[Dict[str, Any]], *, limit: Optional[int] = None) -> list[Dict[str, Any]]:
    deduped: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for node in nodes or []:
        node_id = str(node.get("id") or "").strip()
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        deduped.append(node)
        if limit is not None and len(deduped) >= limit:
            break
    return deduped


def _dedupe_edges(edges: list[Dict[str, Any]], *, limit: Optional[int] = None) -> list[Dict[str, Any]]:
    deduped: list[Dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for edge in edges or []:
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if not source or not target:
            continue
        key = (source, target, str(edge.get("type") or ""), str(edge.get("source_doc") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(edge)
        if limit is not None and len(deduped) >= limit:
            break
    return deduped


async def _query_nodes_by_ids(
    kg_manager: KnowledgeGraphManager,
    node_ids: list[str],
    *,
    limit: int,
) -> list[Dict[str, Any]]:
    nodes: list[Dict[str, Any]] = []
    for node_id in list(dict.fromkeys(node_ids or []))[:limit]:
        rows = await kg_manager.query_nodes(query=node_id, limit=5)
        exact = next((item for item in rows if str(item.get("id")) == str(node_id)), None)
        if exact:
            nodes.append(exact)
    return nodes


async def _expand_subgraph(
    kg_manager: KnowledgeGraphManager,
    *,
    seed_nodes: list[Dict[str, Any]],
    query: Optional[str],
    document_id: Optional[str],
    include_relations: bool,
    expand_neighbors: bool,
    max_depth: int,
    max_edges: int,
    max_nodes: int,
) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    nodes = _dedupe_nodes(seed_nodes, limit=max_nodes)
    if not include_relations or not nodes:
        return nodes, []

    all_edges: list[Dict[str, Any]] = []
    seen_node_ids = {str(node.get("id")) for node in nodes if node.get("id") is not None}
    frontier = list(seen_node_ids)

    for _depth in range(max(1, max_depth if expand_neighbors else 1)):
        if not frontier or len(all_edges) >= max_edges:
            break
        edges = await kg_manager.query_edges(
            document_id=document_id,
            node_ids=frontier,
            limit=max_edges - len(all_edges),
        )
        all_edges.extend(edges)
        if not expand_neighbors:
            break

        neighbor_ids: list[str] = []
        for edge in edges or []:
            for endpoint in (edge.get("source"), edge.get("target")):
                endpoint_id = str(endpoint or "").strip()
                if endpoint_id and endpoint_id not in seen_node_ids:
                    seen_node_ids.add(endpoint_id)
                    neighbor_ids.append(endpoint_id)

        if not neighbor_ids:
            break
        new_nodes = await _query_nodes_by_ids(kg_manager, neighbor_ids, limit=max_nodes)
        nodes = _dedupe_nodes([*nodes, *new_nodes], limit=max_nodes)
        frontier = [str(node.get("id")) for node in new_nodes if node.get("id") is not None]

    if query and len(all_edges) < max_edges:
        matched_edges = await kg_manager.query_edges(
            query=query,
            document_id=document_id,
            node_ids=list(seen_node_ids) or None,
            limit=max_edges - len(all_edges),
        )
        all_edges.extend(matched_edges)
        edge_node_ids = []
        known = {str(node.get("id")) for node in nodes if node.get("id") is not None}
        for edge in matched_edges or []:
            for endpoint in (edge.get("source"), edge.get("target")):
                endpoint_id = str(endpoint or "").strip()
                if endpoint_id and endpoint_id not in known:
                    known.add(endpoint_id)
                    edge_node_ids.append(endpoint_id)
        if edge_node_ids:
            nodes = _dedupe_nodes([*nodes, *(await _query_nodes_by_ids(kg_manager, edge_node_ids, limit=max_nodes))], limit=max_nodes)

    node_ids = {str(node.get("id")) for node in nodes if node.get("id") is not None}
    edges = [
        edge
        for edge in _dedupe_edges(all_edges, limit=max_edges)
        if str(edge.get("source")) in node_ids and str(edge.get("target")) in node_ids
    ]
    return nodes, edges


@router.post("/query", response_model=Dict)
async def query_knowledge_graph(
    request: KnowledgeGraphQueryRequest,
    db: Session = Depends(get_db),
):
    """查询知识图谱节点与关系。"""

    try:
        actual_document_id = await _resolve_document_id(db, request.document_id)
        kg_manager = _build_kg_manager()
        if not kg_manager.is_enabled():
            return ResponseHelper.success(
                result={
                    "query": request.query,
                    "node_type": request.node_type,
                    "document_id": actual_document_id,
                    "echarts_data": {"nodes": [], "links": [], "categories": []},
                    "nodes": [],
                    "relationships": [],
                    "total_nodes": 0,
                    "total_relationships": 0,
                },
                message="知识图谱服务未启用",
            )

        seed_nodes = await kg_manager.query_nodes(
            query=request.query,
            node_type=request.node_type,
            document_id=actual_document_id,
            limit=request.limit,
        )
        max_nodes = max(request.limit, min(request.limit * max(2, request.max_depth + 1), 300))
        nodes, relationships = await _expand_subgraph(
            kg_manager,
            seed_nodes=seed_nodes,
            query=request.query,
            document_id=actual_document_id,
            include_relations=request.include_relations,
            expand_neighbors=request.expand_neighbors,
            max_depth=request.max_depth,
            max_edges=request.max_edges,
            max_nodes=max_nodes,
        )
        nodes = _with_graph_positions(nodes, relationships)

        echarts_data = _build_echarts_payload(nodes, relationships)

        return ResponseHelper.success(
            result={
                "query": request.query,
                "node_type": request.node_type,
                "document_id": actual_document_id,
                "include_relations": request.include_relations,
                "expand_neighbors": request.expand_neighbors,
                "max_depth": request.max_depth,
                "echarts_data": echarts_data,
                "nodes": nodes,
                "relationships": relationships,
                "seed_node_count": len(seed_nodes),
                "total_nodes": len(nodes),
                "total_relationships": len(echarts_data["links"]),
            },
            message="知识图谱查询成功",
        )
    except Exception as exc:
        logger.error("知识图谱查询失败: %s", exc, exc_info=True)
        return ResponseHelper.error(message=f"知识图谱查询失败: {exc}", status=500)


@router.post("/analysis/association", response_model=Dict)
async def analyze_entity_associations(
    request: AssociationAnalysisRequest,
):
    """分析指定实体的关联网络。"""

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
            },
            message="实体关联分析成功",
        )
    except Exception as exc:
        logger.error("实体关联分析失败: %s", exc, exc_info=True)
        return ResponseHelper.error(message=f"关联分析失败: {exc}", status=500)


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
            },
            message="获取知识图谱统计成功",
        )
    except Exception as exc:
        logger.error("获取知识图谱统计失败: %s", exc, exc_info=True)
        return ResponseHelper.error(message=f"获取统计信息失败: {exc}", status=500)
