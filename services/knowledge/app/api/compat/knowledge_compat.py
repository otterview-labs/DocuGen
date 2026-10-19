#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库旧接口兼容层：/knowledge/resource/*

为 jetlinks 老前端（cloud.jetlinks.ui 的 jetlinks-knowledge-ui /
jetlinks-ai-agent-ui）提供 /knowledge/resource/* 路径兼容，内部转换并
转发到现有 /api/v1/rag/* 能力。挂在顶层 /knowledge（不带 /api/v1 前缀，
因为前端 baseURL 直连 runtime，请求路径就是 /knowledge/...）。

本期（P0）覆盖两个核心接口：
- POST /knowledge/resource/_search                              -> unified_search_service
- POST /knowledge/resource/defaultAi/cmd/queryKnowledgeGraph   -> kg manager

认证使用 get_compat_request_user：token 缺失或解析失败（含外部用户体系 token）
均返回 None，绝不抛 401。

其余 /knowledge/* 接口（资源 CRUD / 分类 / 解析 / 统计 / WebSocket）后续 P1/P2 再补。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

try:
    from loguru import logger
except ImportError:  # pragma: no cover
    import logging

    logger = logging.getLogger(__name__)

from app.api.v1.deps import get_compat_request_user
from app.api.v1.rag.endpoints.kg import (  # 复用 kg.py 模块级辅助函数，不改动 kg.py
    KnowledgeGraphQueryRequest,
    _build_echarts_payload,
    _build_kg_manager,
    _resolve_document_id,
)
from app.db.session import get_db
from app.schemas.search import SearchRequest
from app.services.unified_search_service import get_unified_search_service
from app.shared.response_models import ResponseHelper

router = APIRouter(prefix="/knowledge", tags=["知识库-兼容层"])


# runtime 对外公开的检索模式（含内部/历史兼容名）
_RUNTIME_SEARCH_MODES = {
    "intelligent",
    "semantic",
    "keyword",
    "kg",
    "file",
    "image",
    "image_to_image",
    "visual_similarity",  # 内部名
    "hybrid",  # 历史兼容
}


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _normalize_search_mode(raw: Optional[str]) -> str:
    """前端 expands.searchMode -> runtime search_mode；未命中则 fallback intelligent。"""
    if not raw:
        return "intelligent"
    mode = str(raw).strip().lower()
    return mode if mode in _RUNTIME_SEARCH_MODES else "intelligent"


def _as_dict(obj: Any) -> Dict[str, Any]:
    """把检索结果项统一成 dict（兼容 dict / pydantic model / 普通对象）。"""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if hasattr(obj, "__dict__"):
        return vars(obj)
    return {}


def _guess_extension(item: Dict[str, Any]) -> Optional[str]:
    """从结果元数据/内容类型推断文件扩展名。"""
    metadata = item.get("metadata") or {}
    ext = metadata.get("extension") or metadata.get("ext") or metadata.get("file_extension")
    if ext:
        return str(ext).lstrip(".")
    content_type = (item.get("content_type") or "").lower()
    type_map = {
        "pdf": "pdf",
        "document": "doc",
        "image": "png",
        "video": "mp4",
        "text": "txt",
        "url": "html",
        "knowledge_graph": None,
    }
    return type_map.get(content_type)


def _map_search_item(item: Any) -> Dict[str, Any]:
    """runtime SearchResultItem -> 前端 hitSearch 期望结构。

    前端期望每项形如：
        {
          "snippet": str, "confidence": float,
          "expands": {"summary": str},
          "knowledge": {"id": str, "name": str, "content": {"extension": str}}
        }
    """
    item = _as_dict(item)

    snippet = item.get("snippet") or item.get("description")
    if not snippet:
        content = item.get("content")
        if content:
            snippet = str(content)[:200]

    confidence = item.get("similarity_score")
    if confidence is None:
        confidence = item.get("score")

    return {
        "snippet": snippet,
        "confidence": confidence,
        "expands": {
            "summary": item.get("description"),
        },
        "knowledge": {
            "id": item.get("resource_id") or item.get("content_id") or item.get("id"),
            "name": item.get("title"),
            "content": {
                "extension": _guess_extension(item),
            },
        },
    }


# ---------------------------------------------------------------------------
# 接口1：检索
# ---------------------------------------------------------------------------

@router.post("/resource/_search")
async def compat_resource_search(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: Optional[Any] = Depends(get_compat_request_user),
):
    """兼容 POST /knowledge/resource/_search -> /api/v1/rag/search/unified。

    前端请求体形如：
        {"text": "查询内容", "expands": {"searchMode": "semantic", "collectionId": ["..."]}}
    返回 {success, result: [{snippet, confidence, expands, knowledge}, ...]}。
    """
    try:
        text = payload.get("text") or payload.get("query")
        if not text:
            return ResponseHelper.success(result=[], message="success")

        expands = payload.get("expands") or {}
        raw_collection = expands.get("collectionId") or expands.get("collection_id")
        collection_id: Optional[List[str]] = None
        if isinstance(raw_collection, list):
            collection_id = raw_collection or None
        elif raw_collection:
            collection_id = [raw_collection]

        request = SearchRequest(
            query=text,
            search_mode=_normalize_search_mode(expands.get("searchMode")),
            collection_id=collection_id,
        )

        # 对齐 unified_search endpoint：从用户上下文补充权限绑定
        if current_user and hasattr(current_user, "permissions") and not request.bindings:
            request.bindings = getattr(current_user, "permissions", [])

        search_service = get_unified_search_service()
        search_result = await search_service.search(
            request=request,
            user_id=getattr(current_user, "id", None),
            db=db,
        )

        results: List[Any] = search_result.get("results", []) or []
        mapped = [_map_search_item(item) for item in results]
        return ResponseHelper.success(result=mapped, message="success")
    except Exception as exc:
        logger.error("兼容层检索失败: {}", exc, exc_info=True)
        return ResponseHelper.error(message=f"检索失败: {exc}", status=500)


# ---------------------------------------------------------------------------
# 接口2：知识图谱
# ---------------------------------------------------------------------------

@router.post("/resource/defaultAi/cmd/queryKnowledgeGraph")
async def compat_query_knowledge_graph(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """兼容 POST /knowledge/resource/defaultAi/cmd/queryKnowledgeGraph -> /api/v1/rag/kg/query。

    前端请求体形如：{"document_id": "..."}（也可用 resource_id）。
    返回 {success, result: {data: {echarts_data: {nodes, links, categories}, ...}}}。
    前端取 result.data.echarts_data，故相比 runtime 原接口多包一层 data。
    """
    try:
        request = KnowledgeGraphQueryRequest(
            query=payload.get("query"),
            node_type=payload.get("node_type"),
            document_id=payload.get("document_id") or payload.get("resource_id"),
            limit=payload.get("limit", 10),
        )

        actual_document_id = await _resolve_document_id(db, request.document_id)
        kg_manager = _build_kg_manager()

        if not kg_manager.is_enabled():
            runtime_result = {
                "query": request.query,
                "node_type": request.node_type,
                "document_id": actual_document_id,
                "echarts_data": {"nodes": [], "links": [], "categories": []},
                "nodes": [],
                "relationships": [],
                "total_nodes": 0,
                "total_relationships": 0,
            }
            return ResponseHelper.success(
                result={"data": runtime_result},
                message="知识图谱服务未启用",
            )

        nodes = await kg_manager.query_nodes(
            query=request.query,
            node_type=request.node_type,
            document_id=actual_document_id,
            limit=request.limit,
        )
        node_ids = [str(node["id"]) for node in nodes]
        edges = await kg_manager.query_edges(
            query=request.query,
            document_id=actual_document_id,
            node_ids=node_ids or None,
            limit=max(request.limit * 10, 100),
        )
        echarts_data = _build_echarts_payload(nodes, edges)

        runtime_result = {
            "query": request.query,
            "node_type": request.node_type,
            "document_id": actual_document_id,
            "echarts_data": echarts_data,
            "nodes": nodes,
            "relationships": [
                edge
                for edge in edges
                if str(edge.get("source")) in node_ids and str(edge.get("target")) in node_ids
            ],
            "total_nodes": len(nodes),
            "total_relationships": len(echarts_data["links"]),
        }

        return ResponseHelper.success(
            result={"data": runtime_result},
            message="知识图谱查询成功",
        )
    except Exception as exc:
        logger.error("兼容层知识图谱查询失败: {}", exc, exc_info=True)
        return ResponseHelper.error(message=f"知识图谱查询失败: {exc}", status=500)
